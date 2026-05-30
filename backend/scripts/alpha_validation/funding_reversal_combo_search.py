"""
Funding + Reversal Combo Search

P1: 系统化搜索 funding + reversal 的最优组合。

核心问题：
  1. funding_zscore 单独能产生 Alpha 吗？
  2. funding + ret_5 的组合比 ret_5 单独更强吗？
  3. funding + drawdown 的组合比 drawdown 单独更强吗？
  4. 最优的 funding combo 是什么？

搜索空间：
  primary_features:  [funding_zscore, drawdown_from_high, ret_5]
  confirm_features:  [ret_1, ret_3, ret_5, ret_10, volume_zscore, volatility_zscore,
                      trend_20, drawdown_from_high, funding_zscore]
  directions:        [long, short]
  percentiles:       [85, 90, 95]
  holding_bars:      [5, 10, 20]

用法：
  python funding_reversal_combo_search.py
  python funding_reversal_combo_search.py --symbols BTCUSDT,ETCUSDT
"""

import sys
import time
from pathlib import Path
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.signals.funding_regime_signal import run_signal_test
from research.alpha.regime_analysis import classify_regime
from infrastructure.logging import get_logger

logger = get_logger("research.alpha.funding_reversal_combo")

SYMBOLS = ["BTCUSDT", "ETCUSDT", "ZECUSDT", "SOLUSDT"]
EXCHANGE = "binance"
TIMEFRAME = "1h"
DAYS = 365
FEATURE_SOURCE = "engine_standalone"
TAKER_FEE = 0.0004

PRIMARY_FEATURES = ["funding_zscore", "drawdown_from_high", "ret_5"]
CONFIRM_FEATURES = [
    "ret_1", "ret_3", "ret_5", "ret_10",
    "volume_zscore", "volatility_zscore",
    "trend_20", "drawdown_from_high", "funding_zscore",
]
PERCENTILES = [85, 90, 95]
HOLDING_BARS_LIST = [5, 10, 20]
DIRECTIONS = ["long", "short"]

OUTPUT_DIR = BACKEND_ROOT / "reports" / "funding_combo"


def _compute_threshold(fm: pd.DataFrame, feature: str, direction: str, percentile: float) -> float:
    valid = fm[feature].dropna()
    if len(valid) == 0:
        return 0.0
    if direction == "short":
        return float(valid.quantile(percentile / 100))
    else:
        return float(valid.quantile((100 - percentile) / 100))


def _run_single_combo(
    close: np.ndarray,
    fm: pd.DataFrame,
    primary_feature: str,
    confirm_features: List[str],
    direction: str,
    percentile: float,
    holding_bars: int,
    taker_fee: float,
) -> Optional[Dict]:
    primary_thresh = _compute_threshold(fm, primary_feature, direction, percentile)
    primary_vals = fm[primary_feature].values.astype(float)

    if direction == "short":
        primary_mask = primary_vals > primary_thresh
    else:
        primary_mask = primary_vals < -primary_thresh

    feat_valid = ~np.isnan(primary_vals)
    signal_mask = primary_mask & feat_valid

    for cf in confirm_features:
        if cf == primary_feature:
            continue
        if cf not in fm.columns:
            return None
        cf_vals = fm[cf].values.astype(float)
        cf_thresh = _compute_threshold(fm, cf, direction, percentile)
        cf_valid = ~np.isnan(cf_vals)
        if direction == "short":
            cf_mask = cf_vals > cf_thresh
        else:
            cf_mask = cf_vals < -cf_thresh
        signal_mask = signal_mask & cf_valid & cf_mask

    regime_labels = fm.get("trend_regime", pd.Series(["unknown"] * len(fm))).values

    result = run_signal_test(
        close=close,
        feature_vals=signal_mask.astype(float),
        regime_labels=regime_labels,
        feature_threshold=0.5,
        holding_bars=holding_bars,
        direction="long",
        taker_fee=taker_fee,
    )

    combo_name = primary_feature
    if confirm_features:
        cf_str = "+".join(cf for cf in confirm_features if cf != primary_feature)
        if cf_str:
            combo_name = f"{primary_feature}+{cf_str}"

    return {
        "combo": combo_name,
        "primary": primary_feature,
        "confirms": ",".join(cf for cf in confirm_features if cf != primary_feature),
        "direction": direction,
        "percentile": percentile,
        "holding_bars": holding_bars,
        "trades": result["trades"],
        "win_rate": result["win_rate"],
        "avg_ret": result["avg_ret"],
        "sharpe": result["sharpe"],
        "profit_factor": result["profit_factor"],
    }


def _run_symbol(symbol: str, days: int) -> pd.DataFrame:
    print(f"\n  Loading {symbol}...")
    from research.alpha.features.matrix_adapter import get_research_feature_matrix

    fm = get_research_feature_matrix(
        symbol=symbol,
        exchange=EXCHANGE,
        days=days,
        timeframe=TIMEFRAME,
        feature_source=FEATURE_SOURCE,
    )
    fm = classify_regime(fm)
    close = fm["close"].values.astype(float)

    available_primary = [f for f in PRIMARY_FEATURES if f in fm.columns]
    available_confirm = [f for f in CONFIRM_FEATURES if f in fm.columns]

    if not available_primary:
        print(f"  {symbol}: No primary features available")
        return pd.DataFrame()

    print(f"  {symbol}: {len(fm)} bars, primary={available_primary}, confirm={available_confirm}")

    rows = []

    for primary in available_primary:
        for direction in DIRECTIONS:
            for percentile in PERCENTILES:
                for hb in HOLDING_BARS_LIST:
                    result = _run_single_combo(
                        close, fm, primary, [], direction, percentile, hb, TAKER_FEE
                    )
                    if result and result["trades"] >= 10:
                        rows.append(result)

                    for cf in available_confirm:
                        if cf == primary:
                            continue
                        result = _run_single_combo(
                            close, fm, primary, [cf], direction, percentile, hb, TAKER_FEE
                        )
                        if result and result["trades"] >= 10:
                            rows.append(result)

                    for c1, c2 in combinations(available_confirm, 2):
                        if primary in (c1, c2):
                            continue
                        result = _run_single_combo(
                            close, fm, primary, [c1, c2], direction, percentile, hb, TAKER_FEE
                        )
                        if result and result["trades"] >= 10:
                            rows.append(result)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["symbol"] = symbol
    return df


