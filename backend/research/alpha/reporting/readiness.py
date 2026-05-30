"""
Production Readiness Classification

根据 Walk Forward + Parameter Stability 结果，对 alpha 候选进行生产就绪分级。

分级体系：
  READY             WF pass + 1D stable + 2D stable + stab_passed
  CONDITIONAL_READY WF pass + (1D stable OR 2D stable) + stab_score >= 0.5
  WF_ONLY           WF pass，但没有稳定参数区域
  STAB_ONLY         Stability pass，但 WF 不通过
  UNSTABLE          WF 和 Stability 都不通过
  REJECTED          IC/signal/WF fail 或 trades < MINIMUM_TRADES
"""

from typing import Dict, Any, List

import pandas as pd


MINIMUM_TRADES = 50

READINESS_ICONS = {
    "READY": "\U0001f7e2",
    "CONDITIONAL_READY": "\U0001f7e0",
    "WF_ONLY": "\U0001f7e1",
    "STAB_ONLY": "\U0001f7e1",
    "UNSTABLE": "\U0001f534",
    "REJECTED": "\u274c",
}


def classify_production_readiness(row) -> str:
    if row["final_status"] not in ("pass", "warning"):
        return "REJECTED"

    trades = row.get("trades")
    if pd.notna(trades) and int(trades) < MINIMUM_TRADES:
        return "REJECTED"

    wf_ok = bool(row.get("wf_passed", False))
    stab_ok = bool(row.get("stab_passed", False))
    is_1d_stable = bool(row.get("stab_is_1d_stable", False))
    is_2d_stable = bool(row.get("stab_is_2d_stable", False))
    stab_score = float(row.get("stab_stability_score", 0) or 0)

    if wf_ok and stab_ok:
        return "READY"
    elif wf_ok and is_1d_stable and stab_score >= 0.5:
        return "CONDITIONAL_READY"
    elif wf_ok and is_2d_stable and stab_score >= 0.5:
        return "CONDITIONAL_READY"
    elif wf_ok:
        return "WF_ONLY"
    elif stab_ok:
        return "STAB_ONLY"
    else:
        return "UNSTABLE"


def generate_paper_trading_config(
    leaderboard: pd.DataFrame,
    timeframe: str = "1h",
    exchange: str = "binance",
    feature_source: str = "engine_standalone",
    days: int = 365,
) -> Dict[str, Any]:
    ready = leaderboard[
        leaderboard["production_readiness"].isin(["READY", "CONDITIONAL_READY"])
    ]

    configs = []
    for _, row in ready.iterrows():
        readiness = row["production_readiness"]
        config = {
            "strategy": row["strategy"],
            "symbol": row["symbol"],
            "timeframe": timeframe,
            "exchange": exchange,
            "direction": row["direction"],
            "readiness": readiness,
            "threshold": float(row["threshold"]) if pd.notna(row["threshold"]) else None,
            "holding_bars": int(row["holding_bars"]) if pd.notna(row["holding_bars"]) else None,
            "profit_factor": float(row["profit_factor"]) if pd.notna(row["profit_factor"]) else None,
            "sharpe": float(row["sharpe"]) if pd.notna(row["sharpe"]) else None,
            "win_rate": float(row["win_rate"]) if pd.notna(row["win_rate"]) else None,
            "wf_avg_sharpe": float(row["wf_avg_sharpe"]) if pd.notna(row["wf_avg_sharpe"]) else None,
            "wf_profitable_window_ratio": float(row["wf_profitable_window_ratio"]) if pd.notna(row["wf_profitable_window_ratio"]) else None,
        }

        for col in ("profitable_area_ratio", "stable_area_ratio", "largest_region_ratio",
                     "needle_peak_ratio", "mean_sharpe", "std_sharpe", "cv"):
            val = row.get(col)
            if pd.notna(val):
                config[col] = float(val)

        stab_score = row.get("stab_stability_score")
        if pd.notna(stab_score):
            config["stability_score"] = float(stab_score)

        configs.append(config)

    return {
        "generated_at": pd.Timestamp.now().isoformat(),
        "feature_source": feature_source,
        "days": days,
        "total_candidates": len(ready),
        "candidates": configs,
    }
