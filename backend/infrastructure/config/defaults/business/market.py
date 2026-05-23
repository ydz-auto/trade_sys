"""
Market 配置 - 业务配置
"""

MARKET_CONFIGS = {
    "market.check_interval": 60,
    "market.regime_threshold": 0.6,
    "market.sentiment_weight": 0.2,
}


MARKET_SCHEMAS = {
    "market.check_interval": {
        "value_type": "int",
        "default": 60,
        "description": "Market check interval in seconds",
        "min_value": 10,
        "max_value": 3600,
    },
    "market.regime_threshold": {
        "value_type": "float",
        "default": 0.6,
        "description": "Market regime detection threshold",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "market.sentiment_weight": {
        "value_type": "float",
        "default": 0.2,
        "description": "Market sentiment weight in decisions",
        "min_value": 0.0,
        "max_value": 1.0,
    },
}
