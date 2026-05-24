"""
System 配置
"""

SYSTEM_CONFIGS = {
    "system.mode": "PAPER",
    "system.allow_trading": True,
    "system.auto_restart": False,
    "system.log_level": "INFO",
}


SYSTEM_SCHEMAS = {
    "system.mode": {
        "value_type": "string",
        "default": "PAPER",
        "description": "System operation mode",
        "options": ["LIVE", "PAPER", "BACKTEST"],
        "required": True,
    },
    "system.allow_trading": {
        "value_type": "bool",
        "default": True,
        "description": "Allow trading operations",
        "required": True,
    },
    "system.auto_restart": {
        "value_type": "bool",
        "default": False,
        "description": "Auto restart on failure",
    },
    "system.log_level": {
        "value_type": "string",
        "default": "INFO",
        "description": "Logging level",
        "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
    },
}