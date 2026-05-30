"""
Alpha Production Validation

对 top-3 alpha 候选跑完整验证 pipeline（含 Walk Forward + Parameter Stability），
输出 per-symbol leaderboard 和 paper trading 配置。

目标：回答"哪些 alpha / 哪些币 / 哪些参数可以进入 paper trading？"

用法：
    python alpha_production_validation.py
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.reporting.readiness import (
    classify_production_readiness,
    generate_paper_trading_config,
    READINESS_ICONS,
)

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETCUSDT", "ZECUSDT"]
TIMEFRAME = "1h"
DAYS = 365
EXCHANGE = "binance"

STRATEGIES = [
    "ret_5_reversal",
    "drawdown_dip_buying",
    "funding_extreme_reversal",
]

OUTPUT_DIR = BACKEND_ROOT / "reports" / "alpha_production_validation"


def run_full_validation():
    from research.alpha.validation.pipeline import AlphaPipeline

    pipeline = AlphaPipeline(
        symbols=SYMBOLS,
        timeframes=[TIMEFRAME],
        days=DAYS,
        exchange=EXCHANGE,
        skip_walk_forward=False,
        skip_stability=False,
        output_dir=str(OUTPUT_DIR / "pipeline_output"),
        feature_source="engine_standalone",
    )

    result = pipeline.run(STRATEGIES)
    return result


def extract_per_symbol_leaderboard(result) -> pd.DataFrame:
    rows = []
    for r in result.results:
        best_metrics = r.best_metrics or {}
        best_params = r.best_params or {}

        wf_data = {}
        stab_data = {}
        for s in r.stages:
            if s.stage_name == "walk_forward":
                wf_data = s.data or {}
                wf_data["passed"] = s.passed
            elif s.stage_name == "parameter_stability":
                stab_data = s.data or {}
                stab_data["passed"] = s.passed

        stab_report = stab_data.get("stability_report") or {}

        rows.append({
            "strategy": r.strategy,
            "symbol": r.symbol,
            "final_status": r.final_status,
            "profit_factor": best_metrics.get("profit_factor"),
            "sharpe": best_metrics.get("sharpe"),
            "win_rate": best_metrics.get("win_rate"),
            "trades": best_metrics.get("trades"),
            "avg_return": best_metrics.get("avg_ret"),
            "threshold": best_params.get("threshold"),
            "holding_bars": best_params.get("holding_bars"),
            "direction": best_params.get("direction"),
            "wf_passed": wf_data.get("passed"),
            "wf_avg_return": wf_data.get("avg_return"),
            "wf_avg_sharpe": wf_data.get("avg_sharpe"),
            "wf_win_rate_consistency": wf_data.get("win_rate_consistency"),
            "wf_decay_rate": wf_data.get("decay_rate"),
            "wf_profitable_window_ratio": wf_data.get("profitable_window_ratio"),
            "wf_total_windows": wf_data.get("total_windows"),
            "stab_passed": stab_data.get("passed"),
            "stab_is_1d_stable": stab_data.get("is_1d_stable"),
            "stab_is_2d_stable": stab_data.get("is_2d_stable"),
            "stab_is_cross_regime_stable": stab_data.get("is_cross_regime_stable"),
            "stab_stability_score": stab_data.get("stability_score"),
            "profitable_area_ratio": stab_report.get("profitable_area_ratio"),
            "stable_area_ratio": stab_report.get("stable_area_ratio"),
            "largest_region_ratio": stab_report.get("largest_region_ratio"),
            "needle_peak_ratio": stab_report.get("needle_peak_ratio"),
            "mean_sharpe": stab_report.get("mean_sharpe"),
            "std_sharpe": stab_report.get("std_sharpe"),
            "cv": stab_report.get("cv"),
            "stab_report_dict": stab_report,
        })

    return pd.DataFrame(rows)


def main():
    print("=" * 70)
    print("ALPHA PRODUCTION VALIDATION")
    print(f"Strategies: {STRATEGIES}")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframe: {TIMEFRAME}, Days: {DAYS}")
    print(f"Feature source: engine_standalone")
    print(f"Walk Forward: ENABLED")
    print(f"Stability: ENABLED")
    print("=" * 70)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Running full validation pipeline (this may take a while)...")
    t0 = time.time()
    result = run_full_validation()
    elapsed = time.time() - t0
    print(f"Pipeline completed in {elapsed:.1f}s")
    print()

    leaderboard = extract_per_symbol_leaderboard(result)
    leaderboard["production_readiness"] = leaderboard.apply(classify_production_readiness, axis=1)

    leaderboard.to_csv(OUTPUT_DIR / "per_symbol_leaderboard.csv", index=False)

    print("=" * 70)
    print("PER-SYMBOL LEADERBOARD")
    print("=" * 70)
    print()

    for strategy in STRATEGIES:
        strat_rows = leaderboard[leaderboard["strategy"] == strategy]
        if strat_rows.empty:
            continue
        print(f"--- {strategy} ---")
        for _, row in strat_rows.iterrows():
            icon = READINESS_ICONS.get(row["production_readiness"], "\u2753")

            pf_str = f"PF={row['profit_factor']:.3f}" if pd.notna(row.get("profit_factor")) else "PF=N/A"
            sharpe_str = f"sharpe={row['sharpe']:.3f}" if pd.notna(row.get("sharpe")) else "sharpe=N/A"
            print(f"  {icon} {row['symbol']:<12} status={row['final_status']:<8} {pf_str} {sharpe_str}")

            if pd.notna(row.get("wf_avg_sharpe")):
                print(f"    WF: avg_sharpe={row['wf_avg_sharpe']:.3f}, "
                      f"decay={row['wf_decay_rate']:.3f}, "
                      f"profitable_windows={row['wf_profitable_window_ratio']:.2f}, "
                      f"passed={row['wf_passed']}")
            stab_report = row.get("stab_report_dict")
            if isinstance(stab_report, dict) and stab_report:
                from research.stability.analyzer import StabilityReport
                report = StabilityReport(
                    profitable_area_ratio=stab_report.get("profitable_area_ratio", 0.0),
                    stable_area_ratio=stab_report.get("stable_area_ratio", 0.0),
                    largest_region_ratio=stab_report.get("largest_region_ratio", 0.0),
                    needle_peak_ratio=stab_report.get("needle_peak_ratio", 0.0),
                    mean_sharpe=stab_report.get("mean_sharpe", 0.0),
                    std_sharpe=stab_report.get("std_sharpe", 0.0),
                    cv=stab_report.get("cv", 0.0),
                    stability_score=stab_report.get("stability_score", 0.0),
                    is_stable=stab_report.get("is_stable", False),
                    needle_peak_count=stab_report.get("needle_peak_count", 0),
                    stable_region_count=stab_report.get("stable_region_count", 0),
                )
                print(report.format_text(symbol=row["symbol"], strategy=row["strategy"]))
            print(f"    -> {row['production_readiness']}")
        print()

    print("=" * 70)
    print("PRODUCTION READINESS SUMMARY")
    print("=" * 70)

    readiness_counts = leaderboard["production_readiness"].value_counts()
    for status, count in readiness_counts.items():
        print(f"  {status}: {count}")

    ready_count = (leaderboard["production_readiness"] == "READY").sum()
    total_count = len(leaderboard)
    print(f"\n  Ready for paper trading: {ready_count}/{total_count}")
    print()

    pt_config = generate_paper_trading_config(
        leaderboard,
        timeframe=TIMEFRAME,
        exchange=EXCHANGE,
        feature_source="engine_standalone",
        days=DAYS,
    )
    with open(OUTPUT_DIR / "paper_trading_config.json", "w", encoding="utf-8") as f:
        json.dump(pt_config, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("PAPER TRADING CANDIDATES")
    print("=" * 70)
    if pt_config["candidates"]:
        for c in pt_config["candidates"]:
            readiness = c.get("readiness", "READY")
            icon = "\U0001f7e2" if readiness == "READY" else "\U0001f7e0"
            thresh_str = f"thresh={c['threshold']:.6f}" if c.get("threshold") else "thresh=N/A"
            pf_str = f"PF={c['profit_factor']:.3f}" if c.get("profit_factor") else "PF=N/A"
            print(f"  {icon} {c['strategy']}/{c['symbol']} "
                  f"[{readiness}] "
                  f"dir={c['direction']} "
                  f"{thresh_str} "
                  f"hold={c['holding_bars']}bars "
                  f"{pf_str}")
    else:
        print("  No candidates ready for paper trading")

    print()
    print(f"Reports saved to: {OUTPUT_DIR}")
    print(f"  - per_symbol_leaderboard.csv")
    print(f"  - paper_trading_config.json")


if __name__ == "__main__":
    main()
