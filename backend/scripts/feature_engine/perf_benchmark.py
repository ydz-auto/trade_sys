"""
Performance Benchmark: research vs engine vs engine_standalone

比较：
  - build time
  - rows/sec
  - features/sec
  - peak memory

用法：
    python perf_benchmark.py
"""

import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETCUSDT", "ZECUSDT"]
TIMEFRAME = "1h"
DAYS = 365
EXCHANGE = "binance"

OUTPUT_DIR = BACKEND_ROOT / "reports" / "feature_parity" / "perf_benchmark"

WARMUP_RUNS = 1
BENCHMARK_RUNS = 3

SOURCES = ["research", "engine", "engine_standalone"]


def benchmark_single(symbol: str, feature_source: str, days: int = DAYS) -> Dict[str, Any]:
    from engines.compute.feature.feature_engine import FeatureEngine

    engine = FeatureEngine(source=feature_source)

    times = []
    peak_memories = []
    result_shape = None
    result_cols = 0

    for i in range(WARMUP_RUNS + BENCHMARK_RUNS):
        tracemalloc.start()
        t0 = time.perf_counter()

        df = engine.build_historical_matrix(
            symbol=symbol,
            exchange=EXCHANGE,
            days=days,
            timeframe=TIMEFRAME,
        )

        t1 = time.perf_counter()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        elapsed = t1 - t0
        peak_mb = peak / (1024 * 1024)

        if i >= WARMUP_RUNS:
            times.append(elapsed)
            peak_memories.append(peak_mb)

        if result_shape is None:
            result_shape = df.shape
            result_cols = len(df.columns)

    avg_time = np.mean(times)
    min_time = np.min(times)
    max_time = np.max(times)
    avg_peak_mem = np.mean(peak_memories)
    rows = result_shape[0] if result_shape else 0

    return {
        "symbol": symbol,
        "feature_source": feature_source,
        "days": days,
        "rows": rows,
        "columns": result_cols,
        "avg_time_s": round(avg_time, 3),
        "min_time_s": round(min_time, 3),
        "max_time_s": round(max_time, 3),
        "avg_peak_mem_mb": round(avg_peak_mem, 1),
        "rows_per_sec": round(rows / avg_time, 1) if avg_time > 0 else 0,
        "features_per_sec": round(result_cols / avg_time, 1) if avg_time > 0 else 0,
    }


def main():
    print("=" * 70)
    print("PERFORMANCE BENCHMARK: research vs engine vs engine_standalone")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframe: {TIMEFRAME}, Days: {DAYS}")
    print(f"Warmup: {WARMUP_RUNS}, Benchmark runs: {BENCHMARK_RUNS}")
    print("=" * 70)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []

    for source in SOURCES:
        print(f"--- {source.upper()} SOURCE ---")
        for symbol in SYMBOLS:
            print(f"  Benchmarking {symbol} ({source})...")
            result = benchmark_single(symbol, source)
            all_results.append(result)
            print(f"    avg={result['avg_time_s']}s, "
                  f"peak_mem={result['avg_peak_mem_mb']}MB, "
                  f"rows/sec={result['rows_per_sec']}, "
                  f"features/sec={result['features_per_sec']}")
        print()

    df = pd.DataFrame(all_results)
    df.to_csv(OUTPUT_DIR / "benchmark_results.csv", index=False)

    print("=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print()

    print(f"{'Symbol':<12} {'Source':<22} {'Rows':>8} {'Cols':>6} "
          f"{'Avg(s)':>8} {'Min(s)':>8} {'PeakMB':>10} "
          f"{'Rows/s':>10} {'Feat/s':>10}")
    print("-" * 100)
    for _, row in df.iterrows():
        print(f"{row['symbol']:<12} {row['feature_source']:<22} "
              f"{row['rows']:>8} {row['columns']:>6} "
              f"{row['avg_time_s']:>8.3f} {row['min_time_s']:>8.3f} "
              f"{row['avg_peak_mem_mb']:>10.1f} "
              f"{row['rows_per_sec']:>10.1f} {row['features_per_sec']:>10.1f}")

    print()
    print("=" * 70)
    print("COMPARISON SUMMARY (vs research baseline)")
    print("=" * 70)

    for symbol in SYMBOLS:
        r_row = df[(df["symbol"] == symbol) & (df["feature_source"] == "research")]
        if r_row.empty:
            continue
        r = r_row.iloc[0]

        print(f"\n  {symbol} (research baseline: {r['avg_time_s']:.3f}s, {r['avg_peak_mem_mb']:.1f}MB, {r['columns']} cols):")

        for source in ["engine", "engine_standalone"]:
            e_row = df[(df["symbol"] == symbol) & (df["feature_source"] == source)]
            if e_row.empty:
                continue
            e = e_row.iloc[0]

            time_ratio = e["avg_time_s"] / r["avg_time_s"] if r["avg_time_s"] > 0 else float("inf")
            mem_ratio = e["avg_peak_mem_mb"] / r["avg_peak_mem_mb"] if r["avg_peak_mem_mb"] > 0 else float("inf")
            rows_ratio = e["rows_per_sec"] / r["rows_per_sec"] if r["rows_per_sec"] > 0 else float("inf")

            speed_label = "FASTER" if time_ratio < 1.0 else "SLOWER"
            mem_label = "LESS" if mem_ratio < 1.0 else "MORE"

            print(f"    {source:<22} {e['avg_time_s']:.3f}s ({speed_label} {abs(1-time_ratio)*100:.1f}%), "
                  f"mem={e['avg_peak_mem_mb']:.1f}MB ({mem_label} {abs(1-mem_ratio)*100:.1f}%), "
                  f"rows/s={e['rows_per_sec']:.1f} ({rows_ratio:.2f}x), "
                  f"cols={e['columns']}")

    print()
    print(f"Results saved to: {OUTPUT_DIR / 'benchmark_results.csv'}")


if __name__ == "__main__":
    main()
