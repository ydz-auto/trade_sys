"""
Crowding Alpha Factory

系统化生成所有 crowding 相关的 Alpha 变体。

核心思想：
  crowding = "太多人站在同一边"
  度量方式：
    1. funding 极端 → 多头拥挤
    2. OI 高位 + funding 极端 → 杠杆拥挤
    3. OI 激增 + 价格反转 → 挤压前兆
    4. leverage_crowdedness 综合指标

Factory 模式：
  输入 feature matrix
  输出 所有 crowding 变体的回测结果

用法：
  python crowding_alpha_factory.py
  python crowding_alpha_factory.py --symbols BTCUSDT,ETCUSDT
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

from research.alpha.signals.funding_regime_signal import run_signal_test
from research.alpha.regime_analysis import classify_regime
from infrastructure.logging import get_logger

logger = get_logger("research.alpha.crowding_factory")

SYMBOLS = ["BTCUSDT", "ETCUSDT", "ZECUSDT", "SOLUSDT"]
EXCHANGE = "binance"
TIMEFRAME = "1h"
DAYS = 365
FEATURE_SOURCE = "engine_standalone"
TAKER_FEE = 0.0004

CROWDING_FEATURES = [
    "funding_zscore",
    "oi_zscore",
    "oi_change",
    "leverage_crowdedness",
    "oi_funding_divergence",
]

PERCENTILES = [85, 90, 95, 99]
HOLDING_BARS_LIST = [5, 10, 20]
DIRECTIONS = ["long", "short"]

OUTPUT_DIR = BACKEND_ROOT / "reports" / "crowding_alpha"


def _compute_threshold(fm: pd.DataFrame, feature: str, direction: str, percentile: float) -> float:
    valid = fm[feature].dropna()
    if len(valid) == 0:
        return 0.0
    if direction == "short":
        return float(valid.quantile(percentile / 100))
    else:
        return float(valid.quantile((100 - percentile) / 100))


def _build_crowding_variants(fm: pd.DataFrame, close: np.ndarray) -> pd.DataFrame:
    available = [f for f in CROWDING_FEATURES if f in fm.columns]

    if not available:
        return pd.DataFrame()

    regime_labels = fm.get("trend_regime", pd.Series(["unknown"] * len(fm))).values

    rows = []

    for feature in available:
        for direction in DIRECTIONS:
            for percentile in PERCENTILES:
                for hb in HOLDING_BARS_LIST:
                    threshold = _compute_threshold(fm, feature, direction, percentile)
                    feature_vals = fm[feature].values.astype(float)

                    result = run_signal_test(
                        close=close,
                        feature_vals=feature_vals,
                        regime_labels=regime_labels,
                        feature_threshold=threshold,
                        holding_bars=hb,
                        direction=direction,
                        taker_fee=TAKER_FEE,
                    )

                    rows.append({
                        "feature": feature,
                        "direction": direction,
                        "percentile": percentile,
                        "holding_bars": hb,
                        "trades": result["trades"],
                        "win_rate": result["win_rate"],
                        "avg_ret": result["avg_ret"],
                        "sharpe": result["sharpe"],
                        "profit_factor": result["profit_factor"],
                        "variant_type": "single",
                    })

    combo_definitions = []

    if "funding_zscore" in available and "oi_zscore" in available:
        combo_definitions.append({
            "name": "funding_oi_crowding",
            "features": ["funding_zscore", "oi_zscore"],
            "direction": "short",
            "logic": "both_extreme_positive",
        })
        combo_definitions.append({
            "name": "oi_squeeze_long",
            "features": ["oi_zscore", "funding_zscore"],
            "direction": "long",
            "logic": "oi_high_funding_low",
        })

    if "funding_zscore" in available and "oi_change" in available:
        combo_definitions.append({
            "name": "funding_oi_surge",
            "features": ["funding_zscore", "oi_change"],
            "direction": "short",
            "logic": "both_extreme_positive",
        })

    if "leverage_crowdedness" in available:
        combo_definitions.append({
            "name": "leverage_crowded_short",
            "features": ["leverage_crowdedness"],
            "direction": "short",
            "logic": "extreme_positive",
        })

    if "oi_funding_divergence" in available:
        combo_definitions.append({
            "name": "divergence_long",
            "features": ["oi_funding_divergence"],
            "direction": "long",
            "logic": "extreme_negative",
        })

    for combo in combo_definitions:
        for percentile in PERCENTILES:
            for hb in HOLDING_BARS_LIST:
                combo_signal = _compute_combo_signal(fm, combo, percentile)
                if combo_signal is None:
                    continue

                result = run_signal_test(
                    close=close,
                    feature_vals=combo_signal,
                    regime_labels=regime_labels,
                    feature_threshold=0.5,
                    holding_bars=hb,
                    direction=combo["direction"],
                    taker_fee=TAKER_FEE,
                )

                rows.append({
                    "feature": combo["name"],
                    "direction": combo["direction"],
                    "percentile": percentile,
                    "holding_bars": hb,
                    "trades": result["trades"],
                    "win_rate": result["win_rate"],
                    "avg_ret": result["avg_ret"],
                    "sharpe": result["sharpe"],
                    "profit_factor": result["profit_factor"],
                    "variant_type": "combo",
                })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _compute_combo_signal(
    fm: pd.DataFrame,
    combo: Dict,
    percentile: float,
) -> Optional[np.ndarray]:
    logic = combo["logic"]
    features = combo["features"]
    direction = combo["direction"]

    if logic == "both_extreme_positive":
        mask = pd.Series(True, index=fm.index)
        for feat in features:
            if feat not in fm.columns:
                return None
            thresh = _compute_threshold(fm, feat, "short", percentile)
            mask &= (fm[feat] > thresh) & (~fm[feat].isna())
        return mask.astype(float).values

    elif logic == "oi_high_funding_low":
        if "oi_zscore" not in fm.columns or "funding_zscore" not in fm.columns:
            return None
        oi_thresh = _compute_threshold(fm, "oi_zscore", "short", percentile)
        fund_thresh = _compute_threshold(fm, "funding_zscore", "long", percentile)
        mask = (fm["oi_zscore"] > oi_thresh) & (fm["funding_zscore"] < fund_thresh)
        mask &= (~fm["oi_zscore"].isna()) & (~fm["funding_zscore"].isna())
        return mask.astype(float).values

    elif logic == "extreme_positive":
        feat = features[0]
        if feat not in fm.columns:
            return None
        thresh = _compute_threshold(fm, feat, "short", percentile)
        mask = (fm[feat] > thresh) & (~fm[feat].isna())
        return mask.astype(float).values

    elif logic == "extreme_negative":
        feat = features[0]
        if feat not in fm.columns:
            return None
        thresh = _compute_threshold(fm, feat, "long", percentile)
        mask = (fm[feat] < thresh) & (~fm[feat].isna())
        return mask.astype(float).values

    return None


def _run_symbol(symbol: str, days: int) -> Optional[pd.DataFrame]:
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

    available = [f for f in CROWDING_FEATURES if f in fm.columns]
    print(f"  {symbol}: {len(fm)} bars, crowding features={available}")

    if not available:
        print(f"  {symbol}: No crowding features available, skipping")
        return None

    df = _build_crowding_variants(fm, close)
    if df.empty:
        return None

    df["symbol"] = symbol
    return df


def _format_report(all_dfs: Dict[str, pd.DataFrame]) -> str:
    lines = []
    lines.append("=" * 90)
    lines.append("Crowding Alpha Factory")
    lines.append("=" * 90)

    for symbol, df in all_dfs.items():
        if df.empty:
            continue

        viable = df[(df["trades"] >= 15) & (df["win_rate"] > 0.50) & (df["avg_ret"] > 0)]
        lines.append(f"\n  {symbol}: {len(df)} variants, {len(viable)} viable")

        top = df.nlargest(10, "sharpe")
        lines.append(f"\n  Top 10 by Sharpe:")
        lines.append(f"  {'feature':<25} {'type':>6} {'dir':>5} {'pct':>4} {'hb':>3} {'trades':>7} {'wr':>6} {'sharpe':>8} {'pf':>6}")
        lines.append(f"  {'-' * 75}")

        for _, row in top.iterrows():
            wr_str = f"{row['win_rate']:.3f}" if not np.isnan(row['win_rate']) else "nan"
            sh_str = f"{row['sharpe']:.2f}" if not np.isnan(row['sharpe']) else "nan"
            pf_str = f"{row['profit_factor']:.2f}" if not np.isnan(row['profit_factor']) and not np.isinf(row['profit_factor']) else "inf"
            lines.append(f"  {row['feature']:<25} {row['variant_type']:>6} {row['direction']:>5} {row['percentile']:>4} {row['holding_bars']:>3} {row['trades']:>7} {wr_str:>6} {sh_str:>8} {pf_str:>6}")

    combined = pd.concat(all_dfs.values(), ignore_index=True) if all_dfs else pd.DataFrame()
    if combined.empty:
        return "\n".join(lines)

    lines.append(f"\n  CROSS-SYMBOL: Top 20 by Sharpe (trades >= 15):")
    lines.append(f"  {'symbol':<10} {'feature':<25} {'type':>6} {'dir':>5} {'pct':>4} {'hb':>3} {'trades':>7} {'sharpe':>8}")
    lines.append(f"  {'-' * 80}")

    viable = combined[(combined["trades"] >= 15)].nlargest(20, "sharpe")
    for _, row in viable.iterrows():
        sh_str = f"{row['sharpe']:.2f}" if not np.isnan(row['sharpe']) else "nan"
        lines.append(f"  {row['symbol']:<10} {row['feature']:<25} {row['variant_type']:>6} {row['direction']:>5} {row['percentile']:>4} {row['holding_bars']:>3} {row['trades']:>7} {sh_str:>8}")

    lines.append(f"\n  FEATURE COMPARISON:")
    lines.append(f"  {'-' * 60}")

    for feature in CROWDING_FEATURES + ["funding_oi_crowding", "oi_squeeze_long", "leverage_crowded_short", "divergence_long"]:
        feat_df = combined[combined["feature"] == feature]
        if feat_df.empty:
            continue
        viable_feat = feat_df[(feat_df["trades"] >= 15) & (feat_df["win_rate"] > 0.50)]
        best_sharpe = feat_df["sharpe"].max()
        viable_count = len(viable_feat)
        total_count = len(feat_df)
        symbols_with_alpha = viable_feat["symbol"].nunique() if not viable_feat.empty else 0
        lines.append(f"  {feature:<25} best_sharpe={best_sharpe:>6.2f}  viable={viable_count}/{total_count}  symbols={symbols_with_alpha}")

    lines.append("")
    lines.append("=" * 90)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crowding Alpha Factory")
    parser.add_argument("--symbols", type=str, default=None)
    parser.add_argument("--days", type=int, default=DAYS)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else SYMBOLS

    print("=" * 90)
    print("Crowding Alpha Factory")
    print(f"Symbols: {symbols}")
    print(f"Crowding features: {CROWDING_FEATURES}")
    print(f"Percentiles: {PERCENTILES}")
    print(f"Holding bars: {HOLDING_BARS_LIST}")
    print("=" * 90)

    all_dfs = {}
    for symbol in symbols:
        try:
            t0 = time.time()
            df = _run_symbol(symbol, args.days)
            elapsed = time.time() - t0
            if df is not None and not df.empty:
                all_dfs[symbol] = df
                print(f"  {symbol}: {len(df)} variants in {elapsed:.1f}s")
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
    combined.to_csv(OUTPUT_DIR / "crowding_alpha_factory.csv", index=False)
    print(f"\nCSV saved to {OUTPUT_DIR / 'crowding_alpha_factory.csv'}")


if __name__ == "__main__":
    main()
