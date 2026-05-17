"""
Startup Settings - 基础设施启动配置
使用 pydantic-settings 加载环境变量

只负责进程启动时固定的配置：
- 数据库连接
- Redis 连接
- Kafka 配置
- API Keys
- 环境标识
"""

from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseSettings):
    """Kafka 配置"""
    model_config = SettingsConfigDict(env_prefix="KAFKA_", env_file=".env")

    bootstrap_servers: str = Field(default="localhost:9092", description="Kafka bootstrap servers")
    client_id: str = Field(default="tradeagent", description="Kafka client ID")
    consumer_group: str = Field(default="tradeagent", description="Kafka consumer group")
    auto_offset_reset: str = Field(default="latest", description="Auto offset reset")
    enable_auto_commit: bool = Field(default=True, description="Enable auto commit")
    max_poll_records: int = Field(default=100, description="Max poll records")
    session_timeout_ms: int = Field(default=30000, description="Session timeout ms")
    heartbeat_interval_ms: int = Field(default=10000, description="Heartbeat interval ms")


class RedisSettings(BaseSettings):
    """Redis 配置"""
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env")

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[str] = Field(default=None, description="Redis password")
    url: str = Field(default="redis://localhost:6379/0", description="Redis URL (override)")
    max_connections: int = Field(default=50, description="Max connections")
    socket_timeout: float = Field(default=5.0, description="Socket timeout")
    socket_connect_timeout: float = Field(default=5.0, description="Socket connect timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")


class PostgresSettings(BaseSettings):
    """PostgreSQL 配置"""
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env")

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(default="tradeagent", description="Database name")
    username: str = Field(default="postgres", description="Username")
    password: str = Field(default="postgres", description="Password")
    min_connections: int = Field(default=5, description="Min pool connections")
    max_connections: int = Field(default=20, description="Max pool connections")
    connection_timeout: int = Field(default=30, description="Connection timeout")
    command_timeout: int = Field(default=60, description="Command timeout")


class ClickHouseSettings(BaseSettings):
    """ClickHouse 配置"""
    model_config = SettingsConfigDict(env_prefix="CLICKHOUSE_", env_file=".env")

    host: str = Field(default="localhost", description="ClickHouse host")
    port: int = Field(default=9000, description="ClickHouse port")
    database: str = Field(default="tradeagent", description="Database name")
    username: str = Field(default="default", description="Username")
    password: str = Field(default="", description="Password")
    min_connections: int = Field(default=5, description="Min pool connections")
    max_connections: int = Field(default=20, description="Max pool connections")
    connection_timeout: int = Field(default=30, description="Connection timeout")
    send_receive_timeout: int = Field(default=300, description="Send receive timeout")


class SystemSettings(BaseSettings):
    """系统配置"""
    model_config = SettingsConfigDict(env_file=".env")

    env: str = Field(default="development", description="Environment: development/staging/production")
    service_name: str = Field(default="tradeagent", description="Service name")
    log_level: str = Field(default="INFO", description="Log level")
    debug: bool = Field(default=False, description="Debug mode")
    allow_trading: bool = Field(default=True, description="Allow real trading")


class LLMSettings(BaseSettings):
    """LLM 服务配置"""
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env")

    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI base URL")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API Key")
    minimax_api_key: Optional[str] = Field(default=None, description="Minimax API Key")
    minimax_base_url: str = Field(default="https://api.minimax.chat/v1", description="Minimax base URL")
    default_model: str = Field(default="gpt-4o", description="Default model")

    zhipu_api_key: Optional[str] = Field(default=None, description="智谱AI API Key")
    zhipu_base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4", description="智谱AI base URL")

    siliconflow_api_key: Optional[str] = Field(default=None, description="硅基流动 API Key")
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1", description="硅基流动 base URL")

    deepseek_api_key: Optional[str] = Field(default=None, description="DeepSeek API Key")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", description="DeepSeek base URL")

    qianfan_api_key: Optional[str] = Field(default=None, description="百度千帆 API Key")
    qianfan_base_url: str = Field(default="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop", description="百度千帆 base URL")

    dashscope_api_key: Optional[str] = Field(default=None, description="阿里百炼 API Key")
    dashscope_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="阿里百炼 base URL")

    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama base URL")


class APIKeysSettings(BaseSettings):
    """第三方 API Keys"""
    model_config = SettingsConfigDict(env_file=".env")

    binance_api_key: Optional[str] = Field(default=None, description="Binance API Key")
    binance_secret_key: Optional[str] = Field(default=None, description="Binance Secret Key")
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram bot token")
    telegram_chat_id: Optional[str] = Field(default=None, description="Telegram chat ID")


class StartupSettings(BaseSettings):
    """
    统一启动配置入口
    整合所有 startup 配置
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    api_keys: APIKeysSettings = Field(default_factory=APIKeysSettings)


_startup_settings: Optional[StartupSettings] = None


def get_startup_settings() -> StartupSettings:
    """获取全局 startup settings 实例"""
    global _startup_settings
    if _startup_settings is None:
        _startup_settings = StartupSettings()
    return _startup_settings


def reload_startup_settings() -> StartupSettings:
    """重新加载 startup settings"""
    global _startup_settings
    _startup_settings = StartupSettings()
    return _startup_settings
