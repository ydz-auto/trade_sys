"""
Per-Symbol Leaderboard - Alpha 研究的核心输出

按每个标的独立生成完整的 Alpha Factory 报告：
  reports/leaderboard/
  ├── BTCUSDT/
  │   ├── strategy_leaderboard.csv
  │   ├── walk_forward_details.csv
  │   ├── stability_report.csv
  │   └── alpha_profile.md
  ├── SOLUSDT/
  ├── ETCUSDT/
  └── ZECUSDT/

支持两种输入：
  1. AlphaPipelineResult（直接从 pipeline 生成）
  2. CSV 文件（从已有 leaderboard.csv 加载）
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.pipeline import AlphaPipelineResult, AlphaValidationResult


def load_from_csv(
    is_lb_path: Optional[str] = None,
    oos_lb_path: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    if is_lb_path is None:
        is_lb_path = str(BACKEND_ROOT / "reports" / "alpha" / "no_oi" / "leaderboard.csv")
    if oos_lb_path is None:
        oos_lb_path = str(BACKEND_ROOT / "reports" / "alpha" / "no_oi" / "oos_2026" / "leaderboard.csv")

    is_lb = pd.read_csv(is_lb_path) if Path(is_lb_path).exists() else None
    oos_lb = pd.read_csv(oos_lb_path) if Path(oos_lb_path).exists() else None
    return is_lb, oos_lb


def generate_from_pipeline_result(
    pipeline_result: AlphaPipelineResult,
    base_output_dir: str = "reports/alpha/leaderboard",
):
    rows = _extract_rows_from_pipeline(pipeline_result)
    df = pd.DataFrame(rows)
    if df.empty:
        print("No results to generate per-symbol leaderboard from.")
        return

    _generate_per_symbol_leaderboard(df, base_output_dir)


def _extract_rows_from_pipeline(
    pipeline_result: AlphaPipelineResult,
) -> List[Dict]:
    rows = []
    for r in pipeline_result.results:
        row = _extract_single_result(r)
        rows.append(row)
    return rows


def _extract_single_result(r: AlphaValidationResult) -> Dict:
    metrics = r.best_metrics or {}
    row = {
        "alpha": r.strategy,
        "symbol": r.symbol,
        "tf": r.timeframe,
        "profit_factor": metrics.get("profit_factor", np.nan),
        "sharpe": metrics.get("sharpe", np.nan),
        "trades": metrics.get("trades", 0),
        "win_rate": metrics.get("win_rate", np.nan),
        "total_return": metrics.get("total_ret", np.nan),
        "avg_ret": metrics.get("avg_ret", np.nan),
        "status": r.final_status,
    }

    wf_data = _extract_stage_data(r, "walk_forward")
    stab_data = _extract_stage_data(r, "parameter_stability")

    row["wf_windows"] = wf_data.get("total_windows", 0)
    row["wf_avg_ret"] = wf_data.get("avg_return", np.nan)
    row["wf_avg_sharpe"] = wf_data.get("avg_sharpe", np.nan)
    row["wf_wr_consistency"] = wf_data.get("win_rate_consistency", np.nan)
    row["wf_profit_factor"] = wf_data.get("profit_factor", np.nan)
    row["wf_decay_rate"] = wf_data.get("decay_rate", np.nan)
    row["wf_profitable_ratio"] = wf_data.get("profitable_window_ratio", np.nan)
    row["wf_sharpe_std"] = wf_data.get("sharpe_std", np.nan)
    row["wf_regime_stability"] = wf_data.get("regime_stability_score", np.nan)
    row["wf_passed"] = wf_data.get("_passed", False)

    row["stab_score"] = stab_data.get("stability_score", np.nan)
    row["stab_1d"] = stab_data.get("is_1d_stable", False)
    row["stab_2d"] = stab_data.get("is_2d_stable", False)
    row["stab_cross_regime"] = stab_data.get("is_cross_regime_stable", False)
    row["stab_regime_concentration"] = stab_data.get("regime_concentration", np.nan)
    row["stab_profitable_regimes"] = ",".join(stab_data.get("profitable_regimes", []))
    row["stab_losing_regimes"] = ",".join(stab_data.get("losing_regimes", []))
    row["stab_passed"] = stab_data.get("_passed", False)

    row["tier"] = _classify_tier(row)

    return row


def _extract_stage_data(r: AlphaValidationResult, stage_name: str) -> Dict:
    for s in r.stages:
        if s.stage_name == stage_name:
            data = dict(s.data) if s.data else {}
            data["_passed"] = s.passed
            return data
    return {}


def _classify_tier(row: Dict) -> str:
    pf = row.get("profit_factor", 0)
    if pd.isna(pf):
        pf = 0
    sharpe = row.get("sharpe", 0)
    if pd.isna(sharpe):
        sharpe = 0
    status = row.get("status", "fail")
    wf_passed = row.get("wf_passed", False)
    stab_passed = row.get("stab_passed", False)
    wf_skipped = row.get("wf_windows", 0) == 0

    if status not in ("pass", "warning"):
        return "C"

    if pf > 1.5 and sharpe > 1.5:
        if wf_skipped or wf_passed:
            if wf_skipped or stab_passed:
                return "A"
            return "B"
        return "B"

    if pf > 1.2 and sharpe > 1.0:
        if wf_skipped or wf_passed:
            return "B"
        return "C"

    return "C"


def _generate_per_symbol_leaderboard(
    df: pd.DataFrame,
    base_output_dir: str,
):
    output_root = BACKEND_ROOT / base_output_dir
    output_root.mkdir(parents=True, exist_ok=True)

    symbols = sorted(df["symbol"].unique())
    print(f"Generating per-symbol leaderboard for {len(symbols)} symbols")
    print(f"  Symbols: {symbols}")

    all_profiles = []

    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"Processing {symbol}")
        print(f"{'='*80}")

        symbol_dir = output_root / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)

        symbol_df = df[df["symbol"] == symbol].copy()

        strategy_lb = _generate_strategy_leaderboard(symbol_df, symbol_dir)
        _generate_walk_forward_details(symbol_df, symbol_dir)
        _generate_stability_report(symbol_df, symbol_dir)

        profile = _generate_alpha_profile(symbol_df, symbol)
        all_profiles.append(profile)

    _generate_global_alpha_map(all_profiles, output_root)

    print(f"\n{'='*80}")
    print(f"Complete!")
    print(f"{'='*80}")


def _generate_strategy_leaderboard(
    symbol_df: pd.DataFrame,
    symbol_dir: Path,
) -> pd.DataFrame:
    lb = symbol_df.copy()

    lb = lb.sort_values(
        by=["tier", "profit_factor"],
        ascending=[True, False],
    ).reset_index(drop=True)

    output_path = symbol_dir / "strategy_leaderboard.csv"
    lb.to_csv(output_path, index=False)
    print(f"  Saved strategy_leaderboard.csv ({len(lb)} rows)")
    return lb


def _generate_walk_forward_details(
    symbol_df: pd.DataFrame,
    symbol_dir: Path,
):
    wf_cols = [
        "alpha", "wf_windows", "wf_avg_ret", "wf_avg_sharpe",
        "wf_wr_consistency", "wf_profit_factor", "wf_decay_rate",
        "wf_profitable_ratio", "wf_sharpe_std", "wf_regime_stability",
        "wf_passed",
    ]
    available_cols = [c for c in wf_cols if c in symbol_df.columns]
    if not available_cols:
        return

    wf_df = symbol_df[available_cols].copy()
    wf_df = wf_df.sort_values("wf_avg_sharpe", ascending=False, na_position="last").reset_index(drop=True)

    output_path = symbol_dir / "walk_forward_details.csv"
    wf_df.to_csv(output_path, index=False)
    print(f"  Saved walk_forward_details.csv")


def _generate_stability_report(
    symbol_df: pd.DataFrame,
    symbol_dir: Path,
):
    stab_cols = [
        "alpha", "stab_score", "stab_1d", "stab_2d",
        "stab_cross_regime", "stab_regime_concentration",
        "stab_profitable_regimes", "stab_losing_regimes", "stab_passed",
    ]
    available_cols = [c for c in stab_cols if c in symbol_df.columns]
    if not available_cols:
        return

    stab_df = symbol_df[available_cols].copy()
    stab_df = stab_df.sort_values("stab_score", ascending=False, na_position="last").reset_index(drop=True)

    output_path = symbol_dir / "stability_report.csv"
    stab_df.to_csv(output_path, index=False)
    print(f"  Saved stability_report.csv")


def _generate_alpha_profile(
    symbol_df: pd.DataFrame,
    symbol: str,
) -> Dict:
    is_pass = symbol_df[symbol_df["status"] == "pass"]
    is_warning = symbol_df[symbol_df["status"] == "warning"]
    is_active = pd.concat([is_pass, is_warning])

    tier_a = symbol_df[symbol_df["tier"] == "A"]
    tier_b = symbol_df[symbol_df["tier"] == "B"]

    best_is = None
    if len(is_active) > 0:
        pf_valid = is_active["profit_factor"].dropna()
        if len(pf_valid) > 0:
            best_is = is_active.loc[pf_valid.idxmax()]

    wf_active = symbol_df[symbol_df["wf_passed"] == True]
    best_wf = None
    if len(wf_active) > 0:
        wf_valid = wf_active["wf_avg_sharpe"].dropna()
        if len(wf_valid) > 0:
            best_wf = wf_active.loc[wf_valid.idxmax()]

    profile = {
        "symbol": symbol,
        "is_pass_count": len(is_pass),
        "is_warning_count": len(is_warning),
        "is_fail_count": len(symbol_df) - len(is_pass) - len(is_warning),
        "tier_a_count": len(tier_a),
        "tier_b_count": len(tier_b),
        "best_is_alpha": best_is["alpha"] if best_is is not None else None,
        "best_is_pf": best_is["profit_factor"] if best_is is not None else None,
        "best_wf_alpha": best_wf["alpha"] if best_wf is not None else None,
        "best_wf_sharpe": best_wf["wf_avg_sharpe"] if best_wf is not None else None,
        "dominant_alpha": None,
    }

    if best_is is not None:
        profile["dominant_alpha"] = best_is["alpha"]
    if best_wf is not None:
        profile["dominant_alpha"] = best_wf["alpha"]

    _write_alpha_profile_md(profile, symbol_df, symbol)

    return profile


def _write_alpha_profile_md(
    profile: Dict,
    symbol_df: pd.DataFrame,
    symbol: str,
):
    output_path = BACKEND_ROOT / "reports" / "alpha" / "leaderboard" / symbol / "alpha_profile.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {symbol} Alpha Profile\n\n")

        f.write("## Summary\n\n")
        f.write(f"- **Dominant Alpha**: {profile['dominant_alpha']}\n")
        f.write(f"- **IS Pass**: {profile['is_pass_count']}\n")
        f.write(f"- **IS Warning**: {profile['is_warning_count']}\n")
        f.write(f"- **Tier A**: {profile['tier_a_count']}\n")
        f.write(f"- **Tier B**: {profile['tier_b_count']}\n\n")

        f.write("## Best In-Sample\n\n")
        if profile['best_is_alpha']:
            f.write(f"- **Alpha**: {profile['best_is_alpha']}\n")
            pf_val = profile['best_is_pf']
            f.write(f"- **PF**: {pf_val:.2f}\n\n")

        f.write("## Best Walk-Forward\n\n")
        if profile['best_wf_alpha']:
            f.write(f"- **Alpha**: {profile['best_wf_alpha']}\n")
            wf_val = profile['best_wf_sharpe']
            f.write(f"- **WF Sharpe**: {wf_val:.3f}\n\n")

        f.write("## Tier A Candidates\n\n")
        tier_a = symbol_df[symbol_df["tier"] == "A"]
        if len(tier_a) > 0:
            f.write("| Alpha | PF | Sharpe | WF Passed | Stab Passed |\n")
            f.write("|-------|----|--------|-----------|-------------|\n")
            for _, row in tier_a.iterrows():
                f.write(
                    f"| {row['alpha']} | {row['profit_factor']:.2f} | "
                    f"{row['sharpe']:.2f} | {row.get('wf_passed', 'N/A')} | "
                    f"{row.get('stab_passed', 'N/A')} |\n"
                )
            f.write("\n")

        f.write("## Tier B Candidates\n\n")
        tier_b = symbol_df[symbol_df["tier"] == "B"]
        if len(tier_b) > 0:
            f.write("| Alpha | PF | Sharpe | WF Passed | Stab Passed |\n")
            f.write("|-------|----|--------|-----------|-------------|\n")
            for _, row in tier_b.iterrows():
                f.write(
                    f"| {row['alpha']} | {row['profit_factor']:.2f} | "
                    f"{row['sharpe']:.2f} | {row.get('wf_passed', 'N/A')} | "
                    f"{row.get('stab_passed', 'N/A')} |\n"
                )
            f.write("\n")

    print(f"  Saved alpha_profile.md")


def _generate_global_alpha_map(profiles: List[Dict], output_root: Path):
    alpha_map = pd.DataFrame(profiles)

    csv_path = output_root / "alpha_map.csv"
    alpha_map.to_csv(csv_path, index=False)

    md_path = output_root / "ALPHA_MAP.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Per-Asset Alpha Map\n\n")

        f.write("## Dominant Alpha Summary\n\n")
        f.write("| Symbol | Dominant Alpha | Best IS PF | Best WF Sharpe | Tier A | Tier B |\n")
        f.write("|--------|----------------|------------|----------------|--------|--------|\n")
        for p in profiles:
            is_pf_str = f"{p['best_is_pf']:.2f}" if p['best_is_pf'] is not None else "N/A"
            wf_sh_str = f"{p['best_wf_sharpe']:.3f}" if p['best_wf_sharpe'] is not None else "N/A"
            f.write(
                f"| {p['symbol']} | {p['dominant_alpha']} | "
                f"{is_pf_str} | {wf_sh_str} | "
                f"{p['tier_a_count']} | {p['tier_b_count']} |\n"
            )

        f.write("\n")

        f.write("## Tier Classification\n\n")
        f.write("- **Tier A**: PF>1.5, Sharpe>1.5, WF pass, Stability pass → Paper Trading\n")
        f.write("- **Tier B**: PF>1.2, Sharpe>1.0, WF pass → Continue Validation\n")
        f.write("- **Tier C**: Below thresholds → Not for production\n\n")

    print(f"\nSaved global alpha_map.csv and ALPHA_MAP.md")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Per-Symbol Leaderboard Generator")
    parser.add_argument("--is-lb", type=str, default=None,
                        help="Path to IS leaderboard CSV")
    parser.add_argument("--oos-lb", type=str, default=None,
                        help="Path to OOS leaderboard CSV")
    parser.add_argument("--output-dir", type=str, default="reports/alpha/leaderboard",
                        help="Output directory")

    args = parser.parse_args()

    is_lb, oos_lb = load_from_csv(args.is_lb, args.oos_lb)

    if is_lb is None:
        print("Error: No IS leaderboard data available")
        return

    if oos_lb is not None:
        is_lb["dataset"] = "IS"
        oos_lb["dataset"] = "OOS"
        combined = pd.concat([is_lb, oos_lb], ignore_index=True)
    else:
        combined = is_lb

    _generate_per_symbol_leaderboard(combined, args.output_dir)


if __name__ == "__main__":
    main()
