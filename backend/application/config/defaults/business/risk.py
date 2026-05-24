"""
Risk 配置 - 业务配置
"""

RISK_CONFIGS = {
    "risk.max_risk_index": 80,
    "risk.max_drawdown_pct": 0.08,
    "risk.max_consecutive_losses": 3,
    "risk.auto_pause_on_high_risk": True,
}


RISK_SCHEMAS = {
    "risk.max_risk_index": {
        "value_type": "int",
        "default": 80,
        "description": "Maximum risk index before pausing trading",
        "min_value": 0,
        "max_value": 100,
        "required": True,
    },
    "risk.max_drawdown_pct": {
        "value_type": "float",
        "default": 0.08,
        "description": "Maximum drawdown percentage",
        "min_value": 0.0,
        "max_value": 1.0,
        "required": True,
    },
    "risk.max_consecutive_losses": {
        "value_type": "int",
        "default": 3,
        "description": "Maximum consecutive losses before pause",
        "min_value": 1,
        "max_value": 10,
    },
    "risk.auto_pause_on_high_risk": {
        "value_type": "bool",
        "default": True,
        "description": "Auto pause trading on high risk",
    },
}
