"""
Funding Conditional IC Analysis

P0: 回答 funding_zscore 在不同 regime 下是否有预测力。

核心问题：
  1. funding_zscore 的 unconditional IC 是多少？
  2. 在 trend_regime 下，哪个 regime 的 funding IC 最强？
  3. 在 vol_regime 下，哪个 regime 的 funding IC 最强？
  4. 在 funding 自身的极端状态下，IC 是否更强？
  5. 跨 symbol 对比，funding IC 是否一致？

输出：
  1. 终端结构化报告
  2. funding_conditional_ic.csv

用法：
  python funding_conditional_ic.py
  python funding_conditional_ic.py --symbols BTCUSDT,ETCUSDT
  python funding_conditional_ic.py --days 180
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.ic.analysis import compute_ic_table, compute_conditional_ic
from research.alpha.regime_analysis import classify_regime
from infrastructure.logging import get_logger

logger = get_logger("research.alpha.funding_conditional_ic")

SYMBOLS = ["BTCUSDT", "ETCUSDT", "ZECUSDT", "SOLUSDT"]
EXCHANGE = "binance"
TIMEFRAME = "1h"
DAYS = 365
FEATURE_SOURCE = "engine_standalone"
TREND_THRESHOLD = 0.01

FUNDING_FEATURES = [
    "funding_rate",
    "funding_zscore",
]

LABELS = [
    "future_ret_1",
    "future_ret_3",
    "future_ret_5",
    "future_ret_10",
]

REGIME_COLS = ["trend_regime", "vol_regime", "funding_regime"]

OUTPUT_DIR = BACKEND_ROOT / "reports" / "funding_ic"


def _classify_funding_regime(fm: pd.DataFrame) -> pd.DataFrame:
    df = fm.copy()
    if "funding_zscore" not in df.columns:
        df["funding_regime"] = "unknown"
        return df

    fz = df["funding_zscore"]
    df["funding_regime"] = np.where(
        fz > 1.5, "extreme_positive",
        np.where(
            fz > 0.5, "positive",
            np.where(
                fz < -1.5, "extreme_negative",
                np.where(fz < -0.5, "negative", "neutral")
            )
        )
    )
    return df


def _run_single_symbol(symbol: str, days: int) -> Optional[Dict]:
    print(f"\n  Loading {symbol} feature matrix...")
    from research.alpha.features.matrix_adapter import get_research_feature_matrix
    from research.alpha.labels import compute_labels_from_df

    fm = get_research_feature_matrix(
        symbol=symbol,
        exchange=EXCHANGE,
        days=days,
        timeframe=TIMEFRAME,
        feature_source=FEATURE_SOURCE,
    )

    has_funding = any(f in fm.columns for f in FUNDING_FEATURES)
    if not has_funding:
        print(f"  {symbol}: No funding features available, skipping")
        return None

    fm = classify_regime(fm, trend_threshold=TREND_THRESHOLD)
    fm = _classify_funding_regime(fm)

    labels = compute_labels_from_df(fm)

    available_features = [f for f in FUNDING_FEATURES if f in fm.columns]
    available_labels = [l for l in LABELS if l in labels.columns]

    if not available_features or not available_labels:
        print(f"  {symbol}: No valid feature-label pairs, skipping")
        return None

    print(f"  {symbol}: {len(fm)} bars, features={available_features}, labels={available_labels}")

    ic_df = compute_ic_table(fm, labels, features=available_features, labels=available_labels)

    conditional_results = {}
    for regime_col in REGIME_COLS:
        if regime_col not in fm.columns:
            continue
        for feat in available_features:
            for lab in ["future_ret_5"]:
                if lab not in available_labels:
                    continue
                cond = compute_conditional_ic(fm, labels, feat, lab, regime_col=regime_col)
                key = f"{feat}|{lab}|{regime_col}"
                conditional_results[key] = cond

    regime_dist = {}
    for regime_col in REGIME_COLS:
        if regime_col in fm.columns:
            regime_dist[regime_col] = fm[regime_col].value_counts().to_dict()

    return {
        "symbol": symbol,
        "unconditional_ic": ic_df,
        "conditional_ic": conditional_results,
        "regime_distribution": regime_dist,
        "feature_matrix": fm,
        "labels": labels,
    }


def _format_report(all_results: Dict[str, Dict]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("Funding Conditional IC Analysis")
    lines.append("=" * 80)

    lines.append("")
    lines.append("UNCONDITIONAL IC")
    lines.append("-" * 80)
    for symbol, result in all_results.items():
        ic_df = result["unconditional_ic"]
        if ic_df.empty:
            continue
        lines.append(f"\n  {symbol}:")
        lines.append(f"  {'feature':<20} {'label':<16} {'IC':>8} {'Rank IC':>8} {'p-value':>10} {'n':>8}")
        lines.append(f"  {'-' * 70}")
        for _, row in ic_df.iterrows():
            ic_str = f"{row['ic']:.4f}" if not np.isnan(row['ic']) else "nan"
            ric_str = f"{row['rank_ic']:.4f}" if not np.isnan(row['rank_ic']) else "nan"
            p_str = f"{row['p_value']:.4f}" if not np.isnan(row['p_value']) else "nan"
            sig = " **" if not np.isnan(row.get('p_value', np.nan)) and row['p_value'] < 0.01 else \
                  " *" if not np.isnan(row.get('p_value', np.nan)) and row['p_value'] < 0.05 else ""
            lines.append(f"  {row['feature']:<20} {row['label']:<16} {ic_str:>8} {ric_str:>8} {p_str:>10} {row['sample_count']:>8}{sig}")

    lines.append("")
    lines.append("CONDITIONAL IC (funding_zscore -> future_ret_5)")
    lines.append("-" * 80)

    for symbol, result in all_results.items():
        lines.append(f"\n  {symbol}:")
        for regime_col in REGIME_COLS:
            key = f"funding_zscore|future_ret_5|{regime_col}"
            cond = result["conditional_ic"].get(key)
            if cond is None or cond.empty:
                continue
            lines.append(f"\n    By {regime_col}:")
            lines.append(f"    {'regime':<20} {'IC':>8} {'Rank IC':>8} {'p-value':>10} {'n':>8}")
            lines.append(f"    {'-' * 56}")
            for _, row in cond.iterrows():
                ic_str = f"{row['ic']:.4f}" if not np.isnan(row['ic']) else "nan"
                ric_str = f"{row['rank_ic']:.4f}" if not np.isnan(row['rank_ic']) else "nan"
                p_str = f"{row['p_value']:.4f}" if not np.isnan(row['p_value']) else "nan"
                sig = " **" if not np.isnan(row.get('p_value', np.nan)) and row['p_value'] < 0.01 else \
                      " *" if not np.isnan(row.get('p_value', np.nan)) and row['p_value'] < 0.05 else ""
                lines.append(f"    {row['regime']:<20} {ic_str:>8} {ric_str:>8} {p_str:>10} {row['sample_count']:>8}{sig}")

    lines.append("")
    lines.append("REGIME DISTRIBUTION")
    lines.append("-" * 80)
    for symbol, result in all_results.items():
        lines.append(f"\n  {symbol}:")
        for regime_col, dist in result["regime_distribution"].items():
            total = sum(dist.values())
            parts = ", ".join(f"{k}={v} ({v/total:.0%})" for k, v in sorted(dist.items()))
            lines.append(f"    {regime_col}: {parts}")

    lines.append("")
    lines.append("CROSS-SYMBOL COMPARISON")
    lines.append("-" * 80)
    lines.append(f"\n  {'symbol':<12} {'uncond IC':>10} {'trend_up':>10} {'trend_down':>10} {'range':>10} {'extreme_pos':>12} {'extreme_neg':>12}")
    lines.append(f"  {'-' * 76}")

    for symbol, result in all_results.items():
        ic_df = result["unconditional_ic"]
        fz_ic = ic_df[(ic_df["feature"] == "funding_zscore") & (ic_df["label"] == "future_ret_5")]
        uncond_ic = fz_ic["ic"].values[0] if len(fz_ic) > 0 else np.nan

        regime_ics = {}
        for regime_col in ["trend_regime", "funding_regime"]:
            key = f"funding_zscore|future_ret_5|{regime_col}"
            cond = result["conditional_ic"].get(key)
            if cond is not None and not cond.empty:
                for _, row in cond.iterrows():
                    regime_ics[f"{regime_col}_{row['regime']}"] = row['ic']

        trend_up = regime_ics.get("trend_regime_trend_up", np.nan)
        trend_down = regime_ics.get("trend_regime_trend_down", np.nan)
        range_ic = regime_ics.get("trend_regime_range", np.nan)
        ext_pos = regime_ics.get("funding_regime_extreme_positive", np.nan)
        ext_neg = regime_ics.get("funding_regime_extreme_negative", np.nan)

        def _fmt(v):
            return f"{v:.4f}" if not np.isnan(v) else "nan"

        lines.append(f"  {symbol:<12} {_fmt(uncond_ic):>10} {_fmt(trend_up):>10} {_fmt(trend_down):>10} {_fmt(range_ic):>10} {_fmt(ext_pos):>12} {_fmt(ext_neg):>12}")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def _save_csv(all_results: Dict[str, Dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for symbol, result in all_results.items():
        for key, cond in result["conditional_ic"].items():
            feat, lab, regime_col = key.split("|")
            for _, row in cond.iterrows():
                rows.append({
                    "symbol": symbol,
                    "feature": feat,
                    "label": lab,
                    "regime_col": regime_col,
                    "regime": row["regime"],
                    "ic": row["ic"],
                    "rank_ic": row["rank_ic"],
                    "p_value": row["p_value"],
                    "rank_p_value": row.get("rank_p_value", np.nan),
                    "sample_count": row["sample_count"],
                })

        ic_df = result["unconditional_ic"]
        for _, row in ic_df.iterrows():
            rows.append({
                "symbol": symbol,
                "feature": row["feature"],
                "label": row["label"],
                "regime_col": "unconditional",
                "regime": "all",
                "ic": row["ic"],
                "rank_ic": row["rank_ic"],
                "p_value": row["p_value"],
                "rank_p_value": row.get("rank_p_value", np.nan),
                "sample_count": row["sample_count"],
            })

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(output_dir / "funding_conditional_ic.csv", index=False)
        print(f"\n  CSV saved to {output_dir / 'funding_conditional_ic.csv'}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Funding Conditional IC Analysis")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    parser.add_argument("--days", type=int, default=DAYS)
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR))
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else SYMBOLS
    output_dir = Path(args.output_dir)

    print("=" * 80)
    print("Funding Conditional IC Analysis")
    print(f"Symbols: {symbols}")
    print(f"Timeframe: {TIMEFRAME}, Days: {args.days}")
    print(f"Features: {FUNDING_FEATURES}")
    print("=" * 80)

    all_results = {}
    for symbol in symbols:
        try:
            t0 = time.time()
            result = _run_single_symbol(symbol, args.days)
            elapsed = time.time() - t0
            if result:
                all_results[symbol] = result
                print(f"  {symbol}: Done in {elapsed:.1f}s")
        except Exception as e:
            print(f"  {symbol}: ERROR - {e}")
            import traceback
            traceback.print_exc()

    if not all_results:
        print("No results computed.")
        return

    report = _format_report(all_results)
    print(report)

    _save_csv(all_results, output_dir)


if __name__ == "__main__":
    main()
