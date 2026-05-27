"""
Signal Rule Validator - 通用信号规则验证

验证任意 IC 发现是否能转化为简单交易规则。

信号规则:
  条件: regime in target_regimes AND feature > percentile_threshold (SHORT)
                                  OR feature < -percentile_threshold (LONG)
  动作: SHORT / LONG

支持任意 feature 列 (funding_zscore, ret_1, ret_5, trend_20 等)。
阈值基于 feature 在目标 regime 内的百分位自动计算。

CLI:
  python -m research.alpha.funding_regime_signal \
    --symbol BTCUSDT --days 90 \
    --feature ret_5 --regimes all \
    --percentiles 75,85,90,95 \
    --holding-bars 1,3,5,10 \
    --directions short,long
"""

import sys
import argparse
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------- 核心回测逻辑 ----------

def run_signal_test(
    close: np.ndarray,
    feature_vals: np.ndarray,
    regime_labels: np.ndarray,
    feature_threshold: float,
    holding_bars: int,
    direction: str = "short",
    target_regimes: List[str] = None,
    taker_fee: float = 0.0005,
) -> dict:
    """
    对单组 (threshold, holding_bars, direction) 运行信号规则验证。

    short: feature > threshold → 做空 (高值预期下跌)
    long:  feature < -threshold → 做多 (低值预期上涨)
    """
    n = len(close)
    max_exit = n - holding_bars

    # Regime 过滤
    if target_regimes:
        regime_mask = np.isin(regime_labels, target_regimes)
    else:
        regime_mask = np.ones(n, dtype=bool)

    feat_valid = ~np.isnan(feature_vals)

    if direction == "short":
        signal_mask = regime_mask & feat_valid & (feature_vals > feature_threshold)
    else:
        signal_mask = regime_mask & feat_valid & (feature_vals < -feature_threshold)

    valid_idx = np.where(signal_mask[:max_exit])[0]

    if len(valid_idx) == 0:
        return {
            "trades": 0, "win_rate": np.nan, "avg_ret": np.nan,
            "total_ret": np.nan, "sharpe": np.nan, "profit_factor": np.nan,
        }

    entry_prices = close[valid_idx]
    exit_prices = close[valid_idx + holding_bars]

    if direction == "short":
        raw_ret = -(exit_prices - entry_prices) / entry_prices
    else:
        raw_ret = (exit_prices - entry_prices) / entry_prices

    fee = 2.0 * taker_fee
    rets = raw_ret - fee

    trades = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]

    win_rate = len(wins) / trades
    avg_ret = np.mean(rets)
    total_ret = np.sum(rets)

    std_ret = np.std(rets, ddof=1) if trades > 1 else 0.0
    sharpe = avg_ret / std_ret * np.sqrt(trades) if std_ret > 0 else 0.0

    sum_win = np.sum(wins) if len(wins) > 0 else 0.0
    sum_loss = abs(np.sum(losses)) if len(losses) > 0 else 0.0
    profit_factor = sum_win / sum_loss if sum_loss > 0 else np.inf if sum_win > 0 else np.nan

    return {
        "trades": trades,
        "win_rate": win_rate,
        "avg_ret": avg_ret,
        "total_ret": total_ret,
        "sharpe": sharpe,
        "profit_factor": profit_factor,
    }


def run_signal_matrix(
    fm: pd.DataFrame,
    close: np.ndarray,
    feature_name: str,
    feature_thresholds: List[float],
    holding_bars_list: List[int],
    directions: List[str] = None,
    target_regimes: List[str] = None,
    taker_fee: float = 0.0005,
) -> pd.DataFrame:
    """运行 directions x threshold x holding_bars 的完整信号矩阵。"""
    if directions is None:
        directions = ["short"]

    feature_vals = fm[feature_name].values.astype(float)
    regime_labels = fm["trend_regime"].values

    rows = []
    for direction in directions:
        for thresh in feature_thresholds:
            for hb in holding_bars_list:
                result = run_signal_test(
                    close, feature_vals, regime_labels,
                    feature_threshold=thresh,
                    holding_bars=hb,
                    direction=direction,
                    target_regimes=target_regimes,
                    taker_fee=taker_fee,
                )
                result["direction"] = direction
                result["threshold"] = thresh
                result["holding_bars"] = hb
                rows.append(result)

    df = pd.DataFrame(rows)
    cols = ["direction", "threshold", "holding_bars", "trades", "win_rate",
            "avg_ret", "total_ret", "sharpe", "profit_factor"]
    return df[[c for c in cols if c in df.columns]]