def _format_report(all_dfs: Dict[str, pd.DataFrame]) -> str:
    lines = []
    lines.append("=" * 90)
    lines.append("Funding + Reversal Combo Search")
    lines.append("=" * 90)

    for symbol, df in all_dfs.items():
        if df.empty:
            continue
        lines.append(f"\n  {symbol} - Top 10 by Sharpe:")
        lines.append(f"  {'combo':<35} {'dir':>5} {'pct':>4} {'hb':>3} {'trades':>7} {'wr':>6} {'sharpe':>8} {'pf':>6}")
        lines.append(f"  {'-' * 80}")

        top = df.nlargest(10, "sharpe")
        for _, row in top.iterrows():
            wr_str = f"{row['win_rate']:.3f}" if not np.isnan(row['win_rate']) else "nan"
            sh_str = f"{row['sharpe']:.2f}" if not np.isnan(row['sharpe']) else "nan"
            pf_str = f"{row['profit_factor']:.2f}" if not np.isnan(row['profit_factor']) and not np.isinf(row['profit_factor']) else "inf"
            lines.append(f"  {row['combo']:<35} {row['direction']:>5} {row['percentile']:>4} {row['holding_bars']:>3} {row['trades']:>7} {wr_str:>6} {sh_str:>8} {pf_str:>6}")

    combined = pd.concat(all_dfs.values(), ignore_index=True) if all_dfs else pd.DataFrame()
    if combined.empty:
        return "\n".join(lines)

    lines.append(f"\n  CROSS-SYMBOL: Top 20 by Sharpe (trades >= 30):")
    lines.append(f"  {'symbol':<10} {'combo':<30} {'dir':>5} {'pct':>4} {'hb':>3} {'trades':>7} {'wr':>6} {'sharpe':>8} {'pf':>6}")
    lines.append(f"  {'-' * 85}")

    viable = combined[combined["trades"] >= 30].nlargest(20, "sharpe")
    for _, row in viable.iterrows():
        wr_str = f"{row['win_rate']:.3f}" if not np.isnan(row['win_rate']) else "nan"
        sh_str = f"{row['sharpe']:.2f}" if not np.isnan(row['sharpe']) else "nan"
        pf_str = f"{row['profit_factor']:.2f}" if not np.isnan(row['profit_factor']) and not np.isinf(row['profit_factor']) else "inf"
        lines.append(f"  {row['symbol']:<10} {row['combo']:<30} {row['direction']:>5} {row['percentile']:>4} {row['holding_bars']:>3} {row['trades']:>7} {wr_str:>6} {sh_str:>8} {pf_str:>6}")

    lines.append(f"\n  COMBO vs SINGLE FEATURE:")
    lines.append(f"  {'-' * 60}")

    for primary in PRIMARY_FEATURES:
        single = combined[(combined["primary"] == primary) & (combined["confirms"] == "")]
        combo = combined[(combined["primary"] == primary) & (combined["confirms"] != "")]

        if single.empty:
            continue

        best_single_sharpe = single["sharpe"].max()
        best_combo_sharpe = combo["sharpe"].max() if not combo.empty else np.nan

        improvement = ""
        if not np.isnan(best_combo_sharpe) and best_single_sharpe > 0:
            pct = (best_combo_sharpe - best_single_sharpe) / abs(best_single_sharpe) * 100
            improvement = f" ({pct:+.0f}%)"

        lines.append(f"  {primary}: single_best={best_single_sharpe:.2f}, combo_best={best_combo_sharpe:.2f}{improvement}")

    lines.append("")
    lines.append("=" * 90)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Funding + Reversal Combo Search")
    parser.add_argument("--symbols", type=str, default=None)
    parser.add_argument("--days", type=int, default=DAYS)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else SYMBOLS

    print("=" * 90)
    print("Funding + Reversal Combo Search")
    print(f"Symbols: {symbols}")
    print(f"Primary features: {PRIMARY_FEATURES}")
    print(f"Confirm features: {CONFIRM_FEATURES}")
    print(f"Percentiles: {PERCENTILES}")
    print(f"Holding bars: {HOLDING_BARS_LIST}")
    print("=" * 90)

    all_dfs = {}
    for symbol in symbols:
        try:
            t0 = time.time()
            df = _run_symbol(symbol, args.days)
            elapsed = time.time() - t0
            if not df.empty:
                all_dfs[symbol] = df
                print(f"  {symbol}: {len(df)} combos in {elapsed:.1f}s")
        except Exception as e:
            print(f"  {symbol}: ERROR - {e}")
            import traceback
            traceback.print_exc()

    if not all_dfs:
        print("No results computed.")
        return

    report = _format_report(all_dfs)
    print(report)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(all_dfs.values(), ignore_index=True)
    combined.to_csv(OUTPUT_DIR / "funding_reversal_combo_search.csv", index=False)
    print(f"\nCSV saved to {OUTPUT_DIR / 'funding_reversal_combo_search.csv'}")


if __name__ == "__main__":
    main()
