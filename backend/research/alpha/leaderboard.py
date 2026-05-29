"""
Leaderboard - Alpha 验证结果聚合与输出

输出格式：
- CSV: reports/alpha/leaderboard.csv（给人看和排序）
- JSON: reports/alpha/leaderboard.json（给后续 pipeline / dashboard 用）
- CLI: 格式化表格打印
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from research.alpha.pipeline import AlphaPipelineResult, AlphaValidationResult


_STATUS_ICONS = {
    "pass": "\u2705",
    "warning": "\u26a0\ufe0f",
    "fail": "\u274c",
    "blocked": "\U0001f6ab",
    "error": "\U0001f6ab",
    "unknown": "?",
}

_TIER_ICONS = {
    "A": "\U0001f7e2",
    "B": "\U0001f7e1",
    "C": "\U0001f534",
}


class Leaderboard:
    def __init__(self, pipeline_result: AlphaPipelineResult):
        self.pipeline_result = pipeline_result
        self._df: Optional[pd.DataFrame] = None

    def generate(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        rows = []
        for r in self.pipeline_result.results:
            row = self._extract_row(r)
            rows.append(row)

        self._df = pd.DataFrame(rows)
        return self._df

    def _extract_row(self, r: AlphaValidationResult) -> Dict:
        stages_passed = sum(1 for s in r.stages if s.passed)
        total_stages = len(r.stages)

        stage_passed_list = [s.stage_name for s in r.stages if s.passed]
        fail_reason_list = [f"{s.stage_name}: {s.message}" for s in r.stages if not s.passed and not s.skipped]

        metrics = r.best_metrics or {}
        status = self._compute_status(r)

        wf_data = self._extract_stage_data(r, "walk_forward")
        stab_data = self._extract_stage_data(r, "parameter_stability")

        row = {
            "alpha": r.strategy,
            "symbol": r.symbol,
            "tf": r.timeframe,
            "fee_mode": self.pipeline_result.config.get("fee_mode", ""),
            "profit_factor": metrics.get("profit_factor", np.nan),
            "sharpe": metrics.get("sharpe", np.nan),
            "trades": metrics.get("trades", 0),
            "win_rate": metrics.get("win_rate", np.nan),
            "total_return": metrics.get("total_ret", np.nan),
            "avg_ret": metrics.get("avg_ret", np.nan),
            "stages_passed": stages_passed,
            "total_stages": total_stages,
            "stage_passed": ",".join(stage_passed_list) if stage_passed_list else "",
            "fail_reason": "; ".join(fail_reason_list) if fail_reason_list else "",
            "status": status,
            "wf_windows": wf_data.get("total_windows", 0),
            "wf_avg_sharpe": wf_data.get("avg_sharpe", np.nan),
            "wf_decay_rate": wf_data.get("decay_rate", np.nan),
            "wf_profitable_ratio": wf_data.get("profitable_window_ratio", np.nan),
            "wf_regime_stability": wf_data.get("regime_stability_score", np.nan),
            "wf_passed": wf_data.get("_passed", False),
            "stab_score": stab_data.get("stability_score", np.nan),
            "stab_1d": stab_data.get("is_1d_stable", False),
            "stab_2d": stab_data.get("is_2d_stable", False),
            "stab_cross_regime": stab_data.get("is_cross_regime_stable", False),
            "stab_passed": stab_data.get("_passed", False),
        }

        row["tier"] = self._classify_tier(row)

        return row

    def _extract_stage_data(self, r: AlphaValidationResult, stage_name: str) -> Dict:
        for s in r.stages:
            if s.stage_name == stage_name:
                data = dict(s.data) if s.data else {}
                data["_passed"] = s.passed
                return data
        return {}

    def _compute_status(self, r: AlphaValidationResult) -> str:
        if r.final_status in ("blocked", "unknown", "error"):
            return r.final_status

        metrics = r.best_metrics
        if metrics is None:
            return "fail"

        pf = metrics.get("profit_factor", 0)
        sharpe = metrics.get("sharpe", 0)
        trades = metrics.get("trades", 0)

        if pf > 1.1 and sharpe > 1 and trades >= 30:
            return "pass"
        if pf > 1.0 and trades >= 30:
            return "warning"
        return "fail"

    def _classify_tier(self, row: Dict) -> str:
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

    def save_csv(self, path: str) -> None:
        df = self.generate()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

    def save_json(self, path: str) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": self.pipeline_result.timestamp,
            "config": self.pipeline_result.config,
            "results": self.pipeline_result.to_dict()["results"],
            "summary": self._build_summary(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    def print_table(self) -> None:
        df = self.generate()
        if len(df) == 0:
            print("No results to display.")
            return

        print(f"\n{'='*140}")
        print(f"Alpha Leaderboard | {self.pipeline_result.timestamp}")
        print(f"{'='*140}")
        print(
            f"{'alpha':<25} {'symbol':<10} {'tf':<5} "
            f"{'PF':>8} {'sharpe':>8} {'trades':>7} "
            f"{'WF':>5} {'Stab':>5} "
            f"{'decay':>7} {'pf_ratio':>8} "
            f"{'tier':>5} {'status':>8}"
        )
        print(f"{'-'*138}")

        for _, row in df.iterrows():
            pf_str = f"{row['profit_factor']:.3f}" if pd.notna(row["profit_factor"]) else "nan"
            sh_str = f"{row['sharpe']:.3f}" if pd.notna(row["sharpe"]) else "nan"

            wf_str = "Y" if row.get("wf_passed", False) else ("-" if row.get("wf_windows", 0) == 0 else "N")
            stab_str = "Y" if row.get("stab_passed", False) else ("-" if pd.isna(row.get("stab_score", np.nan)) else "N")

            decay_str = f"{row['wf_decay_rate']:.2f}" if pd.notna(row.get("wf_decay_rate", np.nan)) else "-"
            pf_ratio_str = f"{row['wf_profitable_ratio']:.2f}" if pd.notna(row.get("wf_profitable_ratio", np.nan)) else "-"

            tier = row.get("tier", "C")
            tier_icon = _TIER_ICONS.get(tier, "?")

            icon = _STATUS_ICONS.get(row["status"], "?")

            print(
                f"{row['alpha']:<25} {row['symbol']:<10} {row['tf']:<5} "
                f"{pf_str:>8} {sh_str:>8} {int(row['trades']):>7} "
                f"{wf_str:>5} {stab_str:>5} "
                f"{decay_str:>7} {pf_ratio_str:>8} "
                f"{tier_icon}{tier:>4} {icon} {row['status']}"
            )

        print(f"{'='*140}")

    def print_summary(self) -> None:
        df = self.generate()
        if len(df) == 0:
            print("No results to summarize.")
            return

        print(f"\n{'='*60}")
        print(f"Alpha Factory Summary")
        print(f"{'='*60}")

        status_counts = df["status"].value_counts()
        for status, count in status_counts.items():
            icon = _STATUS_ICONS.get(status, "?")
            print(f"  {icon} {status}: {count}")

        if "tier" in df.columns:
            tier_counts = df["tier"].value_counts()
            print(f"\n  Tier Distribution:")
            for tier in ["A", "B", "C"]:
                count = tier_counts.get(tier, 0)
                tier_icon = _TIER_ICONS.get(tier, "?")
                print(f"    {tier_icon} Tier {tier}: {count}")

        active = df[df["status"].isin(["pass", "warning"])]
        if len(active) > 0:
            print(f"\n  Active alphas: {len(active)}")
            symbol_counts = active["symbol"].value_counts()
            print(f"  Strongest symbols: {symbol_counts.to_dict()}")

            best = active.loc[active["profit_factor"].idxmax()] if len(active) > 0 else None
            if best is not None and pd.notna(best["profit_factor"]):
                print(
                    f"  Best alpha: {best['alpha']} on {best['symbol']} "
                    f"(PF={best['profit_factor']:.3f})"
                )

            if "tier" in active.columns:
                tier_a = active[active["tier"] == "A"]
                if len(tier_a) > 0:
                    print(f"\n  Paper Trading Candidates (Tier A):")
                    for _, row in tier_a.iterrows():
                        print(f"    {row['alpha']} on {row['symbol']} (PF={row['profit_factor']:.2f})")
        else:
            print(f"\n  No active alphas found.")

        print(f"{'='*60}")

    def _build_summary(self) -> dict:
        df = self.generate()
        summary = {
            "total_results": len(df),
            "by_status": df["status"].value_counts().to_dict(),
            "unique_alphas": list(df["alpha"].unique()),
            "unique_symbols": list(df["symbol"].unique()),
        }
        if "tier" in df.columns:
            summary["by_tier"] = df["tier"].value_counts().to_dict()
        return summary
