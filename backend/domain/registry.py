"""
Domain 配置注册表

管理所有 domain 配置的注册和访问
确保配置边界清晰，不允许跨 bounded context 访问
"""

from typing import Dict, List, Optional, Type
from pydantic import BaseModel

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


class DomainRegistry:
    """
    领域配置注册表
    确保配置边界清晰
    """

    _domains: Dict[str, Dict] = {}

    @classmethod
    def register(cls, domain_name: str, config_class: Type[BaseModel],
                 defaults: Dict, schema: Dict):
        """注册领域配置"""
        cls._domains[domain_name] = {
            "class": config_class,
            "defaults": defaults,
            "schema": schema,
        }

    @classmethod
    def get_defaults(cls, domain_name: str) -> Optional[Dict]:
        """获取领域默认值"""
        domain = cls._domains.get(domain_name)
        return domain["defaults"] if domain else None

    @classmethod
    def get_schema(cls, domain_name: str) -> Optional[Dict]:
        """获取领域 schema"""
        domain = cls._domains.get(domain_name)
        return domain["schema"] if domain else None

    @classmethod
    def get_config_class(cls, domain_name: str) -> Optional[Type[BaseModel]]:
        """获取领域配置类"""
        domain = cls._domains.get(domain_name)
        return domain["class"] if domain else None

    @classmethod
    def get_all_domains(cls) -> List[str]:
        """获取所有领域名称"""
        return list(cls._domains.keys())

    @classmethod
    def get_all_defaults(cls) -> Dict:
        """合并所有领域默认值"""
        all_defaults = {}
        for domain_defaults in cls._domains.values():
            all_defaults.update(domain_defaults["defaults"])
        return all_defaults

    @classmethod
    def get_all_schemas(cls) -> Dict:
        """合并所有领域 schema"""
        all_schemas = {}
        for domain_schema in cls._domains.values():
            all_schemas.update(domain_schema["schema"])
        return all_schemas


DomainRegistry.register("risk", RiskRuntimeConfig, RISK_DEFAULTS, RISK_SCHEMA)
DomainRegistry.register("strategy", StrategyRuntimeConfig, STRATEGY_DEFAULTS, STRATEGY_SCHEMA)
DomainRegistry.register("execution", ExecutionRuntimeConfig, EXECUTION_DEFAULTS, EXECUTION_SCHEMA)
DomainRegistry.register("data", DataRuntimeConfig, DATA_DEFAULTS, DATA_SCHEMA)


__all__ = [
    "DomainRegistry",
    "RiskRuntimeConfig",
    "StrategyRuntimeConfig",
    "ExecutionRuntimeConfig",
    "DataRuntimeConfig",
]
