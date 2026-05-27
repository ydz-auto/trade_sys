"""
Consistency Test - 研究工具一致性验证

验证 simple_backtest 和 walk_forward 在相同数据、相同策略、
相同手续费/滑点下，输出是否一致。

验收标准：
1. 同一口径（single_bar）下，两者 avg_trade_return 差异 < 1e-4
2. 同一口径（holding_period）下，两者指标差异 < 1%
3. 不同口径（single_bar vs holding_period）差异可解释
4. walk_forward (holding_bars=10) 与 simple_backtest 端到端一致
5. 并行 vs 串行结果一致

使用方式：
    python -m research.consistency_test --strategy funding_extreme_reversal --days 90
    python -m research.consistency_test --strategy funding_extreme_reversal --days 90 --source parquet
"""

import sys
from pathlib import Path
from typing import Dict, Any
import argparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import numpy as np

from engines.compute.strategy_v2 import StrategyV2, SignalType
from research.common.backtest_engine import (
    run_single_bar_backtest,
    run_holding_period_backtest,
    BacktestMetrics,
)
from research.common.loaders import get_strategy_class, load_from_parquet
from research.common.types import StrategyName
from research.simple_backtest import SimpleBacktester
from research.common.mock import generate_test_contexts
from research.walk_forward_simple import (
    WalkForwardAnalyzer,
    run_walk_forward,
    run_walk_forward_parallel,
)


TAKER_FEE = 0.0005
MAKER_FEE = 0.0002
SLIPPAGE_BPS = 2.0


def _fmt_pct(v: float) -> str:
    return f"{v:.6f}" if abs(v) < 1 else f"{v:.2f}"


def test_single_bar_consistency(
    strategy: StrategyV2,
    market_contexts,
    timestamps,
    prices,
) -> Dict[str, Any]:
    """
    测试1: single_bar_backtest 在全量数据上的结果
    与 walk_forward 全量窗口（单窗口覆盖全部数据）的结果对比
    """
    # 直接调用 single_bar_backtest
    _, direct_metrics = run_single_bar_backtest(
        strategy, market_contexts, timestamps, prices,
        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, slippage_bps=SLIPPAGE_BPS
    )

    # 通过 walk_forward 单窗口覆盖全部数据
    total_bars = len(market_contexts)
    intervals = np.diff(timestamps)
    avg_interval = np.mean(intervals) if len(intervals) > 0 else 60000
    day_ms = 24 * 60 * 60 * 1000
    total_days = int(total_bars * avg_interval / day_ms)

    if total_days < 2:
        return {"status": "SKIP", "reason": "数据不足"}

    # 留足训练期空间: train=1天, test 留 2 天余量
    test_days = max(1, total_days - 3)
    analyzer = WalkForwardAnalyzer(
        train_period_days=1,
        test_period_days=test_days,
        maker_fee=MAKER_FEE,
        taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS,
        holding_bars=1,
    )
    wf_result = analyzer.analyze(strategy, market_contexts, timestamps, prices)

    if not wf_result.window_results:
        return {"status": "SKIP", "reason": "无窗口结果"}

    wf_window = wf_result.window_results[0]

    # 比较
    avg_ret_diff = abs(direct_metrics.avg_trade_return - wf_window.avg_return)
    total_pnl_diff = abs(direct_metrics.total_pnl_pct - wf_window.total_return)
    win_rate_diff = abs(direct_metrics.win_rate - wf_window.win_rate)

    # total_pnl 差异来自窗口边界（walk_forward 跳过训练期数据），允许相对 5% 或绝对 0.2
    passed = (
        avg_ret_diff < 1e-4
        and win_rate_diff < 0.01
        and (total_pnl_diff < 0.2
             or (abs(direct_metrics.total_pnl_pct) > 0
                 and total_pnl_diff / abs(direct_metrics.total_pnl_pct) < 0.05))
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "direct": {
            "trades": direct_metrics.total_trades,
            "avg_return": direct_metrics.avg_trade_return,
            "total_pnl": direct_metrics.total_pnl_pct,
            "win_rate": direct_metrics.win_rate,
            "profit_factor": direct_metrics.profit_factor,
        },
        "walk_forward": {
            "trades": wf_window.signals,
            "avg_return": wf_window.avg_return,
            "total_return": wf_window.total_return,
            "win_rate": wf_window.win_rate,
            "profit_factor": wf_window.profit_factor,
        },
        "diff": {
            "avg_return": avg_ret_diff,
            "total_pnl": total_pnl_diff,
            "win_rate": win_rate_diff,
        },
    }


