"""
Config Schemas - 配置模型定义

所有配置的 Pydantic 模型，确保类型安全。
"""

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class KafkaConfig(BaseModel):
    """Kafka 配置"""
    bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    consumer_config: Dict[str, Any] = Field(default_factory=lambda: {
        "auto_offset_reset": "latest",
        "enable_auto_commit": True,
        "max_poll_records": 1000,
        "session_timeout_ms": 30000,
    })
    producer_config: Dict[str, Any] = Field(default_factory=lambda: {
        "acks": "all",
        "retries": 3,
        "batch_size": 16384,
        "linger_ms": 5,
    })


class RedisConfig(BaseModel):
    """Redis 配置"""
    url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    max_connections: int = 100
    connection_timeout: int = 5
    socket_timeout: int = 5


class ClickHouseConfig(BaseModel):
    """ClickHouse 配置"""
    host: str = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port: int = 9000
    http_port: int = 8123
    database: str = os.environ.get("CLICKHOUSE_DATABASE", "tradeagent")
    user: str = os.environ.get("CLICKHOUSE_USERNAME", "default")
    password: str = os.environ.get("CLICKHOUSE_PASSWORD", "")
    connection_timeout: int = 10
    send_receive_timeout: int = 300


class PostgreSQLConfig(BaseModel):
    """PostgreSQL 配置"""
    host: str = os.environ.get("POSTGRES_HOST", "localhost")
    port: int = 5432
    database: str = os.environ.get("POSTGRES_DATABASE", "tradeagent")
    user: str = os.environ.get("POSTGRES_USERNAME", "postgres")
    password: str = os.environ.get("POSTGRES_PASSWORD", "postgres")
    min_connections: int = 5
    max_connections: int = 20


class ObservabilityConfig(BaseModel):
    """可观测性配置"""
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    jaeger_enabled: bool = True
    jaeger_endpoint: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")


class DataLakeStorageConfig(BaseModel):
    """数据湖存储配置"""
    smb_host: str = os.environ.get("DATA_LAKE_SMB_HOST", "192.168.1.14")
    smb_share: str = os.environ.get("DATA_LAKE_SMB_SHARE", "00_crypto")
    smb_path: str = os.environ.get("DATA_LAKE_SMB_PATH", "00_code/backend/data_lake")
    local_path: str = os.environ.get("DATA_LAKE_LOCAL_PATH", "./data_lake")
    use_smb: bool = os.environ.get("DATA_LAKE_USE_SMB", "false").lower() == "true"
    
    @property
    def smb_url(self) -> str:
        """获取完整的 SMB URL"""
        return f"smb://{self.smb_host}/{self.smb_share}/{self.smb_path}"
    
    @property
    def effective_path(self) -> str:
        """获取有效路径（根据 use_smb 决定使用 SMB 还是本地路径）"""
        if self.use_smb:
            return self.smb_url
        return self.local_path


class InfraConfig(BaseModel):
    """基础设施配置"""
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    clickhouse: ClickHouseConfig = Field(default_factory=ClickHouseConfig)
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    data_lake: DataLakeStorageConfig = Field(default_factory=DataLakeStorageConfig)


class EnvironmentConfig(BaseModel):
    """环境配置"""
    environment: str = "dev"
    debug: bool = False
    log_level: str = "INFO"
    
    @validator("environment")
    def validate_environment(cls, v):
        allowed = ["dev", "prod", "staging", "replay"]
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v


class FeatureFlags(BaseModel):
    """功能开关"""
    enable_llm: bool = False
    enable_replay: bool = True
    enable_projection: bool = True
    enable_shadow_execution: bool = False
    enable_narrative: bool = False
    experimental: Dict[str, bool] = Field(default_factory=dict)
    safety: Dict[str, bool] = Field(default_factory=lambda: {
        "enable_circuit_breaker": True,
        "enable_rate_limit": True,
        "enable_position_guard": True,
    })
    observability: Dict[str, bool] = Field(default_factory=lambda: {
        "enable_detailed_metrics": True,
        "enable_tracing": True,
        "enable_profiling": False,
    })


class RuntimeConfigBase(BaseModel):
    """Runtime 配置基类"""
    name: str
    version: str = "1.0.0"
    enabled: bool = True
    
    kafka_bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    
    shutdown_timeout: int = 30
    health_check_interval: int = 10


class IngestionRuntimeConfig(RuntimeConfigBase):
    """Ingestion Runtime 配置"""
    name: str = "ingestion_runtime"
    collection_interval: int = 300
    symbols: List[str] = Field(default_factory=lambda: ["BTC", "ETH"])
    news_sources: List[str] = Field(default_factory=lambda: ["coindesk", "cointelegraph"])


class SignalRuntimeConfig(RuntimeConfigBase):
    """Signal Runtime 配置"""
    name: str = "signal_runtime"
    fusion_window_seconds: int = 300
    fusion_min_events: int = 1
    fusion_min_confidence: float = 0.3


class ExecutionRuntimeConfig(RuntimeConfigBase):
    """Execution Runtime 配置"""
    name: str = "execution_runtime"
    max_position_size: float = 0.1
    max_leverage: int = 5
    enable_mock: bool = True


class ProjectionRuntimeConfig(RuntimeConfigBase):
    """Projection Runtime 配置"""
    name: str = "projection_runtime"
    batch_size: int = 100
    flush_interval: float = 1.0
    redis_key_prefix: str = "projection:"


class CorrelationRuntimeConfig(RuntimeConfigBase):
    """Correlation Runtime 配置"""
    name: str = "correlation_runtime"
    symbols: List[str] = Field(default_factory=lambda: ["BTC", "ETH"])
    timeframes: List[str] = Field(default_factory=lambda: ["1h", "4h"])
    interval: int = 3600
    output_dir: str = "./data/correlation_results"


class StrategyConfig(BaseModel):
    """策略配置基类"""
    name: str
    enabled: bool = True
    timeframes: Dict[str, str] = Field(default_factory=dict)
    indicators: Dict[str, Any] = Field(default_factory=dict)
    signals: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)


class BTCSwingConfig(StrategyConfig):
    """BTC Swing 策略配置"""
    name: str = "btc_swing"
    timeframes: Dict[str, str] = Field(default_factory=lambda: {
        "primary": "4h",
        "confirmation": "1d",
    })
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "macro": 0.4,
        "funding": 0.2,
        "technical": 0.3,
        "sentiment": 0.1,
    })
