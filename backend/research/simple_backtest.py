"""
Simple Backtest - 简单回测工具

核心：验证交易规则能否盈利

规则：
- signal long  -> 开多
- signal short -> 开空
- 持有 N 根 bar 或反向 signal 平仓
- 扣手续费和滑点

核心指标：
- win_rate: 胜率
- avg_trade_return: 平均每笔收益
- max_drawdown: 最大回撤
- profit_factor: 盈利因子
- sharpe: 夏普比率
- trade_count: 交易次数

验证的是策略本身的 edge，不是参数调优。
"""

import sys
from pathlib import Path
from typing import List, Any, Tuple
import pandas as pd
import numpy as np
import argparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engines.compute.strategy_v2 import StrategyV2, SignalType

try:
    from research.common.loaders import get_strategy_class, save_results_to_json
    from research.common.types import StrategyName
    from research.common.backtest_engine import run_holding_period_backtest, SingleSignalResult, BacktestMetrics
    from research.common.mock import generate_test_contexts
except ImportError:
    from common.loaders import get_strategy_class, save_results_to_json
    from common.types import StrategyName
    from common.backtest_engine import run_holding_period_backtest, SingleSignalResult, BacktestMetrics
    from common.mock import generate_test_contexts


class SimpleBacktester:
    """
    简单回测器

    核心职责：
    1. 模拟交易执行（不考虑仓位管理）
    2. 计算交易级别的指标
    3. 扣费用和滑点
    """

    def __init__(
        self,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
        slippage_bps: float = 2.0,
        max_holding_bars: int = 10
    ):
        """
        Args:
            maker_fee: Maker 手续费率
            taker_fee: Taker 手续费率
            slippage_bps: 滑点（基点）
            max_holding_bars: 最大持仓 bar 数
        """
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage_bps = slippage_bps
        self.max_holding_bars = max_holding_bars

    def backtest(
        self,
        strategy: StrategyV2,
        market_contexts: List[Any],
        timestamps: List[int],
        prices: np.ndarray
    ) -> Tuple[List[SingleSignalResult], BacktestMetrics]:
        """
        执行回测（使用统一回测引擎）

        Args:
            strategy: 策略实例
            market_contexts: MarketContext 列表
            timestamps: 时间戳列表
            prices: 价格序列

        Returns:
            (信号结果列表, 回测指标)
        """
        if len(market_contexts) != len(timestamps) or len(timestamps) != len(prices):
            raise ValueError("数据长度不一致")

        return run_holding_period_backtest(
            strategy,
            market_contexts,
            timestamps,
            prices,
            maker_fee=self.maker_fee,
            taker_fee=self.taker_fee,
            slippage_bps=self.slippage_bps,
            max_holding_bars=self.max_holding_bars
        )

    def get_trades_df(self, trades: List[SingleSignalResult]) -> pd.DataFrame:
        """获取交易记录 DataFrame"""
        if not trades:
            return pd.DataFrame()

        data = [{
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "holding_bars": t.holding_bars,
            "confidence": t.confidence,
            "reason": t.reason,
        } for t in trades]

        return pd.DataFrame(data)


def run_simple_backtest(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage_bps: float = 2.0,
    max_holding_bars: int = 10
) -> Tuple[List[SingleSignalResult], BacktestMetrics]:
    """
    运行简单回测

    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        maker_fee: Maker 手续费率
        taker_fee: Taker 手续费率
        slippage_bps: 滑点（基点）
        max_holding_bars: 最大持仓 bar 数

    Returns:
        (信号结果列表, 回测指标)
    """
    backtester = SimpleBacktester(
        maker_fee=maker_fee,
        taker_fee=taker_fee,
        slippage_bps=slippage_bps,
        max_holding_bars=max_holding_bars
    )

    return backtester.backtest(strategy, market_contexts, timestamps, prices)


def compare_strategy_backtests(
    strategies: List[StrategyV2],
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray
) -> pd.DataFrame:
    """
    比较多个策略的回测结果

    Args:
        strategies: 策略列表
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列

    Returns:
        pd.DataFrame: 比较结果
    """
    results = []

    for strategy in strategies:
        try:
            trades, metrics = run_simple_backtest(strategy, market_contexts, timestamps, prices)
            avg_holding = np.mean([t.holding_bars for t in trades]) if trades else 0
            results.append({
                "strategy": strategy.meta.name,
                "symbol": strategy.symbol,
                "total_trades": metrics.total_trades,
                "long_trades": metrics.long_trades,
                "short_trades": metrics.short_trades,
                "win_rate": metrics.win_rate,
                "avg_trade_return": metrics.avg_trade_return,
                "median_trade_return": metrics.median_trade_return,
                "total_pnl": metrics.total_pnl_pct,
                "max_drawdown": metrics.max_drawdown,
                "sharpe_ratio": metrics.sharpe_ratio,
                "profit_factor": metrics.profit_factor,
                "avg_holding_bars": avg_holding,
            })
        except Exception as e:
            results.append({
                "strategy": strategy.meta.name,
                "symbol": strategy.symbol,
                "error": str(e)
            })

    return pd.DataFrame(results)