def test_holding_period_consistency(
    strategy: StrategyV2,
    market_contexts,
    timestamps,
    prices,
    holding_bars: int = 10,
) -> Dict[str, Any]:
    """
    测试2: holding_period_backtest 在全量数据上的结果
    与 simple_backtest 在全量数据上的结果对比
    """
    # 直接调用 holding_period_backtest
    _, engine_metrics = run_holding_period_backtest(
        strategy, market_contexts, timestamps, prices,
        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS, max_holding_bars=holding_bars
    )

    # 通过 SimpleBacktester
    backtester = SimpleBacktester(
        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS, max_holding_bars=holding_bars
    )
    bt_trades, bt_metrics = backtester.backtest(strategy, market_contexts, timestamps, prices)

    trades_diff = abs(engine_metrics.total_trades - bt_metrics.total_trades)
    avg_ret_diff = abs(engine_metrics.avg_trade_return - bt_metrics.avg_trade_return)
    win_rate_diff = abs(engine_metrics.win_rate - bt_metrics.win_rate)
    pf_diff = abs(engine_metrics.profit_factor - bt_metrics.profit_factor)

    passed = (
        trades_diff == 0
        and avg_ret_diff < 1e-4
        and win_rate_diff < 0.01
        and pf_diff < 0.01
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "engine": {
            "trades": engine_metrics.total_trades,
            "avg_return": engine_metrics.avg_trade_return,
            "win_rate": engine_metrics.win_rate,
            "profit_factor": engine_metrics.profit_factor,
            "sharpe": engine_metrics.sharpe_ratio,
        },
        "backtester": {
            "trades": bt_metrics.total_trades,
            "avg_return": bt_metrics.avg_trade_return,
            "win_rate": bt_metrics.win_rate,
            "profit_factor": bt_metrics.profit_factor,
            "sharpe": bt_metrics.sharpe_ratio,
        },
        "diff": {
            "trades": trades_diff,
            "avg_return": avg_ret_diff,
            "win_rate": win_rate_diff,
            "profit_factor": pf_diff,
        },
    }


def test_cross_mode_explainability(
    strategy: StrategyV2,
    market_contexts,
    timestamps,
    prices,
) -> Dict[str, Any]:
    """
    测试3: single_bar vs holding_period 差异可解释性

    预期差异：
    - single_bar 交易数 >= holding_period 交易数（仓位管理限制）
    - 单笔收益应接近（收益计算逻辑相同）
    """
    _, single_metrics = run_single_bar_backtest(
        strategy, market_contexts, timestamps, prices,
        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, slippage_bps=SLIPPAGE_BPS
    )
    _, holding_metrics = run_holding_period_backtest(
        strategy, market_contexts, timestamps, prices,
        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS, max_holding_bars=10
    )

    trades_ratio = (
        single_metrics.total_trades / holding_metrics.total_trades
        if holding_metrics.total_trades > 0 else float('inf')
    )
    avg_ret_ratio = (
        single_metrics.avg_trade_return / holding_metrics.avg_trade_return
        if abs(holding_metrics.avg_trade_return) > 1e-10 else float('inf')
    )

    explainable = (
        single_metrics.total_trades >= holding_metrics.total_trades
        and (trades_ratio <= 5.0 or single_metrics.total_trades == 0)
    )

    return {
        "status": "PASS" if explainable else "FAIL",
        "single_bar": {
            "trades": single_metrics.total_trades,
            "avg_return": single_metrics.avg_trade_return,
            "win_rate": single_metrics.win_rate,
        },
        "holding_period": {
            "trades": holding_metrics.total_trades,
            "avg_return": holding_metrics.avg_trade_return,
            "win_rate": holding_metrics.win_rate,
        },
        "explainability": {
            "trades_ratio": trades_ratio,
            "avg_ret_ratio": avg_ret_ratio,
            "single_ge_holding": single_metrics.total_trades >= holding_metrics.total_trades,
        },
    }


