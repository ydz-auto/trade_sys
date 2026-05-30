"""
Alpha Correlation Analysis CLI

回答：当前系统到底有几个独立 Alpha Source？

用法：
    python alpha_correlation_analysis.py --symbol BTCUSDT
    python alpha_correlation_analysis.py --symbol BTCUSDT,ETCUSDT,ZECUSDT
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.correlation.alpha_return_matrix import AlphaReturnMatrixBuilder
from research.alpha.correlation.alpha_correlation import compute_alpha_correlation, find_highly_correlated_pairs
from research.alpha.correlation.alpha_cluster import cluster_alphas
from research.alpha.correlation.alpha_family_registry import match_clusters_to_families
from research.alpha.correlation.independent_alpha_counter import count_independent_alphas
from research.alpha.correlation.report_generator import (
    generate_correlation_report,
    save_correlation_csv,
    save_cluster_csv,
)

SYMBOLS = ["BTCUSDT", "ETCUSDT", "ZECUSDT", "SOLUSDT"]
EXCHANGE = "binance"
TIMEFRAME = "1h"
DAYS = 365
HOLDING_BARS = 20
PERCENTILE = 90.0
TAKER_FEE = 0.0004
FEATURE_SOURCE = "engine_standalone"
CORR_THRESHOLD = 0.7
DISTANCE_THRESHOLD = 0.3

OUTPUT_DIR = BACKEND_ROOT / "reports" / "alpha_correlation"


def run_analysis(symbol: str):
    print(f"\n{'=' * 70}")
    print(f"  Alpha Correlation Analysis | {symbol}")
    print(f"{'=' * 70}")

    builder = AlphaReturnMatrixBuilder(
        symbol=symbol,
        exchange=EXCHANGE,
        timeframe=TIMEFRAME,
        days=DAYS,
        holding_bars=HOLDING_BARS,
        percentile=PERCENTILE,
        taker_fee=TAKER_FEE,
        feature_source=FEATURE_SOURCE,
    )

    print(f"  Building alpha return matrix...")
    t0 = time.time()
    return_matrix = builder.build()
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s: {return_matrix.shape[1]} alphas, {len(return_matrix)} bars")

    if return_matrix.empty or return_matrix.shape[1] < 2:
        print(f"  Not enough alphas for correlation analysis, skipping")
        return

    print(f"\n  Computing correlation matrix...")
    corr_matrix, abs_corr_matrix = compute_alpha_correlation(return_matrix)

    if corr_matrix.empty:
        print(f"  Correlation matrix empty, skipping")
        return

    print(f"\n  Finding highly correlated pairs (|corr| > {CORR_THRESHOLD})...")
    pairs = find_highly_correlated_pairs(corr_matrix, threshold=CORR_THRESHOLD)
    if not pairs.empty:
        print(f"  Found {len(pairs)} highly correlated pairs:")
        for _, row in pairs.head(10).iterrows():
            print(f"    {row['alpha_1']:<30} {row['alpha_2']:<30} corr={row['correlation']:+.3f}")
    else:
        print(f"  No highly correlated pairs found")

    print(f"\n  Clustering alphas (distance_threshold={DISTANCE_THRESHOLD})...")
    clusters = cluster_alphas(corr_matrix, distance_threshold=DISTANCE_THRESHOLD)
    print(f"  Found {len(clusters)} clusters:")
    for name, members in clusters.items():
        print(f"    {name}: {members}")

    print(f"\n  Matching clusters to predefined families...")
    family_matches = match_clusters_to_families(clusters)
    for match in family_matches:
        print(f"    {match['cluster']} -> {match['best_family_match']} (match={match['match_ratio']:.0%})")

    print(f"\n  Counting independent alphas (corr_threshold={CORR_THRESHOLD})...")
    independent_result = count_independent_alphas(corr_matrix, corr_threshold=CORR_THRESHOLD)

    report = generate_correlation_report(
        return_matrix=return_matrix,
        corr_matrix=corr_matrix,
        clusters=clusters,
        independent_result=independent_result,
        family_matches=family_matches,
        symbol=symbol,
        corr_threshold=CORR_THRESHOLD,
    )

    print(report)

    save_correlation_csv(corr_matrix, str(OUTPUT_DIR), symbol=symbol)
    save_cluster_csv(clusters, independent_result, str(OUTPUT_DIR), symbol=symbol)

    return {
        "symbol": symbol,
        "return_matrix": return_matrix,
        "corr_matrix": corr_matrix,
        "clusters": clusters,
        "independent_result": independent_result,
        "family_matches": family_matches,
    }


def main():
    print("=" * 70)
    print("ALPHA CORRELATION ANALYSIS")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframe: {TIMEFRAME}, Days: {DAYS}")
    print(f"Holding bars: {HOLDING_BARS}, Percentile: {PERCENTILE}")
    print(f"Correlation threshold: {CORR_THRESHOLD}")
    print(f"Feature source: {FEATURE_SOURCE}")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for symbol in SYMBOLS:
        try:
            result = run_analysis(symbol)
            if result:
                all_results[symbol] = result
        except Exception as e:
            print(f"\n  ERROR for {symbol}: {e}")
            import traceback
            traceback.print_exc()

    if len(all_results) > 1:
        print(f"\n{'=' * 70}")
        print("CROSS-SYMBOL COMPARISON")
        print(f"{'=' * 70}")
        print(f"\n  {'Symbol':<12} {'Total':>6} {'Independent':>12} {'Ratio':>8}")
        print(f"  {'-' * 40}")
        for symbol, result in all_results.items():
            total = result["independent_result"]["total_alphas"]
            indep = result["independent_result"]["independent_alpha_count"]
            ratio = indep / total if total > 0 else 0
            print(f"  {symbol:<12} {total:>6} {indep:>12} {ratio:>8.1%}")

    print(f"\nReports saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
