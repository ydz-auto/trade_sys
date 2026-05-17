"""
Config Manager - 统一配置管理器

整合所有配置功能：
- 配置加载
- 配置验证
- 配置热更新
- 配置版本控制
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

import yaml

from config.loader import Config, get_config
from config.schemas import (
    InfraConfig,
    EnvironmentConfig,
    FeatureFlags,
    RuntimeConfigBase,
    IngestionRuntimeConfig,
    SignalRuntimeConfig,
    ExecutionRuntimeConfig,
    ProjectionRuntimeConfig,
    CorrelationRuntimeConfig,
)
from config.validator import ConfigValidator
from config.watcher import ConfigWatcher


T = TypeVar("T", bound=RuntimeConfigBase)


class ConfigManager:
    """
    统一配置管理器
    
    职责：
    - 加载配置
    - 验证配置
    - 监听配置变化
    - 提供类型化配置访问
    """
    
    def __init__(
        self,
        config_dir: str = None,
        environment: str = None,
        enable_watcher: bool = False,
    ):
        self.config_dir = Path(config_dir or os.environ.get("CONFIG_DIR", "config"))
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        
        self._config: Optional[Config] = None
        self._validator = ConfigValidator()
        self._watcher: Optional[ConfigWatcher] = None
        self._enable_watcher = enable_watcher
        
        self._validation_errors: Dict[str, List[str]] = {}
    
    def load(self) -> "ConfigManager":
        """加载配置"""
        self._config = get_config(str(self.config_dir), self.environment)
        
        raw_config = self._get_raw_config()
        self._validation_errors = self._validator.validate_all(raw_config)
        
        if self._enable_watcher:
            self._watcher = ConfigWatcher(str(self.config_dir))
            self._watcher.on_change(self._on_config_change)
        
        return self
    
    def _get_raw_config(self) -> Dict[str, Any]:
        """获取原始配置"""
        if not self._config:
            return {}
        
        return {
            "environment": self._config.env.environment if self._config._env_config else None,
            "log_level": self._config.env.log_level if self._config._env_config else None,
            "kafka": self._config.infra.kafka.model_dump() if self._config._infra_config else {},
            "redis": self._config.infra.redis.model_dump() if self._config._infra_config else {},
            "clickhouse": self._config.infra.clickhouse.model_dump() if self._config._infra_config else {},
            "postgresql": self._config.infra.postgresql.model_dump() if self._config._infra_config else {},
            "features": self._config.features.model_dump() if self._config._feature_flags else {},
        }
    
    async def _on_config_change(self, changes: List[str]) -> None:
        """配置变化回调"""
        self._config = get_config(str(self.config_dir), self.environment)
        
        raw_config = self._get_raw_config()
        self._validation_errors = self._validator.validate_all(raw_config)
    
    async def start_watcher(self) -> None:
        """启动配置监听"""
        if self._watcher:
            await self._watcher.start()
    
    async def stop_watcher(self) -> None:
        """停止配置监听"""
        if self._watcher:
            await self._watcher.stop()
    
    @property
    def config(self) -> Config:
        """获取配置"""
        if not self._config:
            self.load()
        return self._config
    
    @property
    def infra(self) -> InfraConfig:
        """获取基础设施配置"""
        return self.config.infra
    
    @property
    def features(self) -> FeatureFlags:
        """获取功能开关"""
        return self.config.features
    
    def get_runtime_config(self, runtime_name: str) -> Dict[str, Any]:
        """获取运行时配置"""
        return self.config.runtime(runtime_name)
    
    def get_typed_runtime_config(self, config_class: Type[T]) -> T:
        """获取类型化运行时配置"""
        runtime_name = config_class.__name__.replace("Config", "").lower()
        data = self.get_runtime_config(runtime_name)
        return config_class(**data.get(f"{runtime_name}_runtime", {}))
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """获取策略配置"""
        return self.config.strategy(strategy_name)
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """检查功能是否启用"""
        return self.config.is_feature_enabled(feature_name)
    
    def get_validation_errors(self) -> Dict[str, List[str]]:
        """获取验证错误"""
        return self._validation_errors
    
    def has_validation_errors(self) -> bool:
        """是否有验证错误"""
        return bool(self._validation_errors)
    
    def get_config_version(self) -> Dict[str, Any]:
        """获取配置版本"""
        if self._watcher:
            return self._watcher.get_current_version()
        return {"version": "unknown"}


_config_manager: Optional[ConfigManager] = None


def get_config_manager(
    config_dir: str = None,
    environment: str = None,
    enable_watcher: bool = False,
) -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir, environment, enable_watcher).load()
    return _config_manager


def reload_config_manager() -> ConfigManager:
    """重新加载配置管理器"""
    global _config_manager
    if _config_manager is not None:
        _config_manager.load()
    return _config_manager
