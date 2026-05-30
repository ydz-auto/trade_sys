"""
Stability Heatmap Computation

对指定 symbol 画 threshold x holding_bars 的 Sharpe/PF heatmap，
重点找连续稳定盈利区域，不是找最高点。

核心函数：
  run_heatmap()         计算完整 heatmap 数据
  find_stable_regions() 从 heatmap 数据中找稳定区域
  print_ascii_heatmap() 终端 ASCII 可视化
"""

from typing import Dict, List

import numpy as np
import pandas as pd

from infrastructure.logging import get_logger

logger = get_logger("research.stability.heatmap")

THRESHOLD_PERCENTILES = [90, 93, 95, 97, 98, 99, 99.5]
HOLDING_BARS_RANGE = list(range(10, 41, 2))


def compute_signal_sharpe(
    close,
    feature_vals,
    regime_labels,
    threshold,
    holding_bars,
    direction="long",
    taker_fee=0.0004,
):
    from research.alpha.signals.alpha_signal_strategy import run_signal_test
    return run_signal_test(
        close, feature_vals, regime_labels,
        feature_threshold=threshold,
        holding_bars=holding_bars,
        direction=direction,
        taker_fee=taker_fee,
    )


def run_heatmap(
    symbol: str,
    fm: pd.DataFrame,
    feature_name: str = "drawdown_from_high",
    threshold_percentiles: List[float] = None,
    holding_bars_range: List[int] = None,
    direction: str = "long",
    taker_fee: float = 0.0004,
) -> pd.DataFrame:
    if threshold_percentiles is None:
        threshold_percentiles = THRESHOLD_PERCENTILES
    if holding_bars_range is None:
        holding_bars_range = HOLDING_BARS_RANGE

    close = fm["close"].values.astype(float)
    feature_vals = fm[feature_name].values.astype(float)
    regime_labels = fm["trend_regime"].values if "trend_regime" in fm.columns else np.array(["unknown"] * len(fm))

    thresholds = np.percentile(np.abs(feature_vals[~np.isnan(feature_vals)]), threshold_percentiles)
    thresholds = np.round(thresholds, 6)

    results = []

    for i, thresh in enumerate(thresholds):
        for hb in holding_bars_range:
            try:
                result = compute_signal_sharpe(close, feature_vals, regime_labels, thresh, hb, direction, taker_fee)
                sharpe = result.get("sharpe", 0.0)
                pf = result.get("profit_factor", 0.0)
                trades = result.get("trades", 0)
                win_rate = result.get("win_rate", 0.0)
                avg_ret = result.get("avg_ret", 0.0)

                if np.isnan(sharpe):
                    sharpe = 0.0
                if np.isnan(pf):
                    pf = 0.0

                results.append({
                    "threshold_pct": threshold_percentiles[i],
                    "threshold": thresh,
                    "holding_bars": hb,
                    "sharpe": round(sharpe, 3),
                    "profit_factor": round(pf, 3),
                    "trades": trades,
                    "win_rate": round(win_rate, 3),
                    "avg_ret": round(avg_ret, 6),
                })
            except Exception as e:
                logger.warning(f"Heatmap failed for {symbol} thresh={thresh} hb={hb}: {e}")
                results.append({
                    "threshold_pct": threshold_percentiles[i],
                    "threshold": thresh,
                    "holding_bars": hb,
                    "sharpe": 0.0,
                    "profit_factor": 0.0,
                    "trades": 0,
                    "win_rate": 0.0,
                    "avg_ret": 0.0,
                    "error": str(e),
                })

    return pd.DataFrame(results)


def find_stable_regions(df: pd.DataFrame, min_sharpe: float = 1.0) -> List[Dict]:
    stable = df[df["sharpe"] >= min_sharpe].copy()
    if stable.empty:
        return []

    regions = []
    thresh_groups = stable.groupby("threshold_pct")
    for pct, group in thresh_groups:
        hb_min = group["holding_bars"].min()
        hb_max = group["holding_bars"].max()
        regions.append({
            "threshold_pct": pct,
            "threshold": group["threshold"].iloc[0],
            "holding_bars_range": f"{hb_min}-{hb_max}",
            "num_stable_points": len(group),
            "mean_sharpe": round(group["sharpe"].mean(), 3),
            "min_sharpe": round(group["sharpe"].min(), 3),
            "mean_pf": round(group["profit_factor"].mean(), 3),
        })

    return sorted(regions, key=lambda x: x["mean_sharpe"], reverse=True)


def print_ascii_heatmap(df: pd.DataFrame, symbol: str):
    pivot = df.pivot_table(index="threshold_pct", columns="holding_bars", values="sharpe")

    print(f"\n  {symbol} - Sharpe Heatmap (threshold_pct x holding_bars)")
    print(f"  {'Pct':>4}", end="")
    for hb in pivot.columns:
        print(f" {hb:>6}", end="")
    print()
    print(f"  {'----':>4}", end="")
    for _ in pivot.columns:
        print(f" {'------':>6}", end="")
    print()

    for pct in pivot.index:
        print(f"  {pct:>4}", end="")
        for hb in pivot.columns:
            val = pivot.loc[pct, hb]
            if pd.isna(val) or val == 0:
                print(f" {'  .':>6}", end="")
            elif val >= 5:
                print(f" {'H'+str(int(val)):>6}", end="")
            elif val >= 2:
                print(f" {'M'+str(int(val)):>6}", end="")
            elif val >= 1:
                print(f" {'L'+str(round(val,1)):>6}", end="")
            elif val > 0:
                print(f" {'+'+str(round(val,1)):>6}", end="")
            else:
                print(f" {round(val,1):>6}", end="")
        print()

    print(f"\n  Legend: H=High(>=5), M=Med(>=2), L=Low(>=1), +=Marginal, .=Zero/NA")
