"""
Config Adapter - Bridge between runtime kernel and infrastructure config.

Kernel code should use this adapter instead of importing
infrastructure.config directly.
"""
import os
from typing import Any, Callable, Optional


_config_provider: Optional[Callable[[str, Any], Any]] = None


def set_config_provider(provider: Callable[[str, Any], Any]):
    """Inject infrastructure config provider.

    Call this at application startup:
        from runtime.adapters.config_adapter import set_config_provider
        set_config_provider(my_config_getter)
    """
    global _config_provider
    _config_provider = provider


def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value.

    Priority:
    1. Infrastructure config provider (if set)
    2. Environment variables
    3. StartupSettings (pydantic-settings)
    4. Provided default
    """
    if _config_provider is not None:
        result = _config_provider(key, default)
        if result is not default and result is not None:
            return result

    env_value = os.environ.get(key)
    if env_value is not None:
        return env_value

    try:
        from infrastructure.config.startup.settings import get_startup_settings
        settings = get_startup_settings()
        return _resolve_from_settings(key, settings, default)
    except Exception:
        return default


def _resolve_from_settings(key: str, settings: Any, default: Any) -> Any:
    """Resolve config key from StartupSettings"""
    mapping = {
        "KAFKA_BOOTSTRAP_SERVERS": lambda: settings.kafka.bootstrap_servers,
        "KAFKA_CLIENT_ID": lambda: settings.kafka.client_id,
        "REDIS_URL": lambda: settings.redis.url,
        "REDIS_HOST": lambda: settings.redis.host,
        "REDIS_PORT": lambda: settings.redis.port,
        "REDIS_DB": lambda: settings.redis.db,
        "REDIS_PASSWORD": lambda: settings.redis.password,
        "POSTGRES_HOST": lambda: settings.postgres.host,
        "POSTGRES_PORT": lambda: settings.postgres.port,
        "POSTGRES_DATABASE": lambda: settings.postgres.database,
        "POSTGRES_USERNAME": lambda: settings.postgres.username,
        "POSTGRES_PASSWORD": lambda: settings.postgres.password,
        "CLICKHOUSE_HOST": lambda: settings.clickhouse.host,
        "CLICKHOUSE_PORT": lambda: settings.clickhouse.port,
        "CLICKHOUSE_DATABASE": lambda: settings.clickhouse.database,
        "CLICKHOUSE_USERNAME": lambda: settings.clickhouse.username,
        "CLICKHOUSE_PASSWORD": lambda: settings.clickhouse.password,
    }
    resolver = mapping.get(key)
    if resolver:
        try:
            return resolver()
        except Exception:
            pass
    return default


def get_kafka_servers() -> str:
    """Get Kafka bootstrap servers from unified config"""
    return get_config("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def get_redis_url() -> str:
    """Get Redis URL from unified config"""
    return get_config("REDIS_URL", "redis://localhost:6379/0")
