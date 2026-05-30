"""
Alpha Family Registry

预定义的 Alpha 家族分类，用于和聚类结果自动比对。

家族定义基于金融逻辑（而非数据驱动），回答：
  "这些 Alpha 从理论上应该属于同一族吗？"
"""

from typing import Dict, List, Tuple

ALPHA_FAMILIES: Dict[str, List[str]] = {
    "reversal": [
        "ret_1_reversal",
        "ret_3_reversal",
        "ret_5_reversal",
        "ret_10_reversal",
        "drawdown_dip_buying",
        "drawdown_ret5_combo",
        "ret_5_positive_reversal",
    ],
    "exhaustion": [
        "volume_exhaustion",
        "volatility_panic_reversal",
        "range_exhaustion",
        "atr_expansion_reversal",
    ],
    "crowding": [
        "funding_extreme_reversal",
        "funding_trap_short",
        "short_squeeze_simplified",
        "crowded_long_reversal",
        "oi_behavior",
        "oi_squeeze_long",
        "leverage_crowded_short",
        "oi_funding_divergence_long",
    ],
    "parabolic": [
        "parabolic_runup",
        "parabolic_runup_vol_filter",
        "parabolic_runup_ma_filter",
        "parabolic_runup_breakout_filter",
        "parabolic_runup_combined",
        "parabolic_blowoff",
    ],
    "breakout": [
        "breakout_failure",
        "failed_breakout",
    ],
    "volume_climax": [
        "volume_climax_short",
    ],
    "trend": [
        "trend_filter_long",
        "trend_exhaustion",
    ],
    "overbought": [
        "distance_from_high_short",
    ],
}


def match_clusters_to_families(
    clusters: Dict[str, List[str]],
) -> List[Dict]:
    """
    将数据驱动的聚类结果与预定义家族比对。

    Returns:
        [
            {
                "cluster": "cluster_1",
                "members": ["ret_3_reversal", "ret_5_reversal", ...],
                "best_family_match": "reversal",
                "match_ratio": 0.85,
                "family_overlap": {
                    "reversal": 0.85,
                    "exhaustion": 0.14,
                    ...
                }
            },
            ...
        ]
    """
    results = []

    for cluster_name, members in clusters.items():
        family_overlap: Dict[str, float] = {}

        for family_name, family_members in ALPHA_FAMILIES.items():
            overlap = len(set(members) & set(family_members))
            if len(members) > 0:
                family_overlap[family_name] = round(overlap / len(members), 4)
            else:
                family_overlap[family_name] = 0.0

        best_family = max(family_overlap, key=family_overlap.get) if family_overlap else "unknown"
        best_ratio = family_overlap.get(best_family, 0.0)

        results.append({
            "cluster": cluster_name,
            "members": members,
            "best_family_match": best_family,
            "match_ratio": best_ratio,
            "family_overlap": family_overlap,
        })

    results.sort(key=lambda x: len(x["members"]), reverse=True)

    return results