# ---------- 打印 ----------

def print_signal_matrix(result_df: pd.DataFrame, symbol: str, days: int,
                        feature_name: str, regimes_str: str):
    """格式化打印信号矩阵。"""
    print(f"\nSignal Test Matrix: {symbol} | {days}d | feature={feature_name} | regimes={regimes_str}")
    print(f"{'='*105}")
    print(f"{'direction':>10} {'threshold':>12} {'hold_bars':>10} {'trades':>8} "
          f"{'win_rate':>9} {'avg_ret':>10} {'total_ret':>10} {'sharpe':>9} {'pf':>12}")
    print(f"{'-'*103}")

    for _, row in result_df.iterrows():
        wr = f"{row['win_rate']:.3f}" if not np.isnan(row['win_rate']) else "nan"
        ar = f"{row['avg_ret']:.5f}" if not np.isnan(row['avg_ret']) else "nan"
        tr = f"{row['total_ret']:.4f}" if not np.isnan(row['total_ret']) else "nan"
        sh = f"{row['sharpe']:.3f}" if not np.isnan(row['sharpe']) else "nan"
        pf = f"{row['profit_factor']:.3f}" if (not np.isnan(row['profit_factor'])
                                                and not np.isinf(row['profit_factor'])) else "inf"
        direction = row.get('direction', 'short')

        print(f"{direction:>10} {row['threshold']:>12.5f} {int(row['holding_bars']):>10} "
              f"{int(row['trades']):>8} {wr:>9} {ar:>10} {tr:>10} {sh:>9} {pf:>12}")

    print(f"{'='*105}")


