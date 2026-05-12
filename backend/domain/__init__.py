"""
Domain 模块

每个领域拥有自己的配置定义和 schema
shared/config 只负责配置基础设施（storage, cache, pubsub, versioning）
"""

from domain.risk.config import (
    RiskRuntimeConfig,
    RISK_DEFAULTS,
    RISK_SCHEMA,
)
from domain.strategy.config import (
    StrategyRuntimeConfig,
    STRATEGY_DEFAULTS,
    STRATEGY_SCHEMA,
)
from domain.execution.config import (
    ExecutionRuntimeConfig,
    EXECUTION_DEFAULTS,
    EXECUTION_SCHEMA,
)
from domain.data.config import (
    DataRuntimeConfig,
    DATA_DEFAULTS,
    DATA_SCHEMA,
)

__all__ = [
    "RiskRuntimeConfig",
    "RISK_DEFAULTS",
    "RISK_SCHEMA",
    "StrategyRuntimeConfig",
    "STRATEGY_DEFAULTS",
    "STRATEGY_SCHEMA",
    "ExecutionRuntimeConfig",
    "EXECUTION_DEFAULTS",
    "EXECUTION_SCHEMA",
    "DataRuntimeConfig",
    "DATA_DEFAULTS",
    "DATA_SCHEMA",
]
