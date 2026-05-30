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
  python p0_funding_ic.py
  python p0_funding_ic.py --symbols BTCUSDT,ETCUSDT
  python p0_funding_ic.py --days 180
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SYMBOLS = ["BTCUSDT", "ETCUSDT", "ZECUSDT", "SOLUSDT"]
EXCHANGE = "binance"
TIMEFRAME = "1h"
DAYS = 365
FEATURE_SOURCE = "engine_standalone"
TREND_THRESHOLD = 0.01

OUTPUT_DIR = BACKEND_ROOT / "reports" / "funding_ic"


@dataclass
class ICRow:
    symbol: str
    feature: str
    label: str
    horizon: int
    ic: float
    rank_ic: float
    p_value: float
    rank_p_value: float
    sample_count: int
    regime: str = "unconditional"
    regime_col: str = "all"


def _compute_single_ic(
    feature_vals: np.ndarray,
    label_vals: np.ndarray,
) -> Dict:
    """计算单对 feature-label 的 IC 统计。"""
    mask = ~(np.isnan(feature_vals) | np.isnan(label_vals))
    f = feature_vals[mask]
    l = label_vals[mask]
    n = len(f)

    if n < 30:
        return {
            "ic": np.nan, "rank_ic": np.nan,
            "p_value": np.nan, "rank_p_value": np.nan,
            "sample_count": n,
        }

    ic, p_val = stats.pearsonr(f, l)
    rank_ic, rank_p = stats.spearmanr(f, l)

    return {
        "ic": ic,
        "rank_ic": rank_ic,
        "p_value": p_val,
        "rank_p_value": rank_p,
        "sample_count": n,
    }


def _compute_regimes(fm: pd.DataFrame) -> pd.DataFrame:
    df = fm.copy()

    if "trend_20" in df.columns:
        trend = df["trend_20"].fillna(0)
        df["trend_regime"] = np.where(
            trend > TREND_THRESHOLD, "trend_up",
            np.where(trend < -TREND_THRESHOLD, "trend_down", "range")
        )
    else:
        df["trend_regime"] = "range"

    if "vol_20" in df.columns and "vol_60" in df.columns:
        vol_short = df["vol_20"].fillna(0)
        vol_long = df["vol_60"].fillna(0)
        df["vol_regime"] = np.where(
            vol_short > vol_long * 1.2, "high_vol",
            np.where(vol_short < vol_long * 0.8, "low_vol", "normal")
        )
    else:
        df["vol_regime"] = "normal"

    if "funding_zscore" in df.columns:
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
    else:
        df["funding_regime"] = "neutral"

    return df


def _compute_labels(fm: pd.DataFrame) -> pd.DataFrame:
    if "close" not in fm.columns:
        return pd.DataFrame()

    close = fm["close"].values.astype(float)
    labels = pd.DataFrame(index=fm.index)

    for horizon in [1, 3, 5, 10]:
        shift = horizon
        fut_ret = (close[shift:] - close[:-shift]) / close[:-shift]
        pad = np.full(shift, np.nan)
        labels[f"future_ret_{horizon}"] = np.concatenate([fut_ret, pad])

    return labels


def _run_single_symbol(symbol: str, days: int) -> Optional[List[ICRow]]:
    print(f"\n  Loading {symbol}...")
    try:
        from research.alpha.features.matrix_adapter import get_research_feature_matrix
        fm = get_research_feature_matrix(
            symbol=symbol,
            exchange=EXCHANGE,
            days=days,
            timeframe=TIMEFRAME,
            feature_source=FEATURE_SOURCE,
        )
    except Exception as e:
        print(f"  {symbol}: Failed to load feature matrix - {e}")
        return None

    if "funding_zscore" not in fm.columns and "funding_rate" not in fm.columns:
        print(f"  {symbol}: No funding features available")
        return None

    fm = _compute_regimes(fm)
    labels = _compute_labels(fm)

    if labels.empty:
        print(f"  {symbol}: Could not compute labels")
        return None

    features = []
    if "funding_zscore" in fm.columns:
        features.append("funding_zscore")
    if "funding_rate" in fm.columns:
        features.append("funding_rate")

    print(f"  {symbol}: {len(fm)} bars, features={features}")

    rows = []

    for feat in features:
        for horizon in [1, 3, 5, 10]:
            label_col = f"future_ret_{horizon}"
            if label_col not in labels.columns:
                continue

            feat_vals = fm[feat].values.astype(float)
            label_vals = labels[label_col].values.astype(float)

            res = _compute_single_ic(feat_vals, label_vals)
            rows.append(ICRow(
                symbol=symbol,
                feature=feat,
                label=label_col,
                horizon=horizon,
                ic=res["ic"],
                rank_ic=res["rank_ic"],
                p_value=res["p_value"],
                rank_p_value=res["rank_p_value"],
                sample_count=res["sample_count"],
                regime="unconditional",
                regime_col="all",
            ))

            for regime_col in ["trend_regime", "vol_regime", "funding_regime"]:
                if regime_col not in fm.columns:
                    continue
                regimes = fm[regime_col].unique()
                for reg in regimes:
                    mask = fm[regime_col] == reg
                    feat_reg = feat_vals[mask]
                    label_reg = label_vals[mask]
                    res_reg = _compute_single_ic(feat_reg, label_reg)
                    rows.append(ICRow(
                        symbol=symbol,
                        feature=feat,
                        label=label_col,
                        horizon=horizon,
                        ic=res_reg["ic"],
                        rank_ic=res_reg["rank_ic"],
                        p_value=res_reg["p_value"],
                        rank_p_value=res_reg["rank_p_value"],
                        sample_count=res_reg["sample_count"],
                        regime=reg,
                        regime_col=regime_col,
                    ))

    return rows


