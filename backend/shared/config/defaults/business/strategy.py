"""
Strategy 配置 - 业务配置
"""

STRATEGY_CONFIGS = {
    "strategy.momentum_weight": 0.3,
    "strategy.trend_weight": 0.3,
    "strategy.flow_weight": 0.2,
    "strategy.sentiment_weight": 0.2,
}


STRATEGY_SCHEMAS = {
    "strategy.momentum_weight": {
        "value_type": "float",
        "default": 0.3,
        "description": "Momentum factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "strategy.trend_weight": {
        "value_type": "float",
        "default": 0.3,
        "description": "Trend factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "strategy.flow_weight": {
        "value_type": "float",
        "default": 0.2,
        "description": "Flow factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
    "strategy.sentiment_weight": {
        "value_type": "float",
        "default": 0.2,
        "description": "Sentiment factor weight",
        "min_value": 0.0,
        "max_value": 1.0,
    },
}
