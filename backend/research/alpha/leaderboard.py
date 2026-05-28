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


class Leaderboard:
    def __init__(self, pipeline_result: AlphaPipelineResult):
        self.pipeline_result = pipeline_result
        self._df: Optional[pd.DataFrame] = None

    def generate(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        rows = []
        for r in self.pipeline_result.results:
            stages_passed = sum(1 for s in r.stages if s.passed)
            total_stages = len(r.stages)

            stage_passed_list = [s.stage_name for s in r.stages if s.passed]
            fail_reason_list = [f"{s.stage_name}: {s.message}" for s in r.stages if not s.passed and not s.skipped]

            metrics = r.best_metrics or {}
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
                "status": self._compute_status(r),
            }
            rows.append(row)

        self._df = pd.DataFrame(rows)
        return self._df

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

        print(f"\n{'='*120}")
        print(f"Alpha Leaderboard | {self.pipeline_result.timestamp}")
        print(f"{'='*120}")
        print(
            f"{'alpha':<25} {'symbol':<10} {'tf':<5} "
            f"{'PF':>8} {'sharpe':>8} {'trades':>7} "
            f"{'WR':>7} {'avg_ret':>10} {'total_ret':>10} "
            f"{'stages':>7} {'status':>8}"
        )
        print(f"{'-'*118}")

        for _, row in df.iterrows():
            pf_str = f"{row['profit_factor']:.3f}" if pd.notna(row["profit_factor"]) else "nan"
            sh_str = f"{row['sharpe']:.3f}" if pd.notna(row["sharpe"]) else "nan"
            wr_str = f"{row['win_rate']:.3f}" if pd.notna(row["win_rate"]) else "nan"
            ar_str = f"{row['avg_ret']:.5f}" if pd.notna(row["avg_ret"]) else "nan"
            tr_str = f"{row['total_return']:.4f}" if pd.notna(row["total_return"]) else "nan"

            icon = _STATUS_ICONS.get(row["status"], "?")
            stages_str = f"{row['stages_passed']}/{row['total_stages']}"

            print(
                f"{row['alpha']:<25} {row['symbol']:<10} {row['tf']:<5} "
                f"{pf_str:>8} {sh_str:>8} {int(row['trades']):>7} "
                f"{wr_str:>7} {ar_str:>10} {tr_str:>10} "
                f"{stages_str:>7} {icon} {row['status']}"
            )

        print(f"{'='*120}")

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
        else:
            print(f"\n  No active alphas found.")

        print(f"{'='*60}")

    def _build_summary(self) -> dict:
        df = self.generate()
        return {
            "total_results": len(df),
            "by_status": df["status"].value_counts().to_dict(),
            "unique_alphas": list(df["alpha"].unique()),
            "unique_symbols": list(df["symbol"].unique()),
        }
