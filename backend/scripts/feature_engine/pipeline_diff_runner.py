"""
Alpha Pipeline Diff Runner

同一组参数分别用 --feature-source research 和 engine 运行 pipeline，
然后对比 IC / signal / leaderboard / final_candidates

验收标准：
  - IC diff <= 1e-9 或 corr=1
  - signal PF diff <= 1e-6
  - trades count 完全一致
  - leaderboard 排名一致
  - final_candidates 完全一致

用法：
    python pipeline_diff_runner.py
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import time

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETCUSDT", "ZECUSDT"]
TIMEFRAME = "1h"
DAYS = 90
EXCHANGE = "binance"

STRATEGIES = [
    "ret_5_reversal",
    "drawdown_dip_buying",
    "funding_extreme_reversal",
    "volatility_panic_reversal",
]

OUTPUT_DIR = BACKEND_ROOT / "reports" / "feature_parity" / "pipeline_diff"


def run_pipeline(feature_source: str):
    from research.alpha.validation.pipeline import AlphaPipeline

    pipeline = AlphaPipeline(
        symbols=SYMBOLS,
        timeframes=[TIMEFRAME],
        days=DAYS,
        exchange=EXCHANGE,
        skip_walk_forward=True,
        skip_stability=True,
        output_dir=str(OUTPUT_DIR / feature_source),
        feature_source=feature_source,
    )

    result = pipeline.run(STRATEGIES)
    return result


def extract_ic_data(result) -> pd.DataFrame:
    rows = []
    for r in result.results:
        for s in r.stages:
            if s.stage_name == "feature_ic" and s.data:
                ic_table = s.data.get("ic_table", [])
                for ic_row in ic_table:
                    rows.append({
                        "strategy": r.strategy,
                        "symbol": r.symbol,
                        **ic_row,
                    })
    return pd.DataFrame(rows)


def extract_signal_data(result) -> pd.DataFrame:
    rows = []
    for r in result.results:
        best_metrics = r.best_metrics or {}
        for s in r.stages:
            if s.stage_name == "signal_profitability":
                rows.append({
                    "strategy": r.strategy,
                    "symbol": r.symbol,
                    "final_status": r.final_status,
                    "profit_factor": best_metrics.get("profit_factor"),
                    "sharpe": best_metrics.get("sharpe"),
                    "win_rate": best_metrics.get("win_rate"),
                    "trades": best_metrics.get("trades"),
                    "avg_return": best_metrics.get("avg_ret"),
                    "best_params": json.dumps(r.best_params) if r.best_params else None,
                    "stage_passed": s.passed,
                })
                break
    return pd.DataFrame(rows)


def extract_leaderboard(result) -> pd.DataFrame:
    rows = []
    for r in result.results:
        best_metrics = r.best_metrics or {}
        rows.append({
            "strategy": r.strategy,
            "symbol": r.symbol,
            "final_status": r.final_status,
            "profit_factor": best_metrics.get("profit_factor"),
            "sharpe": best_metrics.get("sharpe"),
            "win_rate": best_metrics.get("win_rate"),
            "trades": best_metrics.get("trades"),
        })
    return pd.DataFrame(rows)


def compare_ic(ic_research: pd.DataFrame, ic_engine: pd.DataFrame) -> pd.DataFrame:
    if ic_research.empty or ic_engine.empty:
        return pd.DataFrame({"note": ["No IC data to compare"]})

    merge_cols = ["strategy", "symbol", "feature", "horizon"]
    common_cols = [c for c in merge_cols if c in ic_research.columns and c in ic_engine.columns]

    merged = pd.merge(
        ic_research[common_cols + ["ic", "rank_ic"]],
        ic_engine[common_cols + ["ic", "rank_ic"]],
        on=common_cols,
        suffixes=("_research", "_engine"),
        how="inner",
    )

    if merged.empty:
        return pd.DataFrame({"note": ["No matching IC rows"]})

    merged["ic_diff"] = np.abs(merged["ic_research"] - merged["ic_engine"])
    merged["rank_ic_diff"] = np.abs(merged["rank_ic_research"] - merged["rank_ic_engine"])

    return merged


def compare_signals(sig_research: pd.DataFrame, sig_engine: pd.DataFrame) -> pd.DataFrame:
    if sig_research.empty or sig_engine.empty:
        return pd.DataFrame({"note": ["No signal data to compare"]})

    merge_cols = ["strategy", "symbol"]
    merged = pd.merge(
        sig_research[merge_cols + ["final_status", "profit_factor", "win_rate", "trades"]],
        sig_engine[merge_cols + ["final_status", "profit_factor", "win_rate", "trades"]],
        on=merge_cols,
        suffixes=("_research", "_engine"),
        how="outer",
    )

    if merged.empty:
        return pd.DataFrame({"note": ["No matching signal rows"]})

    numeric_cols = ["profit_factor", "win_rate", "trades"]
    for col in numeric_cols:
        r_col = f"{col}_research"
        e_col = f"{col}_engine"
        if r_col in merged.columns and e_col in merged.columns:
            merged[f"{col}_diff"] = np.abs(
                merged[r_col].fillna(0) - merged[e_col].fillna(0)
            )

    return merged


def compare_leaderboard(lb_research: pd.DataFrame, lb_engine: pd.DataFrame) -> pd.DataFrame:
    if lb_research.empty or lb_engine.empty:
        return pd.DataFrame({"note": ["No leaderboard data to compare"]})

    merge_cols = ["strategy", "symbol"]
    merged = pd.merge(
        lb_research[merge_cols + ["final_status", "profit_factor", "trades"]],
        lb_engine[merge_cols + ["final_status", "profit_factor", "trades"]],
        on=merge_cols,
        suffixes=("_research", "_engine"),
        how="outer",
    )

    return merged


def _serialize_result(result) -> dict:
    def _convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict("records")
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    rows = []
    for r in result.results:
        stages_data = []
        for s in r.stages:
            stage_dict = {
                "stage_name": s.stage_name,
                "passed": s.passed,
                "message": s.message,
                "skipped": s.skipped,
                "data": s.data,
            }
            stages_data.append(stage_dict)
        rows.append({
            "strategy": r.strategy,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "stages": stages_data,
            "final_status": r.final_status,
            "best_params": r.best_params,
            "best_metrics": r.best_metrics,
            "blocked_reason": r.blocked_reason,
        })

    return {
        "results": rows,
        "config": result.config,
        "timestamp": result.timestamp,
    }


def main():
    print("=" * 60)
    print("Alpha Pipeline Diff Runner")
    print(f"Symbols: {SYMBOLS}")
    print(f"Timeframe: {TIMEFRAME}, Days: {DAYS}")
    print(f"Strategies: {STRATEGIES}")
    print("=" * 60)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("1/4: Running pipeline with feature-source=research...")
    print("=" * 60)
    t0 = time.time()
    result_research = run_pipeline("research")
    t_research = time.time() - t0
    print(f"  Research pipeline completed in {t_research:.1f}s")
    print()

    print("=" * 60)
    print("2/4: Running pipeline with feature-source=engine...")
    print("=" * 60)
    t0 = time.time()
    result_engine = run_pipeline("engine")
    t_engine = time.time() - t0
    print(f"  Engine pipeline completed in {t_engine:.1f}s")
    print()

    print("=" * 60)
    print("3/4: Extracting data for comparison...")
    print("=" * 60)

    ic_research = extract_ic_data(result_research)
    ic_engine = extract_ic_data(result_engine)
    sig_research = extract_signal_data(result_research)
    sig_engine = extract_signal_data(result_engine)
    lb_research = extract_leaderboard(result_research)
    lb_engine = extract_leaderboard(result_engine)

    print(f"  IC rows: research={len(ic_research)}, engine={len(ic_engine)}")
    print(f"  Signal rows: research={len(sig_research)}, engine={len(sig_engine)}")
    print(f"  Leaderboard rows: research={len(lb_research)}, engine={len(lb_engine)}")
    print()

    print("=" * 60)
    print("4/4: Comparing results...")
    print("=" * 60)

    ic_diff = compare_ic(ic_research, ic_engine)
    sig_diff = compare_signals(sig_research, sig_engine)
    lb_diff = compare_leaderboard(lb_research, lb_engine)

    ic_diff.to_csv(OUTPUT_DIR / "ic_diff.csv", index=False)
    sig_diff.to_csv(OUTPUT_DIR / "signal_diff.csv", index=False)
    lb_diff.to_csv(OUTPUT_DIR / "leaderboard_diff.csv", index=False)

    with open(OUTPUT_DIR / "result_research.json", "w", encoding="utf-8") as f:
        json.dump(_serialize_result(result_research), f, indent=2, default=str)
    with open(OUTPUT_DIR / "result_engine.json", "w", encoding="utf-8") as f:
        json.dump(_serialize_result(result_engine), f, indent=2, default=str)

    print()
    print("=" * 60)
    print("IC Diff Summary")
    print("=" * 60)
    ic_pass = False
    if not ic_diff.empty and "ic_diff" in ic_diff.columns:
        max_ic_diff = ic_diff["ic_diff"].max()
        max_rank_ic_diff = ic_diff["rank_ic_diff"].max()
        mean_ic_diff = ic_diff["ic_diff"].mean()
        ic_pass = max_ic_diff <= 1e-9
        print(f"  Max IC diff:       {max_ic_diff:.2e}")
        print(f"  Max rank_ic diff:  {max_rank_ic_diff:.2e}")
        print(f"  Mean IC diff:      {mean_ic_diff:.2e}")
        print(f"  IC PASS:           {'✅' if ic_pass else '❌'} (threshold: 1e-9)")

        if not ic_diff.empty and "ic_research" in ic_diff.columns and "ic_engine" in ic_diff.columns:
            valid_mask = ~(ic_diff["ic_research"].isna() | ic_diff["ic_engine"].isna())
            if valid_mask.sum() > 1:
                ic_corr = np.corrcoef(
                    ic_diff.loc[valid_mask, "ic_research"],
                    ic_diff.loc[valid_mask, "ic_engine"],
                )[0, 1]
                print(f"  IC correlation:    {ic_corr:.10f}")
                if abs(ic_corr - 1.0) < 1e-9:
                    ic_pass = True
                    print(f"  IC corr=1 PASS:    ✅")
    else:
        print("  No IC data to compare")

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
        print(f"  Status match:      {'✅' if status_match else '❌'}")
        print(f"  PF PASS:           {'✅' if pf_pass else '❌'} (threshold: 1e-6)")
        print(f"  Trades PASS:       {'✅' if trades_pass else '❌'} (threshold: 0)")
    else:
        print("  No signal data to compare")

    print()
    print("=" * 60)
    print("Leaderboard Diff Summary")
    print("=" * 60)
    lb_status_match = False
    if not lb_diff.empty:
        lb_status_match = (lb_diff["final_status_research"] == lb_diff["final_status_engine"]).all()
        print(f"  Status match:      {'✅' if lb_status_match else '❌'}")
        if "profit_factor_research" in lb_diff.columns:
            pf_diff = np.abs(
                lb_diff["profit_factor_research"].fillna(0) - lb_diff["profit_factor_engine"].fillna(0)
            )
            print(f"  Max PF diff:       {pf_diff.max():.2e}")

        lb_research_sorted = lb_research.sort_values("profit_factor", ascending=False).reset_index(drop=True)
        lb_engine_sorted = lb_engine.sort_values("profit_factor", ascending=False).reset_index(drop=True)
        if len(lb_research_sorted) == len(lb_engine_sorted) and len(lb_research_sorted) > 0:
            rank_match = (
                lb_research_sorted["strategy"] == lb_engine_sorted["strategy"]
            ).all() and (
                lb_research_sorted["symbol"] == lb_engine_sorted["symbol"]
            ).all()
            print(f"  Rank match:        {'✅' if rank_match else '❌'}")
        else:
            print(f"  Rank match:        ❌ (different row counts)")
    else:
        print("  No leaderboard data to compare")

    print()
    print("=" * 60)
    print("Final Candidates")
    print("=" * 60)
    candidates_research = [
        r for r in result_research.results
        if r.final_status in ("pass", "warning")
    ]
    candidates_engine = [
        r for r in result_engine.results
        if r.final_status in ("pass", "warning")
    ]
    print(f"  Research candidates: {len(candidates_research)}")
    print(f"  Engine candidates:   {len(candidates_engine)}")

    research_keys = {(r.strategy, r.symbol) for r in candidates_research}
    engine_keys = {(r.strategy, r.symbol) for r in candidates_engine}
    candidates_match = research_keys == engine_keys
    print(f"  Candidates match:    {'✅' if candidates_match else '❌'}")
    if not candidates_match:
        only_research = research_keys - engine_keys
        only_engine = engine_keys - research_keys
        if only_research:
            print(f"  Only in research: {only_research}")
        if only_engine:
            print(f"  Only in engine: {only_engine}")

    print()
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    checks = {
        "IC diff <= 1e-9": ic_pass,
        "PF diff <= 1e-6": pf_pass,
        "Trades count match": trades_pass,
        "Leaderboard status match": lb_status_match,
        "Final candidates match": candidates_match,
    }
    all_pass = all(checks.values())
    for name, passed in checks.items():
        print(f"  {name}: {'✅ PASS' if passed else '❌ FAIL'}")
    print()
    print(f"  Overall: {'✅ ALL PASS' if all_pass else '❌ SOME FAIL'}")

    print()
    print(f"Reports saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