def test_walkforward_vs_simplebacktest(
    strategy: StrategyV2,
    market_contexts,
    timestamps,
    prices,
    holding_bars: int = 10,
) -> Dict[str, Any]:
    """
    测试4: walk_forward (holding_bars=N) vs simple_backtest (max_holding_bars=N) 端到端对比

    用单窗口 walk_forward 覆盖绝大部分数据，与 simple_backtest 全量数据对比。
    由于 walk_forward 会跳过训练期数据，交易数可能略有差异，
    但 per-trade 指标（avg_return, win_rate）应接近。
    """
    total_bars = len(market_contexts)
    intervals = np.diff(timestamps)
    avg_interval = np.mean(intervals) if len(intervals) > 0 else 60000
    day_ms = 24 * 60 * 60 * 1000
    total_days = int(total_bars * avg_interval / day_ms)

    if total_days < 3:
        return {"status": "SKIP", "reason": "数据不足"}

    # walk_forward: 单窗口，训练1天，测试留 2 天余量
    test_days = max(1, total_days - 3)
    wf_result = run_walk_forward(
        strategy, market_contexts, timestamps, prices,
        train_period_days=1,
        test_period_days=test_days,
        maker_fee=MAKER_FEE,
        taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS,
        holding_bars=holding_bars,
    )

    if not wf_result.window_results:
        return {"status": "SKIP", "reason": "无窗口结果"}

    wf_window = wf_result.window_results[0]

    # simple_backtest: 全量数据
    backtester = SimpleBacktester(
        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS, max_holding_bars=holding_bars
    )
    bt_trades, bt_metrics = backtester.backtest(strategy, market_contexts, timestamps, prices)

    avg_ret_diff = abs(wf_window.avg_return - bt_metrics.avg_trade_return)
    win_rate_diff = abs(wf_window.win_rate - bt_metrics.win_rate)
    total_ret_diff = abs(wf_window.total_return - bt_metrics.total_pnl_pct)

    passed = (
        avg_ret_diff < 0.01
        and win_rate_diff < 0.02
        and (total_ret_diff < 0.2
             or (abs(bt_metrics.total_pnl_pct) > 0
                 and total_ret_diff / abs(bt_metrics.total_pnl_pct) < 0.10))
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "walk_forward": {
            "trades": wf_window.signals,
            "avg_return": wf_window.avg_return,
            "total_return": wf_window.total_return,
            "win_rate": wf_window.win_rate,
        },
        "simple_backtest": {
            "trades": bt_metrics.total_trades,
            "avg_return": bt_metrics.avg_trade_return,
            "total_return": bt_metrics.total_pnl_pct,
            "win_rate": bt_metrics.win_rate,
        },
        "diff": {
            "avg_return": avg_ret_diff,
            "total_return": total_ret_diff,
            "win_rate": win_rate_diff,
        },
    }