def print_signal_diagnostics(fm: pd.DataFrame, feature_name: str,
                             target_regimes: List[str], percentiles: List[int]):
    """打印信号分布诊断。"""
    if feature_name not in fm.columns:
        print(f"  WARNING: {feature_name} not in feature matrix!")
        return

    feat = fm[feature_name].dropna()

    # Regime 过滤
    if target_regimes:
        regime_mask = fm["trend_regime"].isin(target_regimes)
    else:
        regime_mask = pd.Series(True, index=fm.index)

    feat_regime = fm.loc[regime_mask, feature_name].dropna()
    regime_str = ",".join(target_regimes) if target_regimes else "all"

    print(f"\nSignal Diagnostics:")
    print(f"  Total bars: {len(fm)}")
    print(f"  Target regime bars: {regime_mask.sum()}")
    print(f"  {feature_name} valid (total): {len(feat)}")
    print(f"  {feature_name} valid (target regime): {len(feat_regime)}")

    if len(feat_regime) > 0:
        print(f"\n  {feature_name} in {regime_str}:")
        print(f"    min={feat_regime.min():.6f}  max={feat_regime.max():.6f}")
        print(f"    mean={feat_regime.mean():.6f}  std={feat_regime.std():.6f}")
        for p in [5, 10, 25, 50, 75, 90, 95]:
            print(f"    p{p}={feat_regime.quantile(p/100):.6f}")

    # 基于百分位的阈值
    if len(feat_regime) > 0:
        print(f"\n  Percentile-based thresholds:")
        for p in percentiles:
            val = feat_regime.quantile(p / 100)
            neg_val = feat_regime.quantile((100 - p) / 100)
            hi_count = (feat_regime > val).sum()
            lo_count = (feat_regime < neg_val).sum()
            print(f"    p{p}: threshold={val:.6f} "
                  f"SHORT(>{val:.6f})={hi_count}  "
                  f"LONG(<{neg_val:.6f})={lo_count}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description="Signal Rule Validator - 通用信号规则验证")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--timeframe", type=str, default="1m")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--trend-threshold", type=float, default=0.001,
                        help="趋势判定阈值")
    parser.add_argument("--feature", type=str, default="funding_zscore",
                        help="因子列名 (默认: funding_zscore)")
    parser.add_argument("--regimes", type=str, default="trend_down",
                        help="目标 regime (逗号分隔, 或 'all', 默认: trend_down)")
    parser.add_argument("--percentiles", type=str, default="75,85,90,95",
                        help="百分位阈值列表 (逗号分隔, 默认: 75,85,90,95)")
    parser.add_argument("--holding-bars", type=str, default="1,3,5,10",
                        help="持仓 bar 数列表 (逗号分隔)")
    parser.add_argument("--taker-fee", type=float, default=0.0005,
                        help="单边手续费 (默认: 0.0005)")
    parser.add_argument("--directions", type=str, default="short,long",
                        help="方向列表: short,long (逗号分隔, 默认 short,long)")
    parser.add_argument("--symbols", type=str, default=None,
                        help="多标的验证 (逗号分隔, 如 BTCUSDT,ETCUSDT,SOLUSDT)")

    args = parser.parse_args()

    percentiles = [int(x) for x in args.percentiles.split(",")]
    holding_bars_list = [int(x) for x in args.holding_bars.split(",")]
    directions = [x.strip() for x in args.directions.split(",")]

    # 多标的 or 单标的
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        symbols = [args.symbol]

    if args.regimes.strip().lower() == "all":
        target_regimes = None
        regimes_str = "all"
    else:
        target_regimes = [x.strip() for x in args.regimes.split(",")]
        regimes_str = ",".join(target_regimes)

    print(f"Signal Rule Validator | {args.exchange} | {args.days}d")
    print(f"  symbols={symbols}")
    print(f"  timeframe={args.timeframe}")
    print(f"  feature={args.feature}")
    print(f"  regimes={regimes_str}")
    print(f"  percentiles={percentiles}")
    print(f"  holding_bars={holding_bars_list}")
    print(f"  directions={directions}")
    print(f"  taker_fee={args.taker_fee}")
    print("=" * 60)

    from research.alpha.feature_matrix import build_feature_matrix
    from research.alpha.regime_analysis import classify_regime

    all_results = []

    for sym in symbols:
        print(f"\n{'#'*60}")
        print(f"# Symbol: {sym}")
        print(f"{'#'*60}")

        # 1. 构建 feature matrix
        print(f"\nLoading feature matrix for {sym}...")
        try:
            fm = build_feature_matrix(
                symbol=sym,
                exchange=args.exchange,
                days=args.days,
                timeframe=args.timeframe,
            )
        except Exception as e:
            print(f"  ERROR loading {sym}: {e}")
            continue
        print(f"  {len(fm)} bars, {len(fm.columns)} columns")

        if args.feature not in fm.columns:
            print(f"  ERROR: feature '{args.feature}' not found. Available: {list(fm.columns)}")
            continue

        # 2. Regime 分类
        print("Classifying regimes...")
        fm = classify_regime(fm, trend_threshold=args.trend_threshold)

        # 3. 诊断 + 计算百分位阈值
        print_signal_diagnostics(fm, args.feature, target_regimes, percentiles)

        if target_regimes:
            regime_mask = fm["trend_regime"].isin(target_regimes)
        else:
            regime_mask = pd.Series(True, index=fm.index)
        feat_regime = fm.loc[regime_mask, args.feature].dropna()

        if len(feat_regime) == 0:
            print(f"  WARNING: no valid feature data for {sym}, skipping")
            continue

        feature_thresholds = []
        for p in percentiles:
            val = feat_regime.quantile(p / 100)
            feature_thresholds.append(round(val, 8))

        print(f"\n  Computed thresholds: {feature_thresholds}")

        # 4. 信号矩阵
        close = fm["close"].values.astype(float)
        result_df = run_signal_matrix(
            fm, close,
            feature_name=args.feature,
            feature_thresholds=feature_thresholds,
            holding_bars_list=holding_bars_list,
            directions=directions,
            target_regimes=target_regimes,
            taker_fee=args.taker_fee,
        )
        result_df["symbol"] = sym
        print_signal_matrix(result_df, sym, args.days, args.feature, regimes_str)

        # 5. 单标的总结
        viable = result_df[
            (result_df["trades"] >= 30)
            & (result_df["win_rate"] > 0.50)
            & (result_df["avg_ret"] > 0)
        ]
        print(f"\n{'='*60}")
        if len(viable) > 0:
            print(f"PASS [{sym}]: {len(viable)}/{len(result_df)} combinations are viable")
            for _, row in viable.iterrows():
                print(f"  {row.get('direction', 'short'):>5} "
                      f"thresh={row['threshold']:.5f} hold={int(row['holding_bars'])} "
                      f"trades={int(row['trades'])} wr={row['win_rate']:.3f} "
                      f"avg={row['avg_ret']:.5f} sharpe={row['sharpe']:.3f} "
                      f"pf={row['profit_factor']:.3f}")
        else:
            print(f"FAIL [{sym}]: No viable combinations found")
        print(f"{'='*60}")

        all_results.append(result_df)

    # 6. 跨标的汇总
    if len(all_results) > 0:
        combined = pd.concat(all_results, ignore_index=True)
        _print_cross_symbol_summary(combined, symbols)


