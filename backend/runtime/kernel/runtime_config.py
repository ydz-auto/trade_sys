import os
from dataclasses import dataclass


__all__ = ["RuntimeConfig"]


@dataclass
class RuntimeConfig:
    name: str = "unknown"
    version: str = "1.0.0"
    environment: str = "dev"
    log_level: str = "INFO"
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    shutdown_timeout: int = 30
    health_check_interval: int = 10

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        return cls(
            name=os.environ.get("RUNTIME_NAME", "unknown"),
            version=os.environ.get("RUNTIME_VERSION", "1.0.0"),
            environment=os.environ.get("ENVIRONMENT", "dev"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            metrics_enabled=os.environ.get("METRICS_ENABLED", "true").lower() == "true",
            tracing_enabled=os.environ.get("TRACING_ENABLED", "true").lower() == "true",
            shutdown_timeout=int(os.environ.get("SHUTDOWN_TIMEOUT", "30")),
            health_check_interval=int(os.environ.get("HEALTH_CHECK_INTERVAL", "10")),
        )
