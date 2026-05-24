"""
Trading 配置 - 业务配置
"""

TRADING_CONFIGS = {
    "trading.default_leverage": 3,
    "trading.max_position_pct": 0.3,
    "trading.default_stop_loss_pct": 0.02,
    "trading.default_take_profit_pct": 0.06,
    "trading.max_daily_loss_pct": 0.05,
    "trading.order_timeout_seconds": 30,
}


TRADING_SCHEMAS = {
    "trading.default_leverage": {
        "value_type": "int",
        "default": 3,
        "description": "Default leverage for new positions",
        "min_value": 1,
        "max_value": 125,
        "required": True,
    },
    "trading.max_position_pct": {
        "value_type": "float",
        "default": 0.3,
        "description": "Maximum position size as percentage of portfolio",
        "min_value": 0.0,
        "max_value": 1.0,
        "required": True,
    },
    "trading.default_stop_loss_pct": {
        "value_type": "float",
        "default": 0.02,
        "description": "Default stop loss percentage",
        "min_value": 0.001,
        "max_value": 0.5,
    },
    "trading.default_take_profit_pct": {
        "value_type": "float",
        "default": 0.06,
        "description": "Default take profit percentage",
        "min_value": 0.001,
        "max_value": 1.0,
    },
    "trading.max_daily_loss_pct": {
        "value_type": "float",
        "default": 0.05,
        "description": "Maximum daily loss percentage",
        "min_value": 0.001,
        "max_value": 0.5,
    },
    "trading.order_timeout_seconds": {
        "value_type": "int",
        "default": 30,
        "description": "Order timeout in seconds",
        "min_value": 5,
        "max_value": 300,
    },
}
