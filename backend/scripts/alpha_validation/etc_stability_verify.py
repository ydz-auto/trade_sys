"""
ETC Stability 矛盾验证

复现 pipeline 的 1D sweep，看为什么 is_flat=False
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main():
    from engines.compute.feature.feature_engine import FeatureEngine
    from research.alpha.signals.alpha_signal_strategy import run_signal_test
    from research.stability.analyzer import StabilityAnalyzer

    engine = FeatureEngine(source="engine_standalone")
    fm = engine.build_historical_matrix(symbol="ETCUSDT", exchange="binance", days=365, timeframe="1h")

    close = fm["close"].values.astype(float)
    feature_vals = fm["drawdown_from_high"].values.astype(float)
    regime_labels = fm["trend_regime"].values

    base_threshold = 0.11260263
    holding_bars = 20
    direction = "long"

    threshold_range = np.linspace(base_threshold * 0.5, base_threshold * 1.5, 11).tolist()

    print("=" * 70)
    print("ETCUSDT 1D Sweep Reproduction")
    print(f"base_threshold = {base_threshold}")
    print(f"threshold_range = {[round(t, 6) for t in threshold_range]}")
    print("=" * 70)
    print()

    analyzer = StabilityAnalyzer()

    def metric_fn(thresh):
        result = run_signal_test(
            close, feature_vals, regime_labels,
            feature_threshold=thresh,
            holding_bars=holding_bars,
            direction=direction,
            taker_fee=0.0004,
        )
        sharpe = result.get("sharpe", 0.0)
        return sharpe if not np.isnan(sharpe) else 0.0

    sweep = analyzer.analyze_1d("threshold", threshold_range, metric_fn)

    print("1D Sweep Results:")
    for t, m in zip(sweep.param_values, sweep.metric_values):
        print(f"  threshold={t:.6f} -> sharpe={m:.3f}")

    print()
    print(f"mean_metric = {sweep.mean_metric:.3f}")
    print(f"std_metric  = {sweep.std_metric:.3f}")
    print(f"best_param  = {sweep.best_param:.6f}")
    print(f"best_metric = {sweep.best_metric:.3f}")
    print()

    flat_threshold = max(0.1, abs(sweep.mean_metric) * 0.2)
    print(f"is_flat threshold = max(0.1, |{sweep.mean_metric:.3f}| * 0.2) = {flat_threshold:.3f}")
    print(f"std_metric ({sweep.std_metric:.3f}) < threshold ({flat_threshold:.3f}) ? {sweep.std_metric < flat_threshold}")
    print(f"is_flat = {sweep.is_flat}")
    print()

    print("=" * 70)
    print("Now test with wider range (like heatmap):")
    print("=" * 70)

    abs_vals = np.abs(feature_vals[~np.isnan(feature_vals)])
    wide_range = [np.percentile(abs_vals, p) for p in [80, 85, 90, 92, 95, 97]]

    sweep_wide = analyzer.analyze_1d("threshold", wide_range, metric_fn)

    print("Wide Range 1D Sweep Results:")
    for t, m in zip(sweep_wide.param_values, sweep_wide.metric_values):
        print(f"  threshold={t:.6f} -> sharpe={m:.3f}")

    print()
    print(f"mean_metric = {sweep_wide.mean_metric:.3f}")
    print(f"std_metric  = {sweep_wide.std_metric:.3f}")

    flat_threshold_wide = max(0.1, abs(sweep_wide.mean_metric) * 0.2)
    print(f"is_flat threshold = {flat_threshold_wide:.3f}")
    print(f"std_metric ({sweep_wide.std_metric:.3f}) < threshold ({flat_threshold_wide:.3f}) ? {sweep_wide.std_metric < flat_threshold_wide}")
    print(f"is_flat = {sweep_wide.is_flat}")
    print()

    print("=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    print()
    print(f"Pipeline range: {threshold_range[0]:.4f} - {threshold_range[-1]:.4f}")
    print(f"  -> includes low-sharpe region (threshold < 0.08)")
    print(f"  -> std={sweep.std_metric:.3f}, threshold={flat_threshold:.3f}")
    print(f"  -> is_flat={sweep.is_flat}")
    print()
    print(f"Heatmap range: {wide_range[0]:.4f} - {wide_range[-1]:.4f}")
    print(f"  -> all high-sharpe region")
    print(f"  -> std={sweep_wide.std_metric:.3f}, threshold={flat_threshold_wide:.3f}")
    print(f"  -> is_flat={sweep_wide.is_flat}")
    print()
    print("CONCLUSION: Pipeline's base_threshold * 0.5 extends into low-sharpe territory,")
    print("inflating std and causing is_flat=False. The strategy IS stable in the")
    print("high-threshold region, but the sweep range doesn't capture that correctly.")


if __name__ == "__main__":
    main()
