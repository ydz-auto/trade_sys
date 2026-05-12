"""
统一配置工厂

整合 Startup Config (pydantic-settings) 和 Runtime Config (ConfigManager)

分层架构:
- Startup Config: 进程启动固定配置，从环境变量加载
- Runtime Config: 运行时动态配置，支持热更新

使用方式:
    from shared.config.factory import get_infra_config, get_runtime_config

    # Startup 配置（固定值）
    kafka_brokers = get_infra_config().kafka.bootstrap_servers

    # Runtime 配置（动态值）
    risk_config = get_runtime_config().get("risk.max_risk_index")
"""

from typing import Optional

from shared.startup.settings import (
    StartupSettings,
    get_startup_settings,
    KafkaSettings,
    RedisSettings,
    PostgresSettings,
    ClickHouseSettings,
    SystemSettings,
    LLMSettings,
    APIKeysSettings,
)
from shared.config.manager import (
    ConfigManager,
    get_config_manager,
)
from shared.config.versioning import (
    ConfigVersioning,
    ConfigSnapshot,
    get_config_versioning,
    create_trading_snapshot,
    create_backtest_snapshot,
)
from shared.config.manager import (
    StrategyConfigManager,
    UserConfigManager,
    DataSourceConfigManager,
    get_strategy_config_manager,
    get_user_config_manager,
    get_datasource_config_manager,
)
from domain.registry import DomainRegistry


class ConfigFactory:
    """
    统一配置工厂

    提供一致的配置访问接口
    """

    _startup_settings: Optional[StartupSettings] = None
    _config_manager: Optional[ConfigManager] = None
    _versioning: Optional[ConfigVersioning] = None

    @classmethod
    def get_infra_config(cls) -> StartupSettings:
        """
        获取基础设施配置（Startup Config）

        这些配置在进程启动时固定
        从环境变量和 .env 文件加载
        """
        if cls._startup_settings is None:
            cls._startup_settings = get_startup_settings()
        return cls._startup_settings

    @classmethod
    def get_runtime_config(cls) -> ConfigManager:
        """
        获取运行时配置管理器（Runtime Config）

        这些配置在运行时可以动态修改
        支持热更新和版本化
        """
        if cls._config_manager is None:
            cls._config_manager = get_config_manager()
        return cls._config_manager

    @classmethod
    def get_versioning(cls) -> ConfigVersioning:
        """获取配置版本化管理器"""
        if cls._versioning is None:
            cls._versioning = get_config_versioning()
        return cls._versioning

    @classmethod
    def get_strategy_config(cls) -> StrategyConfigManager:
        """获取策略配置管理器"""
        return get_strategy_config_manager()

    @classmethod
    def get_user_config(cls) -> UserConfigManager:
        """获取用户配置管理器"""
        return get_user_config_manager()

    @classmethod
    def get_datasource_config(cls) -> DataSourceConfigManager:
        """获取数据源配置管理器"""
        return get_datasource_config_manager()

    @classmethod
    def register_domain_config(cls):
        """
        注册所有领域配置到 ConfigManager
        在应用启动时调用一次
        """
        config_manager = cls.get_runtime_config()

        for domain_name in DomainRegistry.get_all_domains():
            defaults = DomainRegistry.get_defaults(domain_name)
            schema = DomainRegistry.get_schema(domain_name)

            if defaults:
                for key, value in defaults.items():
                    if config_manager.get(key) is None:
                        config_manager.set(key, value, reason=f"Initialize {domain_name} config")

    @classmethod
    def create_trading_snapshot(cls, **kwargs) -> ConfigSnapshot:
        """创建交易配置快照"""
        return create_trading_snapshot(**kwargs)

    @classmethod
    def create_backtest_snapshot(cls, **kwargs) -> ConfigSnapshot:
        """创建回测配置快照"""
        return create_backtest_snapshot(**kwargs)

    @classmethod
    def reset(cls):
        """重置所有配置实例"""
        cls._startup_settings = None
        cls._config_manager = None
        cls._versioning = None


def get_infra_config() -> StartupSettings:
    """获取基础设施配置"""
    return ConfigFactory.get_infra_config()


def get_runtime_config() -> ConfigManager:
    """获取运行时配置管理器"""
    return ConfigFactory.get_runtime_config()


def get_versioning() -> ConfigVersioning:
    """获取配置版本化管理器"""
    return ConfigFactory.get_versioning()


def get_strategy_config() -> StrategyConfigManager:
    """获取策略配置管理器"""
    return ConfigFactory.get_strategy_config()


def get_user_config() -> UserConfigManager:
    """获取用户配置管理器"""
    return ConfigFactory.get_user_config()


def get_datasource_config() -> DataSourceConfigManager:
    """获取数据源配置管理器"""
    return ConfigFactory.get_datasource_config()


def initialize_config():
    """
    初始化配置系统
    在应用启动时调用一次
    """
    ConfigFactory.get_infra_config()
    ConfigFactory.register_domain_config()