def _format_report(all_rows: List[ICRow]) -> str:
    lines = []
    lines.append("=" * 90)
    lines.append("Funding Conditional IC Analysis")
    lines.append("=" * 90)

    symbols = sorted(list({r.symbol for r in all_rows}))

    lines.append(f"\nUNCONDITIONAL IC:")
    lines.append("-" * 80)
    lines.append(f"  {'symbol':<10} {'feature':<15} {'horizon':>6} {'ic':>8} {'rank_ic':>8} {'p':>10} {'n':>7}")
    lines.append(f"  {'-' * 75}")

    for sym in symbols:
        sym_rows = [r for r in all_rows if r.symbol == sym and r.regime == "unconditional"]
        for r in sym_rows:
            ic_str = f"{r.ic:.4f}" if not np.isnan(r.ic) else "nan"
            ric_str = f"{r.rank_ic:.4f}" if not np.isnan(r.rank_ic) else "nan"
            p_str = f"{r.p_value:.4f}" if not np.isnan(r.p_value) else "nan"
            sig = " **" if not np.isnan(r.p_value) and r.p_value < 0.01 else " *" if not np.isnan(r.p_value) and r.p_value < 0.05 else ""
            lines.append(f"  {sym:<10} {r.feature:<15} {r.horizon:>6} {ic_str:>8} {ric_str:>8} {p_str:>10} {r.sample_count:>7}{sig}")

    for regime_col in ["trend_regime", "vol_regime", "funding_regime"]:
        lines.append(f"\nCONDITIONAL IC BY {regime_col.upper()}:")
        lines.append("-" * 80)
        lines.append(f"  {'symbol':<10} {'feature':<15} {'regime':<20} {'horizon':>6} {'ic':>8} {'rank_ic':>8} {'p':>10} {'n':>7}")
        lines.append(f"  {'-' * 85}")

        for sym in symbols:
            sym_rows = [r for r in all_rows if r.symbol == sym and r.regime_col == regime_col and r.regime != "unconditional" and r.horizon == 5]
            for r in sorted(sym_rows, key=lambda x: abs(x.ic) if not np.isnan(x.ic) else -1, reverse=True):
                ic_str = f"{r.ic:.4f}" if not np.isnan(r.ic) else "nan"
                ric_str = f"{r.rank_ic:.4f}" if not np.isnan(r.rank_ic) else "nan"
                p_str = f"{r.p_value:.4f}" if not np.isnan(r.p_value) else "nan"
                sig = " **" if not np.isnan(r.p_value) and r.p_value < 0.01 else " *" if not np.isnan(r.p_value) and r.p_value < 0.05 else ""
                lines.append(f"  {sym:<10} {r.feature:<15} {r.regime:<20} {r.horizon:>6} {ic_str:>8} {ric_str:>8} {p_str:>10} {r.sample_count:>7}{sig}")

    lines.append(f"\nCROSS-SYMBOL COMPARISON (horizon=5):")
    lines.append("-" * 80)
    lines.append(f"  {'symbol':<10} {'trend_up':>12} {'trend_down':>12} {'range':>12} {'high_vol':>12} {'extreme_neg':>15}")
    lines.append(f"  {'-' * 75}")

    for sym in symbols:
        regime_ics = {}
        for r in all_rows:
            if r.symbol == sym and r.feature == "funding_zscore" and r.horizon == 5 and r.regime != "unconditional":
                regime_ics[r.regime] = r.ic if not np.isnan(r.ic) else np.nan

        def _fmt(x):
            return f"{x:.4f}" if not np.isnan(x) else "nan"

        lines.append(f"  {sym:<10} {_fmt(regime_ics.get('trend_up', np.nan)):>12} {_fmt(regime_ics.get('trend_down', np.nan)):>12} {_fmt(regime_ics.get('range', np.nan)):>12} {_fmt(regime_ics.get('high_vol', np.nan)):>12} {_fmt(regime_ics.get('extreme_negative', np.nan)):>15}")

    lines.append("")
    lines.append("=" * 90)
    return "\n".join(lines)


def _save_csv(all_rows: List[ICRow], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    dicts = []
    for r in all_rows:
        dicts.append({
            "symbol": r.symbol,
            "feature": r.feature,
            "label": r.label,
            "horizon": r.horizon,
            "ic": r.ic,
            "rank_ic": r.rank_ic,
            "p_value": r.p_value,
            "rank_p_value": r.rank_p_value,
            "sample_count": r.sample_count,
            "regime": r.regime,
            "regime_col": r.regime_col,
        })

    pd.DataFrame(dicts).to_csv(output_dir / "funding_conditional_ic.csv", index=False)
    print(f"\nCSV saved to {output_dir / 'funding_conditional_ic.csv'}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Funding Conditional IC Analysis")
    parser.add_argument("--symbols", type=str, default=None)
    parser.add_argument("--days", type=int, default=DAYS)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else SYMBOLS

    print("=" * 90)
    print("Funding Conditional IC Analysis")
    print(f"Symbols: {symbols}")
    print(f"Timeframe: {TIMEFRAME}, Days: {args.days}")
    print("=" * 90)

    all_rows = []
    for symbol in symbols:
        try:
            rows = _run_single_symbol(symbol, args.days)
            if rows:
                all_rows.extend(rows)
        except Exception as e:
            print(f"  {symbol}: ERROR - {e}")
            import traceback
            traceback.print_exc()

    if not all_rows:
        print("No results computed.")
        return

    report = _format_report(all_rows)
    print(report)

    _save_csv(all_rows, OUTPUT_DIR)


if __name__ == "__main__":
    main()
