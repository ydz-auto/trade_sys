"""
Correlation Service 配置 - 业务配置
"""

CORRELATION_CONFIGS = {
    "correlation.symbols": ["BTC", "ETH"],
    "correlation.timeframes": ["1h", "4h"],
    "correlation.interval": 3600,
    "correlation.output_dir": "./data/correlation_results",
    "correlation.kafka.enabled": False,
    "correlation.kafka.topic": "tradeagent.correlation_results",
    "correlation.storage.enabled": True,
}

CORRELATION_SCHEMAS = {
    "correlation.symbols": {
        "value_type": "list",
        "default": ["BTC", "ETH"],
        "description": "Trading symbols for correlation analysis",
    },
    "correlation.timeframes": {
        "value_type": "list",
        "default": ["1h", "4h"],
        "description": "Timeframes for correlation analysis",
        "options": ["1m", "5m", "15m", "1h", "4h", "1d"],
    },
    "correlation.interval": {
        "value_type": "int",
        "default": 3600,
        "description": "Correlation analysis interval in seconds",
        "min_value": 60,
        "max_value": 86400,
    },
    "correlation.output_dir": {
        "value_type": "string",
        "default": "./data/correlation_results",
        "description": "Output directory for correlation results",
    },
    "correlation.kafka.enabled": {
        "value_type": "bool",
        "default": False,
        "description": "Enable Kafka publishing for correlation results",
    },
    "correlation.kafka.topic": {
        "value_type": "string",
        "default": "tradeagent.correlation_results",
        "description": "Kafka topic for correlation results",
    },
    "correlation.storage.enabled": {
        "value_type": "bool",
        "default": True,
        "description": "Enable ClickHouse storage for correlation results",
    },
}
