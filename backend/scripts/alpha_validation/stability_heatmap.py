"""
drawdown_dip_buying 2D Stability Heatmap

对 4 个 symbol 画 threshold x holding_bars 的 Sharpe/PF heatmap，
重点找连续稳定盈利区域，不是找最高点。

输出：
  - CSV: 每个 (threshold, holding_bars) 的 sharpe/pf
  - 终端 ASCII heatmap
  - 稳定区域标注

用法：
    python stability_heatmap.py
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.stability.heatmap import (
    THRESHOLD_PERCENTILES,
    HOLDING_BARS_RANGE,
    run_heatmap,
    find_stable_regions,
    print_ascii_heatmap,
)

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETCUSDT", "ZECUSDT"]
STRATEGY = "drawdown_dip_buying"
TIMEFRAME = "1h"
DAYS = 365
EXCHANGE = "binance"

OUTPUT_DIR = BACKEND_ROOT / "reports" / "alpha_production_validation" / "stability_heatmap"


def build_feature_matrix(symbol: str):
    from engines.compute.feature.feature_engine import FeatureEngine
    engine = FeatureEngine(source="engine_standalone")
    return engine.build_historical_matrix(
        symbol=symbol, exchange=EXCHANGE, days=DAYS, timeframe=TIMEFRAME,
    )


def main():
    print("=" * 80)
    print("DRAWDOWN_DIP_BUYING 2D STABILITY HEATMAP")
    print(f"Symbols: {SYMBOLS}")
    print(f"Threshold percentiles: {THRESHOLD_PERCENTILES}")
    print(f"Holding bars range: {HOLDING_BARS_RANGE[0]}-{HOLDING_BARS_RANGE[-1]}")
    print("=" * 80)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for symbol in SYMBOLS:
        print(f"\n{'=' * 80}")
        print(f"  {symbol}")
        print(f"{'=' * 80}")

        print(f"  Building feature matrix for {symbol}...")
        fm = build_feature_matrix(symbol)

        df = run_heatmap(symbol, fm)
        df.to_csv(OUTPUT_DIR / f"{symbol}_heatmap.csv", index=False)

        print_ascii_heatmap(df, symbol)

        regions = find_stable_regions(df, min_sharpe=1.0)
        print(f"\n  Stable Regions (sharpe >= 1.0):")
        if regions:
            for reg in regions:
                print(f"    P{reg['threshold_pct']}: thresh={reg['threshold']:.6f}, "
                      f"hold={reg['holding_bars_range']}, "
                      f"points={reg['num_stable_points']}, "
                      f"mean_sharpe={reg['mean_sharpe']}, "
                      f"min_sharpe={reg['min_sharpe']}, "
                      f"mean_PF={reg['mean_pf']}")
        else:
            print("    None found")

        regions_strict = find_stable_regions(df, min_sharpe=2.0)
        print(f"\n  High-Quality Regions (sharpe >= 2.0):")
        if regions_strict:
            for reg in regions_strict:
                print(f"    P{reg['threshold_pct']}: thresh={reg['threshold']:.6f}, "
                      f"hold={reg['holding_bars_range']}, "
                      f"points={reg['num_stable_points']}, "
                      f"mean_sharpe={reg['mean_sharpe']}, "
                      f"mean_PF={reg['mean_pf']}")
        else:
            print("    None found")

    print(f"\n\nHeatmaps saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
