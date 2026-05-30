"""
Alpha Pipeline Diff Runner: research vs engine_standalone

用法：
    python pipeline_diff_standalone.py
"""

import sys
from pathlib import Path
import json
import time

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pipeline_diff_runner import (
    run_pipeline,
    extract_ic_data,
    extract_signal_data,
    extract_leaderboard,
    compare_ic,
    compare_signals,
    compare_leaderboard,
    _serialize_result,
)

OUTPUT_DIR = BACKEND_ROOT / "reports" / "feature_parity" / "pipeline_diff_standalone"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Alpha Pipeline Diff: research vs engine_standalone")
    print("=" * 60)
    print()

    print("1/4: Running pipeline with feature-source=research...")
    t0 = time.time()
    result_research = run_pipeline("research")
    t_research = time.time() - t0
    print(f"  Research pipeline completed in {t_research:.1f}s")
    print()

    print("2/4: Running pipeline with feature-source=engine_standalone...")
    t0 = time.time()
    result_standalone = run_pipeline("engine_standalone")
    t_standalone = time.time() - t0
    print(f"  Standalone pipeline completed in {t_standalone:.1f}s")
    print()

    print("3/4: Extracting data...")
    ic_r = extract_ic_data(result_research)
    ic_s = extract_ic_data(result_standalone)
    sig_r = extract_signal_data(result_research)
    sig_s = extract_signal_data(result_standalone)
    lb_r = extract_leaderboard(result_research)
    lb_s = extract_leaderboard(result_standalone)
    print(f"  IC rows: research={len(ic_r)}, standalone={len(ic_s)}")
    print(f"  Signal rows: research={len(sig_r)}, standalone={len(sig_s)}")
    print(f"  Leaderboard rows: research={len(lb_r)}, standalone={len(lb_s)}")
    print()

    print("4/4: Comparing...")
    ic_diff = compare_ic(ic_r, ic_s)
    sig_diff = compare_signals(sig_r, sig_s)
    lb_diff = compare_leaderboard(lb_r, lb_s)

    ic_diff.to_csv(OUTPUT_DIR / "ic_diff.csv", index=False)
    sig_diff.to_csv(OUTPUT_DIR / "signal_diff.csv", index=False)
    lb_diff.to_csv(OUTPUT_DIR / "leaderboard_diff.csv", index=False)

    with open(OUTPUT_DIR / "result_research.json", "w", encoding="utf-8") as f:
        json.dump(_serialize_result(result_research), f, indent=2, default=str)
    with open(OUTPUT_DIR / "result_standalone.json", "w", encoding="utf-8") as f:
        json.dump(_serialize_result(result_standalone), f, indent=2, default=str)

    print()
    print("=" * 60)
    print("IC Diff Summary")
    print("=" * 60)
    ic_pass = False
    if not ic_diff.empty and "ic_diff" in ic_diff.columns:
        max_ic_diff = ic_diff["ic_diff"].max()
        max_rank_ic_diff = ic_diff["rank_ic_diff"].max()
        ic_pass = max_ic_diff <= 1e-9
        print(f"  Max IC diff:       {max_ic_diff:.2e}")
        print(f"  Max rank_ic diff:  {max_rank_ic_diff:.2e}")
        if "ic_research" in ic_diff.columns and "ic_engine" in ic_diff.columns:
            valid_mask = ~(ic_diff["ic_research"].isna() | ic_diff["ic_engine"].isna())
            if valid_mask.sum() > 1:
                ic_corr = np.corrcoef(
                    ic_diff.loc[valid_mask, "ic_research"],
                    ic_diff.loc[valid_mask, "ic_engine"],
                )[0, 1]
                print(f"  IC correlation:    {ic_corr:.10f}")
                if abs(ic_corr - 1.0) < 1e-9:
                    ic_pass = True
                    print(f"  IC corr=1 PASS:    True")
        print(f"  IC PASS:           {'YES' if ic_pass else 'NO'}")
    else:
        print("  No IC data")

    print()
    print("=" * 60)
    print("Signal Diff Summary")
    print("=" * 60)
    pf_pass = False
    trades_pass = False
    if not sig_diff.empty and "profit_factor_diff" in sig_diff.columns:
        max_pf_diff = sig_diff["profit_factor_diff"].max()
        max_trades_diff = sig_diff["trades_diff"].max()
        status_match = (sig_diff["final_status_research"] == sig_diff["final_status_engine"]).all()
        pf_pass = max_pf_diff <= 1e-6
        trades_pass = max_trades_diff <= 0
        print(f"  Max PF diff:       {max_pf_diff:.2e}")
        print(f"  Max trades diff:   {max_trades_diff:.2e}")
        print(f"  Status match:      {status_match}")
        print(f"  PF PASS:           {'YES' if pf_pass else 'NO'}")
        print(f"  Trades PASS:       {'YES' if trades_pass else 'NO'}")
    else:
        print("  No signal data")

    print()
    print("=" * 60)
    print("Leaderboard Diff Summary")
    print("=" * 60)
    lb_status_match = False
    if not lb_diff.empty:
        lb_status_match = (lb_diff["final_status_research"] == lb_diff["final_status_engine"]).all()
        print(f"  Status match:      {lb_status_match}")
        if "profit_factor_research" in lb_diff.columns:
            pf_diff = np.abs(
                lb_diff["profit_factor_research"].fillna(0) - lb_diff["profit_factor_engine"].fillna(0)
            )
            print(f"  Max PF diff:       {pf_diff.max():.2e}")
    else:
        print("  No leaderboard data")

    print()
    print("=" * 60)
    print("Final Candidates")
    print("=" * 60)
    c_r = {(r.strategy, r.symbol) for r in result_research.results if r.final_status in ("pass", "warning")}
    c_s = {(r.strategy, r.symbol) for r in result_standalone.results if r.final_status in ("pass", "warning")}
    candidates_match = c_r == c_s
    print(f"  Research candidates:   {len(c_r)}")
    print(f"  Standalone candidates: {len(c_s)}")
    print(f"  Candidates match:      {candidates_match}")
    if not candidates_match:
        only_r = c_r - c_s
        only_s = c_s - c_r
        if only_r:
            print(f"  Only in research: {only_r}")
        if only_s:
            print(f"  Only in standalone: {only_s}")

    print()
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    checks = {
        "IC diff <= 1e-9 or corr=1": ic_pass,
        "PF diff <= 1e-6": pf_pass,
        "Trades count match": trades_pass,
        "Leaderboard status match": lb_status_match,
        "Final candidates match": candidates_match,
    }
    all_pass = all(checks.values())
    for name, passed in checks.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    print()
    print(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAIL'}")
    print()
    print(f"Reports saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