__all__ = [
    "SimpleBacktester",
    "run_simple_backtest",
    "compare_strategy_backtests",
]


# ==================== CLI 命令行接口 ====================

def main():
    """CLI 入口函数"""
    parser = argparse.ArgumentParser(description="Simple Backtest Tool - 简单回测工具")

    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=StrategyName.ALL,
        help=f"策略名称: {', '.join(StrategyName.ALL)}"
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="交易对 (默认: BTCUSDT)"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="测试天数 (默认: 30)"
    )

    parser.add_argument(
        "--taker-fee",
        type=float,
        default=0.0005,
        help="Taker 手续费率 (默认: 0.0005)"
    )

    parser.add_argument(
        "--maker-fee",
        type=float,
        default=0.0002,
        help="Maker 手续费率 (默认: 0.0002)"
    )

    parser.add_argument(
        "--slippage",
        type=float,
        default=2.0,
        help="滑点 (基点, 默认: 2.0)"
    )

    parser.add_argument(
        "--max-holding-bars", "--holding-bars",
        type=int,
        default=10,
        dest="max_holding_bars",
        help="最大持仓 bar 数 (默认: 10)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径"
    )

    parser.add_argument(
        "--source",
        type=str,
        default="mock",
        choices=["mock", "datalake", "parquet"],
        help="数据源: mock(模拟), datalake(数据湖), parquet(本地parquet文件)"
    )

    args = parser.parse_args()

    print(f"简单回测: {args.strategy} | {args.symbol} | {args.days}天")
    print(f"手续费: Taker {args.taker_fee*100:.2f}%, Maker {args.maker_fee*100:.2f}%")
    print(f"滑点: {args.slippage} bps, 最大持仓: {args.max_holding_bars} bars")
    print("="*50)

    strategy_class = get_strategy_class(args.strategy)
    if not strategy_class:
        print(f"错误: 未知策略 {args.strategy}")
        sys.exit(1)

    if args.source == "parquet":
        from research.common.loaders import load_from_parquet
        market_contexts, timestamps, prices = load_from_parquet(args.symbol, args.days)
        if not market_contexts:
            samples_per_day = 96
            num_samples = args.days * samples_per_day
            print(f"parquet 无数据，回退到 mock 生成 {num_samples} 个样本...")
            market_contexts, timestamps, prices = generate_test_contexts(num_samples)
        else:
            print(f"从 parquet 加载 {len(market_contexts)} 个样本")
    elif args.source == "datalake":
        samples_per_day = 96
        num_samples = args.days * samples_per_day
        print(f"生成 {num_samples} 个样本...")
        market_contexts, timestamps, prices = generate_test_contexts(num_samples)
    else:
        samples_per_day = 96
        num_samples = args.days * samples_per_day
        print(f"生成 {num_samples} 个样本...")
        market_contexts, timestamps, prices = generate_test_contexts(num_samples)

    strategy = strategy_class(args.symbol)
    trades, metrics = run_simple_backtest(
        strategy,
        market_contexts,
        timestamps,
        prices,
        maker_fee=args.maker_fee,
        taker_fee=args.taker_fee,
        slippage_bps=args.slippage,
        max_holding_bars=args.max_holding_bars
    )

    print(f"""BacktestResult ({args.strategy}):
  交易总数: {metrics.total_trades} (多:{metrics.long_trades}, 空:{metrics.short_trades})
  胜率: {metrics.win_rate:.2%}
  平均收益: {metrics.avg_trade_return:.4f} ({metrics.avg_trade_return * 100:.2f}%)
  总盈亏: {metrics.total_pnl_pct:.2f} ({metrics.total_pnl_pct * 100:.2f}%)
  最大回撤: {metrics.max_drawdown:.4f}
  Sharpe: {metrics.sharpe_ratio:.2f}
  盈利因子: {metrics.profit_factor:.2f}
""")

    print("\n验收检查:")
    checks = [
        ("交易数 > 0", metrics.total_trades > 0),
        ("胜率 > 50%", metrics.win_rate > 0.5),
        ("盈利因子 > 1", metrics.profit_factor > 1),
        ("夏普比率 > 0", metrics.sharpe_ratio > 0),
    ]

    all_pass = True
    for check, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n✓ 所有检查通过")
    else:
        print("\n✗ 部分检查未通过")

    if args.output:
        result_dict = {
            "strategy": args.strategy,
            "symbol": args.symbol,
            "days": args.days,
            "taker_fee": args.taker_fee,
            "maker_fee": args.maker_fee,
            "slippage": args.slippage,
            "max_holding_bars": args.max_holding_bars,
            "total_trades": metrics.total_trades,
            "long_trades": metrics.long_trades,
            "short_trades": metrics.short_trades,
            "win_rate": metrics.win_rate,
            "avg_trade_return": metrics.avg_trade_return,
            "total_pnl": metrics.total_pnl_pct,
            "max_drawdown": metrics.max_drawdown,
            "sharpe_ratio": metrics.sharpe_ratio,
            "profit_factor": metrics.profit_factor,
        }
        save_results_to_json(result_dict, args.output)


if __name__ == "__main__":
    main()