def test_parallel_vs_sequential(
    strategy: StrategyV2,
    market_contexts,
    timestamps,
    prices,
    holding_bars: int = 1,
) -> Dict[str, Any]:
    """
    测试5: 并行 vs 串行 walk_forward 结果一致性

    两者使用相同的引擎和数据，结果应完全一致。
    """
    total_bars = len(market_contexts)
    intervals = np.diff(timestamps)
    avg_interval = np.mean(intervals) if len(intervals) > 0 else 60000
    day_ms = 24 * 60 * 60 * 1000
    total_days = int(total_bars * avg_interval / day_ms)

    if total_days < 10:
        return {"status": "SKIP", "reason": "数据不足"}

    train_days = max(1, total_days // 5)
    test_days = max(1, (total_days - train_days) // 3)

    # 串行
    seq_result = run_walk_forward(
        strategy, market_contexts, timestamps, prices,
        train_period_days=train_days,
        test_period_days=test_days,
        maker_fee=MAKER_FEE,
        taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS,
        holding_bars=holding_bars,
    )

    # 并行（使用 sequential executor 避免多进程开销）
    par_result = run_walk_forward_parallel(
        strategy, market_contexts, timestamps, prices,
        train_period_days=train_days,
        test_period_days=test_days,
        maker_fee=MAKER_FEE,
        taker_fee=TAKER_FEE,
        slippage_bps=SLIPPAGE_BPS,
        holding_bars=holding_bars,
        executor="sequential",
    )

    # 比较
    windows_match = seq_result.total_windows == par_result.total_windows
    avg_ret_diff = abs(seq_result.avg_return - par_result.avg_return)
    hit_rate_diff = abs(seq_result.avg_hit_rate - par_result.avg_hit_rate)

    # 逐窗口比较
    window_diffs = []
    min_windows = min(len(seq_result.window_results), len(par_result.window_results))
    for i in range(min_windows):
        sw = seq_result.window_results[i]
        pw = par_result.window_results[i]
        window_diffs.append({
            "window": i,
            "signals_diff": abs(sw.signals - pw.signals),
            "avg_return_diff": abs(sw.avg_return - pw.avg_return),
            "win_rate_diff": abs(sw.win_rate - pw.win_rate),
        })

    all_windows_match = all(
        d["signals_diff"] == 0 and d["avg_return_diff"] < 1e-6 and d["win_rate_diff"] < 1e-6
        for d in window_diffs
    )

    passed = windows_match and avg_ret_diff < 1e-6 and hit_rate_diff < 1e-6 and all_windows_match

    return {
        "status": "PASS" if passed else "FAIL",
        "sequential": {
            "windows": seq_result.total_windows,
            "avg_return": seq_result.avg_return,
            "avg_hit_rate": seq_result.avg_hit_rate,
        },
        "parallel": {
            "windows": par_result.total_windows,
            "avg_return": par_result.avg_return,
            "avg_hit_rate": par_result.avg_hit_rate,
        },
        "diff": {
            "windows_match": windows_match,
            "avg_return": avg_ret_diff,
            "avg_hit_rate": hit_rate_diff,
            "all_windows_match": all_windows_match,
        },
    }


def run_all_tests(
    strategy_name: str,
    symbol: str,
    days: int,
    source: str = "mock",
) -> bool:
    """运行所有一致性测试"""
    print("=" * 60)
    print("研究工具一致性验证")
    print(f"策略: {strategy_name} | 交易对: {symbol} | 天数: {days} | 数据源: {source}")
    print(f"手续费: Taker {TAKER_FEE*100:.2f}% | 滑点: {SLIPPAGE_BPS} bps")
    print("=" * 60)

    # 加载数据
    strategy_class = get_strategy_class(strategy_name)
    if not strategy_class:
        print(f"错误: 未知策略 {strategy_name}")
        return False

    if source == "parquet":
        market_contexts, timestamps, prices = load_from_parquet(symbol, days)
        if not market_contexts:
            print("parquet 无数据，回退到 mock...")
            source = "mock"

    if source == "mock":
        np.random.seed(42)
        samples_per_day = 96
        num_samples = days * samples_per_day
        print(f"生成 mock 数据: {num_samples} 个样本 (seed=42)...")
        market_contexts, timestamps, prices = generate_test_contexts(num_samples)

    strategy = strategy_class(symbol)
    print(f"数据: {len(market_contexts)} 条, 价格范围 [{prices.min():.2f}, {prices.max():.2f}]")
    print()

    all_passed = True

    # 测试1: single_bar 一致性
    print("测试1: single_bar_backtest vs walk_forward (全量单窗口)")
    print("-" * 50)
    r1 = test_single_bar_consistency(strategy, market_contexts, timestamps, prices)
    _print_result(r1)
    if r1["status"] == "FAIL":
        all_passed = False
    print()

    # 测试2: holding_period 一致性
    print("测试2: holding_period_backtest vs SimpleBacktester (bars=10)")
    print("-" * 50)
    r2 = test_holding_period_consistency(strategy, market_contexts, timestamps, prices, holding_bars=10)
    _print_result(r2)
    if r2["status"] == "FAIL":
        all_passed = False
    print()

    # 测试3: 跨模式可解释性
    print("测试3: single_bar vs holding_period 差异可解释性")
    print("-" * 50)
    r3 = test_cross_mode_explainability(strategy, market_contexts, timestamps, prices)
    _print_result(r3)
    if r3["status"] == "FAIL":
        all_passed = False
    print()

    # 测试4: walk_forward vs simple_backtest 端到端
    print("测试4: walk_forward vs simple_backtest (holding_bars=10)")
    print("-" * 50)
    r4 = test_walkforward_vs_simplebacktest(strategy, market_contexts, timestamps, prices, holding_bars=10)
    _print_result(r4)
    if r4["status"] == "FAIL":
        all_passed = False
    print()

    # 测试5: 并行 vs 串行
    print("测试5: parallel vs sequential walk_forward")
    print("-" * 50)
    r5 = test_parallel_vs_sequential(strategy, market_contexts, timestamps, prices, holding_bars=1)
    _print_result(r5)
    if r5["status"] == "FAIL":
        all_passed = False
    print()

    # 总结
    print("=" * 60)
    if all_passed:
        print("PASS: 所有测试通过 - 研究工具回测逻辑一致")
    else:
        print("FAIL: 部分测试未通过 - 需要排查差异原因")
    print("=" * 60)

    return all_passed


def _print_result(result: Dict[str, Any]):
    status = result["status"]
    icon = "v" if status == "PASS" else ("!" if status == "SKIP" else "x")
    print(f"  状态: [{icon}] {status}")

    if status == "SKIP":
        print(f"  原因: {result.get('reason', 'unknown')}")
        return

    if "direct" in result and "walk_forward" in result:
        print(f"  直接调用: trades={result['direct']['trades']}, "
              f"avg_ret={_fmt_pct(result['direct']['avg_return'])}, "
              f"pnl={_fmt_pct(result['direct']['total_pnl'])}, "
              f"wr={result['direct']['win_rate']:.4f}")
        print(f"  WalkForward: trades={result['walk_forward']['trades']}, "
              f"avg_ret={_fmt_pct(result['walk_forward']['avg_return'])}, "
              f"pnl={_fmt_pct(result['walk_forward']['total_return'])}, "
              f"wr={result['walk_forward']['win_rate']:.4f}")
        print(f"  差异: avg_ret={result['diff']['avg_return']:.6f}, "
              f"pnl={result['diff']['total_pnl']:.6f}, "
              f"wr={result['diff']['win_rate']:.6f}")

    if "engine" in result and "backtester" in result:
        print(f"  统一引擎: trades={result['engine']['trades']}, "
              f"avg_ret={_fmt_pct(result['engine']['avg_return'])}, "
              f"wr={result['engine']['win_rate']:.4f}, "
              f"pf={result['engine']['profit_factor']:.4f}")
        print(f"  Backtester: trades={result['backtester']['trades']}, "
              f"avg_ret={_fmt_pct(result['backtester']['avg_return'])}, "
              f"wr={result['backtester']['win_rate']:.4f}, "
              f"pf={result['backtester']['profit_factor']:.4f}")
        print(f"  差异: trades={result['diff']['trades']}, "
              f"avg_ret={result['diff']['avg_return']:.6f}, "
              f"wr={result['diff']['win_rate']:.6f}, "
              f"pf={result['diff']['profit_factor']:.6f}")

    if "single_bar" in result and "holding_period" in result:
        print(f"  SingleBar: trades={result['single_bar']['trades']}, "
              f"avg_ret={_fmt_pct(result['single_bar']['avg_return'])}, "
              f"wr={result['single_bar']['win_rate']:.4f}")
        print(f"  HoldingPeriod: trades={result['holding_period']['trades']}, "
              f"avg_ret={_fmt_pct(result['holding_period']['avg_return'])}, "
              f"wr={result['holding_period']['win_rate']:.4f}")
        print(f"  可解释性: trades_ratio={result['explainability']['trades_ratio']:.2f}, "
              f"single>=holding={result['explainability']['single_ge_holding']}")

    if "walk_forward" in result and "simple_backtest" in result:
        print(f"  WalkForward: trades={result['walk_forward']['trades']}, "
              f"avg_ret={_fmt_pct(result['walk_forward']['avg_return'])}, "
              f"total_ret={_fmt_pct(result['walk_forward']['total_return'])}, "
              f"wr={result['walk_forward']['win_rate']:.4f}")
        print(f"  SimpleBT:    trades={result['simple_backtest']['trades']}, "
              f"avg_ret={_fmt_pct(result['simple_backtest']['avg_return'])}, "
              f"total_ret={_fmt_pct(result['simple_backtest']['total_return'])}, "
              f"wr={result['simple_backtest']['win_rate']:.4f}")
        print(f"  差异: avg_ret={result['diff']['avg_return']:.6f}, "
              f"total_ret={result['diff']['total_return']:.6f}, "
              f"wr={result['diff']['win_rate']:.6f}")

    if "sequential" in result and "parallel" in result:
        print(f"  串行: windows={result['sequential']['windows']}, "
              f"avg_ret={_fmt_pct(result['sequential']['avg_return'])}, "
              f"hit_rate={result['sequential']['avg_hit_rate']:.4f}")
        print(f"  并行: windows={result['parallel']['windows']}, "
              f"avg_ret={_fmt_pct(result['parallel']['avg_return'])}, "
              f"hit_rate={result['parallel']['avg_hit_rate']:.4f}")
        d = result["diff"]
        print(f"  差异: windows_match={d['windows_match']}, "
              f"avg_ret={d['avg_return']:.8f}, "
              f"hit_rate={d['avg_hit_rate']:.8f}, "
              f"all_windows_match={d['all_windows_match']}")


def main():
    parser = argparse.ArgumentParser(description="研究工具一致性验证")
    parser.add_argument("--strategy", type=str, required=True, choices=StrategyName.ALL)
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--source", type=str, default="mock", choices=["mock", "parquet"])

    args = parser.parse_args()
    success = run_all_tests(args.strategy, args.symbol, args.days, args.source)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
