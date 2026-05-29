"""
Paper Trading Config Generator - 从 Pipeline 结果生成 Paper Trading 配置

为 Tier A/B 候选生成可直接使用的 Paper Trading 配置文件。

输出：
  reports/alpha/paper_trading/
  ├── paper_trading_config.json
  ├── ETCUSDT_funding_extreme_reversal.json
  ├── ETCUSDT_drawdown_dip_buying.json
  ├── SOLUSDT_ret_5_reversal.json
  └── ZECUSDT_ret_5_reversal.json
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.pipeline import AlphaPipelineResult, AlphaValidationResult


@dataclass
class AlphaTradingConfig:
    symbol: str
    alpha_name: str
    direction: str
    threshold: float
    holding_bars: int
    timeframe: str
    exchange: str
    tier: str
    fee_taker: float
    fee_maker: float
    initial_capital: float
    max_position_size: float
    is_metrics: Dict[str, Any]
    wf_metrics: Dict[str, Any]
    stab_metrics: Dict[str, Any]
    created_at: str = ""
    mode: str = "paper"

    def to_dict(self) -> Dict:
        return asdict(self)


def generate_paper_trading_configs(
    pipeline_result: AlphaPipelineResult,
    output_dir: str = "reports/alpha/paper_trading",
    tiers: Optional[List[str]] = None,
    initial_capital: float = 10000.0,
    max_position_pct: float = 0.1,
    require_strict: bool = True,  # Strict mode: requires IS + WF + Stability all passed
) -> List[AlphaTradingConfig]:
    if tiers is None:
        tiers = ["A"]

    output_path = BACKEND_ROOT / output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    configs = []
    rejected_reasons = []

    for r in pipeline_result.results:
        if r.best_params is None:
            rejected_reasons.append(f"{r.symbol}/{r.strategy}: No best params")
            continue

        row_data = _extract_result_data(r)
        tier = _classify_tier(row_data)

        # Strict mode: must pass WF and Stability
        if require_strict:
            wf_data = _extract_stage_data(r, "walk_forward")
            stab_data = _extract_stage_data(r, "parameter_stability")
            
            wf_passed = wf_data.get("_passed", False)
            stab_passed = stab_data.get("_passed", False)
            wf_skipped = wf_data.get("total_windows", 0) == 0
            stab_skipped = len(stab_data) <= 1  # Only has _passed key, no other data
            
            if not (wf_passed or wf_skipped):
                rejected_reasons.append(f"{r.symbol}/{r.strategy}: Walk-forward failed")
                continue
                
            if not (stab_passed or stab_skipped):
                rejected_reasons.append(f"{r.symbol}/{r.strategy}: Stability failed")
                continue

        if tier not in tiers:
            rejected_reasons.append(f"{r.symbol}/{r.strategy}: Tier {tier} not in {tiers}")
            continue

        config = AlphaTradingConfig(
            symbol=r.symbol,
            alpha_name=r.strategy,
            direction=r.best_params.get("direction", "long"),
            threshold=r.best_params.get("threshold", 0.0),
            holding_bars=r.best_params.get("holding_bars", 5),
            timeframe=r.timeframe if r.timeframe else "1h",
            exchange=pipeline_result.config.get("exchange", "binance"),
            tier=tier,
            fee_taker=pipeline_result.config.get("taker_fee", 0.0005),
            fee_maker=pipeline_result.config.get("maker_fee", 0.0002),
            initial_capital=initial_capital,
            max_position_size=max_position_pct,
            is_metrics=r.best_metrics or {},
            wf_metrics=_extract_stage_data(r, "walk_forward"),
            stab_metrics=_extract_stage_data(r, "parameter_stability"),
            created_at=datetime.now().isoformat(),
            mode="paper",
        )

        configs.append(config)

        config_path = output_path / f"{r.symbol}_{r.strategy}.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, default=str, ensure_ascii=False)
        print(f"  Saved {config_path.name}")

    master_config = {
        "created_at": datetime.now().isoformat(),
        "mode": "paper",
        "total_candidates": len(configs),
        "tiers_included": tiers,
        "initial_capital_per_strategy": initial_capital,
        "max_position_pct": max_position_pct,
        "candidates": [c.to_dict() for c in configs],
    }

    master_path = output_path / "paper_trading_config.json"
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(master_config, f, indent=2, default=str, ensure_ascii=False)
    print(f"\n  Saved master config: {master_path.name}")

    _print_paper_trading_summary(configs, rejected_reasons)

    return configs


def _extract_result_data(r: AlphaValidationResult) -> Dict:
    metrics = r.best_metrics or {}
    wf_data = _extract_stage_data(r, "walk_forward")
    stab_data = _extract_stage_data(r, "parameter_stability")

    return {
        "profit_factor": metrics.get("profit_factor", 0),
        "sharpe": metrics.get("sharpe", 0),
        "status": r.final_status,
        "wf_passed": wf_data.get("_passed", False),
        "stab_passed": stab_data.get("_passed", False),
        "wf_windows": wf_data.get("total_windows", 0),
    }


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


def _print_paper_trading_summary(configs: List[AlphaTradingConfig], rejected_reasons: List[str]):
    print(f"\n{'='*70}")
    print(f"Paper Trading Configuration Summary")
    print(f"{'='*70}")
    print(f"  Accepted candidates: {len(configs)}")
    print(f"  Rejected: {len(rejected_reasons)}")

    by_symbol: Dict[str, List[AlphaTradingConfig]] = {}
    for c in configs:
        by_symbol.setdefault(c.symbol, []).append(c)

    if configs:
        print(f"\n  ✅ Accepted:")
        for symbol, symbol_configs in sorted(by_symbol.items()):
            print(f"\n  {symbol}:")
            for c in symbol_configs:
                print(
                    f"    {c.alpha_name} | "
                    f"dir={c.direction} | "
                    f"thresh={c.threshold:.5f} | "
                    f"hold={c.holding_bars} | "
                    f"tier={c.tier}"
                )

    if rejected_reasons:
        print(f"\n  ❌ Rejected (sample):")
        for reason in rejected_reasons[:20]:  # Show first 20
            print(f"    {reason}")
        if len(rejected_reasons) > 20:
            print(f"    ... and {len(rejected_reasons)-20} more")

    print(f"\n{'='*70}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Paper Trading Config Generator")
    parser.add_argument("--leaderboard", type=str, required=True,
                        help="Path to leaderboard JSON from pipeline")
    parser.add_argument("--tiers", type=str, default="A,B",
                        help="Comma-separated tiers to include (default: A,B)")
    parser.add_argument("--output-dir", type=str, default="reports/alpha/paper_trading",
                        help="Output directory")
    parser.add_argument("--capital", type=float, default=10000.0,
                        help="Initial capital per strategy")
    parser.add_argument("--max-position", type=float, default=0.1,
                        help="Max position size as fraction of capital")

    args = parser.parse_args()

    lb_path = Path(args.leaderboard)
    if not lb_path.exists():
        print(f"Error: Leaderboard file not found: {lb_path}")
        return

    with open(lb_path, "r", encoding="utf-8") as f:
        lb_data = json.load(f)

    print(f"Paper Trading Config Generator")
    print(f"  Leaderboard: {lb_path}")
    print(f"  Tiers: {args.tiers}")
    print(f"  Capital: {args.capital}")
    print(f"  Max Position: {args.max_position}")

    from research.alpha.pipeline import AlphaPipelineResult

    results = []
    for r_dict in lb_data.get("results", []):
        stages = []
        for s_dict in r_dict.get("stages", []):
            from research.alpha.pipeline import StageResult
            stages.append(StageResult(
                stage_name=s_dict["stage_name"],
                passed=s_dict["passed"],
                data={},
                message=s_dict.get("message", ""),
                skipped=s_dict.get("skipped", False),
            ))

        from research.alpha.pipeline import AlphaValidationResult
        results.append(AlphaValidationResult(
            strategy=r_dict["strategy"],
            symbol=r_dict["symbol"],
            timeframe=r_dict["timeframe"],
            stages=stages,
            final_status=r_dict["final_status"],
            best_params=r_dict.get("best_params"),
            best_metrics=r_dict.get("best_metrics"),
        ))

    pipeline_result = AlphaPipelineResult(
        results=results,
        config=lb_data.get("config", {}),
        timestamp=lb_data.get("timestamp", ""),
    )

    tiers = [t.strip() for t in args.tiers.split(",")]
    generate_paper_trading_configs(
        pipeline_result,
        output_dir=args.output_dir,
        tiers=tiers,
        initial_capital=args.capital,
        max_position_pct=args.max_position,
    )


if __name__ == "__main__":
    main()
