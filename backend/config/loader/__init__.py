"""
Config Loader - 统一配置加载器

配置五层化：
1. Infrastructure Config - 基础设施配置
2. Runtime Config - 运行时配置
3. Strategy Config - 策略配置
4. Feature Flags - 功能开关
5. Secrets - 密钥配置

用法:
    from config.loader import get_config
    
    config = get_config()
    kafka_servers = config.infra.kafka.bootstrap_servers
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from dataclasses import dataclass, field

import yaml
from pydantic import BaseModel, Field


T = TypeVar("T", bound=BaseModel)


def expand_env_vars(value: Any) -> Any:
    """展开环境变量"""
    if isinstance(value, str):
        pattern = r"\$\{([^}]+)\}"
        
        def replace(match):
            var_spec = match.group(1)
            if ":-" in var_spec:
                var_name, default = var_spec.split(":-", 1)
                return os.environ.get(var_name, default)
            elif ":" in var_spec:
                var_name, default = var_spec.split(":", 1)
                return os.environ.get(var_name, default)
            else:
                return os.environ.get(var_spec, match.group(0))
        
        return re.sub(pattern, replace, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


class KafkaConfig(BaseModel):
    bootstrap_servers: str = "localhost:9092"
    consumer_config: Dict[str, Any] = Field(default_factory=dict)
    producer_config: Dict[str, Any] = Field(default_factory=dict)


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379/0"
    max_connections: int = 100
    connection_timeout: int = 5
    socket_timeout: int = 5


class ClickHouseConfig(BaseModel):
    host: str = "localhost"
    port: int = 9000
    http_port: int = 8123
    database: str = "tradeagent"
    user: str = "default"
    password: str = ""
    connection_timeout: int = 10
    send_receive_timeout: int = 300


class PostgreSQLConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str = "tradeagent"
    user: str = "postgres"
    password: str = "postgres"
    min_connections: int = 5
    max_connections: int = 20


class ObservabilityConfig(BaseModel):
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    jaeger_enabled: bool = True
    jaeger_endpoint: str = "http://localhost:4317"


class DataLakeStorageConfig(BaseModel):
    smb_host: str = "192.168.1.14"
    smb_share: str = "00_crypto"
    smb_path: str = "00_code/backend/data_lake"
    local_path: str = "./data_lake"
    use_smb: bool = True
    
    @property
    def smb_url(self) -> str:
        return f"smb://{self.smb_host}/{self.smb_share}/{self.smb_path}"
    
    @property
    def effective_path(self) -> str:
        if self.use_smb:
            return self.smb_url
        return self.local_path


class InfraConfig(BaseModel):
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    clickhouse: ClickHouseConfig = Field(default_factory=ClickHouseConfig)
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    data_lake: DataLakeStorageConfig = Field(default_factory=DataLakeStorageConfig)


class EnvironmentConfig(BaseModel):
    environment: str = "dev"
    debug: bool = False
    log_level: str = "INFO"
    infra: InfraConfig = Field(default_factory=InfraConfig)


class FeatureFlags(BaseModel):
    enable_llm: bool = False
    enable_replay: bool = True
    enable_projection: bool = True
    enable_shadow_execution: bool = False
    enable_narrative: bool = False
    experimental: Dict[str, bool] = Field(default_factory=dict)
    safety: Dict[str, bool] = Field(default_factory=dict)
    observability: Dict[str, bool] = Field(default_factory=dict)


class Config:
    """
    统一配置管理器
    
    配置层级：
    1. Environment Config - 环境配置
    2. Infra Config - 基础设施配置
    3. Runtime Config - 运行时配置
    4. Strategy Config - 策略配置
    5. Feature Flags - 功能开关
    """
    
    def __init__(self, config_dir: str = None, environment: str = None):
        self.config_dir = Path(config_dir or os.environ.get("CONFIG_DIR", "config"))
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        
        self._env_config: Optional[EnvironmentConfig] = None
        self._infra_config: Optional[InfraConfig] = None
        self._runtime_configs: Dict[str, Any] = {}
        self._strategy_configs: Dict[str, Any] = {}
        self._feature_flags: Optional[FeatureFlags] = None
        
        self._loaded = False
    
    def load(self) -> "Config":
        """加载所有配置"""
        self._load_environment()
        self._load_infra()
        self._load_runtime()
        self._load_strategy()
        self._load_feature_flags()
        self._loaded = True
        return self
    
    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """加载 YAML 文件"""
        if not path.exists():
            return {}
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        return expand_env_vars(data)
    
    def _load_environment(self) -> None:
        """加载环境配置"""
        env_path = self.config_dir / "environments" / f"{self.environment}.yaml"
        data = self._load_yaml(env_path)
        self._env_config = EnvironmentConfig(**data)
    
    def _load_infra(self) -> None:
        """加载基础设施配置"""
        infra_path = self.config_dir / "infra" / "infra.yaml"
        data = self._load_yaml(infra_path)
        
        if self._env_config and hasattr(self._env_config, "infra"):
            merged = {**self._env_config.infra.model_dump(), **data}
            self._infra_config = InfraConfig(**merged)
        else:
            self._infra_config = InfraConfig(**data)
    
    def _load_runtime(self) -> None:
        """加载运行时配置"""
        runtime_dir = self.config_dir / "runtime"
        if not runtime_dir.exists():
            return
        
        for yaml_file in runtime_dir.glob("*.yaml"):
            runtime_name = yaml_file.stem
            data = self._load_yaml(yaml_file)
            self._runtime_configs[runtime_name] = data
    
    def _load_strategy(self) -> None:
        """加载策略配置"""
        strategy_dir = self.config_dir / "strategy"
        if not strategy_dir.exists():
            return
        
        for yaml_file in strategy_dir.glob("*.yaml"):
            strategy_name = yaml_file.stem
            data = self._load_yaml(yaml_file)
            self._strategy_configs[strategy_name] = data
    
    def _load_feature_flags(self) -> None:
        """加载功能开关"""
        flags_path = self.config_dir / "feature_flags" / "flags.yaml"
        data = self._load_yaml(flags_path)
        self._feature_flags = FeatureFlags(**data.get("features", {}))
    
    @property
    def env(self) -> EnvironmentConfig:
        """获取环境配置"""
        if not self._loaded:
            self.load()
        return self._env_config
    
    @property
    def infra(self) -> InfraConfig:
        """获取基础设施配置"""
        if not self._loaded:
            self.load()
        return self._infra_config
    
    def runtime(self, name: str) -> Dict[str, Any]:
        """获取运行时配置"""
        if not self._loaded:
            self.load()
        return self._runtime_configs.get(name, {})
    
    def strategy(self, name: str) -> Dict[str, Any]:
        """获取策略配置"""
        if not self._loaded:
            self.load()
        return self._strategy_configs.get(name, {})
    
    @property
    def features(self) -> FeatureFlags:
        """获取功能开关"""
        if not self._loaded:
            self.load()
        return self._feature_flags
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """检查功能是否启用"""
        if not self._loaded:
            self.load()
        
        if hasattr(self._feature_flags, feature_name):
            return getattr(self._feature_flags, feature_name)
        
        return self._feature_flags.experimental.get(feature_name, False)
    
    def get_runtime_config(self, runtime_name: str, config_class: Type[T]) -> T:
        """获取类型化的运行时配置"""
        data = self.runtime(runtime_name)
        return config_class(**data.get(f"{runtime_name}_runtime", {}))


_config: Optional[Config] = None


def get_config(config_dir: str = None, environment: str = None) -> Config:
    """获取配置单例"""
    global _config
    if _config is None:
        _config = Config(config_dir, environment).load()
    return _config


def reload_config() -> Config:
    """重新加载配置"""
    global _config
    if _config is not None:
        _config._loaded = False
        _config.load()
    return _config
