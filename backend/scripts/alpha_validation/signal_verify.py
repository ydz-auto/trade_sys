"""
Signal Logic Verification

验证 run_signal_test 和 heatmap 脚本是否用同一套信号逻辑。

测试点：
  BTCUSDT, threshold=0.076, holding_bars=20
  ETCUSDT, threshold=0.113, holding_bars=20

对比：
  1. pipeline 的 _stage_signal_profitability 结果
  2. 直接调用 run_signal_test 结果
  3. heatmap 脚本的结果

如果三者不一致，说明信号生成逻辑有分歧。
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_matrix(symbol):
    from engines.compute.feature.feature_engine import FeatureEngine
    engine = FeatureEngine(source="engine_standalone")
    return engine.build_historical_matrix(
        symbol=symbol, exchange="binance", days=365, timeframe="1h",
    )


def test_signal_direct(symbol, threshold, holding_bars=20, direction="long"):
    from research.alpha.signals.alpha_signal_strategy import run_signal_test

    fm = build_matrix(symbol)
    close = fm["close"].values.astype(float)
    feature_vals = fm["drawdown_from_high"].values.astype(float)
    regime_labels = fm["trend_regime"].values if "trend_regime" in fm.columns else np.array(["unknown"] * len(fm))

    print(f"\n  {symbol}: threshold={threshold}, holding_bars={holding_bars}, direction={direction}")
    print(f"  Feature stats: min={np.nanmin(feature_vals):.6f}, max={np.nanmax(feature_vals):.6f}, "
          f"mean={np.nanmean(feature_vals):.6f}, std={np.nanstd(feature_vals):.6f}")

    abs_vals = np.abs(feature_vals[~np.isnan(feature_vals)])
    for pct in [80, 85, 90, 92, 95, 97, 99]:
        pval = np.percentile(abs_vals, pct)
        print(f"  |feature| P{pct} = {pval:.6f}")

    result = run_signal_test(
        close, feature_vals, regime_labels,
        feature_threshold=threshold,
        holding_bars=holding_bars,
        direction=direction,
        taker_fee=0.0004,
    )

    print(f"\n  run_signal_test result:")
    print(f"    trades={result.get('trades')}")
    print(f"    profit_factor={result.get('profit_factor', 'N/A')}")
    print(f"    sharpe={result.get('sharpe', 'N/A')}")
    print(f"    win_rate={result.get('win_rate', 'N/A')}")
    print(f"    avg_ret={result.get('avg_ret', 'N/A')}")

    return result


def test_signal_pipeline(symbol, threshold, holding_bars=20, direction="long"):
    from research.alpha.validation.pipeline import AlphaPipeline

    pipeline = AlphaPipeline(
        symbols=[symbol],
        timeframes=["1h"],
        days=365,
        exchange="binance",
        skip_walk_forward=True,
        skip_stability=True,
        output_dir=str(Path("reports") / "signal_verify"),
        feature_source="engine_standalone",
    )

    result = pipeline.run(["drawdown_dip_buying"])

    for r in result.results:
        if r.strategy == "drawdown_dip_buying" and r.symbol == symbol:
            print(f"\n  Pipeline result for {symbol}:")
            print(f"    best_params={r.best_params}")
            print(f"    best_metrics={r.best_metrics}")

            for s in r.stages:
                if s.stage_name == "signal_profitability":
                    bp = s.data.get("best_params", {})
                    bm = s.data.get("best_metrics", {})
                    print(f"    Signal stage best_params: {bp}")
                    print(f"    Signal stage best_metrics: {bm}")

            return r

    return None


def main():
    print("=" * 70)
    print("SIGNAL LOGIC VERIFICATION")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("TEST 1: BTCUSDT threshold=0.076 holding=20")
    print("=" * 70)
    test_signal_direct("BTCUSDT", threshold=0.076, holding_bars=20)
    test_signal_pipeline("BTCUSDT", threshold=0.076, holding_bars=20)

    print("\n" + "=" * 70)
    print("TEST 2: ETCUSDT threshold=0.113 holding=20")
    print("=" * 70)
    test_signal_direct("ETCUSDT", threshold=0.113, holding_bars=20)
    test_signal_pipeline("ETCUSDT", threshold=0.113, holding_bars=20)

    print("\n" + "=" * 70)
    print("TEST 3: BTCUSDT - try various thresholds manually")
    print("=" * 70)
    for thresh in [0.05, 0.076, 0.10, 0.15, 0.20]:
        test_signal_direct("BTCUSDT", threshold=thresh, holding_bars=20)


if __name__ == "__main__":
    main()