def _print_cross_symbol_summary(combined: pd.DataFrame, symbols: list):
    """跨标的对比汇总。"""
    viable = combined[
        (combined["trades"] >= 30)
        & (combined["win_rate"] > 0.50)
        & (combined["avg_ret"] > 0)
    ].copy()

    print(f"\n{'='*70}")
    print(f"CROSS-SYMBOL SUMMARY ({len(symbols)} symbols)")
    print(f"{'='*70}")

    # 每个 symbol 的最佳组合
    print(f"\nBest combination per symbol:")
    print(f"{'symbol':>12} {'dir':>6} {'thresh':>10} {'hold':>5} {'trades':>7} "
          f"{'win_rate':>9} {'avg_ret':>10} {'sharpe':>8} {'pf':>8}")
    print(f"{'-'*75}")

    for sym in symbols:
        sym_df = combined[combined["symbol"] == sym]
        if len(sym_df) == 0:
            print(f"{sym:>12} {'(no data)':>6}")
            continue
        best = sym_df.loc[sym_df["avg_ret"].idxmax()]
        if np.isnan(best["avg_ret"]):
            print(f"{sym:>12} {'(nan)':>6}")
            continue
        print(f"{sym:>12} {best['direction']:>6} {best['threshold']:>10.5f} "
              f"{int(best['holding_bars']):>5} {int(best['trades']):>7} "
              f"{best['win_rate']:>9.3f} {best['avg_ret']:>10.5f} "
              f"{best['sharpe']:>8.3f} {best['profit_factor']:>8.3f}")

    # 全局 viable 列表
    if len(viable) > 0:
        viable = viable.sort_values("avg_ret", ascending=False)
        print(f"\nAll viable combinations ({len(viable)} total):")
        print(f"{'symbol':>12} {'dir':>6} {'thresh':>10} {'hold':>5} {'trades':>7} "
              f"{'avg_ret':>10} {'sharpe':>8} {'pf':>8}")
        print(f"{'-'*66}")
        for _, row in viable.iterrows():
            print(f"{row['symbol']:>12} {row['direction']:>6} {row['threshold']:>10.5f} "
                  f"{int(row['holding_bars']):>5} {int(row['trades']):>7} "
                  f"{row['avg_ret']:>10.5f} {row['sharpe']:>8.3f} "
                  f"{row['profit_factor']:>8.3f}")

        # 统计
        viable_symbols = viable["symbol"].unique()
        print(f"\n  Viable symbols: {list(viable_symbols)} ({len(viable_symbols)}/{len(symbols)})")
        if len(viable_symbols) >= 2:
            print(f"  >>> MULTI-SYMBOL ALPHA CONFIRMED <<<")
        else:
            print(f"  >>> SINGLE-SYMBOL ONLY - POSSIBLE OVERFIT <<<")
    else:
        print(f"\nNo viable combinations across any symbol.")

    print(f"{'='*70}")


if __name__ == "__main__":
    main()
