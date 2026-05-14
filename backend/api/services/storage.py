"""
Storage - Shared In-memory Storage
"""
from datetime import datetime
from typing import Dict, List


_factors: Dict[str, Dict] = {}
_proposals: List[Dict] = []
_snapshots: List[Dict] = [
    {
        "id": "snap_001",
        "timestamp": datetime.now().isoformat(),
        "name": "Initial System State",
        "type": "auto",
        "data": {},
        "description": "Initial system startup snapshot"
    }
]
_factor_lineage: List[Dict] = []


def init_factors():
    """Initialize factors data"""
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


init_factors()


def get_factors():
    return _factors


def get_proposals():
    return _proposals


def get_snapshots():
    return _snapshots


def get_factor_lineage_data():
    return _factor_lineage
