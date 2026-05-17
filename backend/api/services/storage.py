"""
Storage - Shared In-memory Storage

Mock 模式控制:
  - 环境变量 DASHBOARD_MOCK=true 时返回模拟数据
  - 默认为 false，返回空数据
"""

import os
from datetime import datetime
from typing import Dict, List


_factors: Dict[str, Dict] = {}
_proposals: List[Dict] = []
_snapshots: List[Dict] = []
_factor_lineage: List[Dict] = []


def _is_mock_mode() -> bool:
    """检查是否启用 mock 模式"""
    return os.getenv("DASHBOARD_MOCK", "false").lower() == "true"


def _init_mock_factors():
    """Initialize mock factors data (only in mock mode)"""
    global _factors
    _factors = {
        "trend": {
            "type": "trend",
            "name": "趋势因子",
            "nameEn": "Trend Factor",
            "weight": 0.25,
            "value": 0.65,
            "confidence": 78,
            "color": "blue"
        },
        "momentum": {
            "type": "momentum",
            "name": "动量因子",
            "nameEn": "Momentum Factor",
            "weight": 0.25,
            "value": 0.72,
            "confidence": 82,
            "color": "green"
        },
        "volatility": {
            "type": "volatility",
            "name": "波动率因子",
            "nameEn": "Volatility Factor",
            "weight": 0.20,
            "value": 0.45,
            "confidence": 65,
            "color": "orange"
        },
        "sentiment": {
            "type": "sentiment",
            "name": "情绪因子",
            "nameEn": "Sentiment Factor",
            "weight": 0.15,
            "value": 0.58,
            "confidence": 71,
            "color": "purple"
        },
        "flow": {
            "type": "flow",
            "name": "资金流因子",
            "nameEn": "Flow Factor",
            "weight": 0.15,
            "value": 0.38,
            "confidence": 59,
            "color": "cyan"
        }
    }


if _is_mock_mode():
    _init_mock_factors()


def get_factors():
    return _factors


def get_proposals():
    return _proposals


def get_snapshots():
    return _snapshots


def get_factor_lineage_data():
    return _factor_lineage


def update_factor(factor_type: str, data: Dict):
    """Update factor data"""
    global _factors
    _factors[factor_type] = data


def clear_factors():
    """Clear all factors"""
    global _factors
    _factors = {}


def add_proposal(proposal: Dict):
    """Add a proposal"""
    _proposals.append(proposal)


def clear_proposals():
    """Clear all proposals"""
    global _proposals
    _proposals = []


def add_snapshot(snapshot: Dict):
    """Add a snapshot"""
    _snapshots.append(snapshot)


def add_factor_lineage(lineage: Dict):
    """Add factor lineage"""
    _factor_lineage.append(lineage)
