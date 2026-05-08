"""
LLM Service 配置
"""

import os
from typing import Dict, Optional
from pydantic import BaseModel

from shared.config.defaults.infrastructure import LOGGING_CONFIGS, LOG_CONFIG, LOG_LEVELS, CACHE_CONFIGS, DEFAULT_TTL


class Settings(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    minimax_api_key: Optional[str] = None
    minimax_api_base: Optional[str] = None

    redis_url: str = CACHE_CONFIGS.get("cache.redis_url", "redis://localhost:6379/0")
    cache_ttl: int = CACHE_CONFIGS.get("cache.sentiment_ttl", DEFAULT_TTL)

    log_level: str = LOGGING_CONFIGS.get("logging.system_level", "INFO")
    log_dir: str = LOGGING_CONFIGS.get("logging.dir", "logs")
    log_config: Dict = LOG_CONFIG


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            minimax_api_key=os.getenv("MINIMAX_API_KEY"),
            minimax_api_base=os.getenv("MINIMAX_API_BASE", "https://api.minimax.chat/v1"),
            redis_url=os.getenv("REDIS_URL", CACHE_CONFIGS.get("cache.redis_url", "redis://localhost:6379/0")),
            cache_ttl=int(os.getenv("LLM_CACHE_TTL", str(CACHE_CONFIGS.get("cache.sentiment_ttl", DEFAULT_TTL)))),
            log_level=os.getenv("LOG_LEVEL", LOGGING_CONFIGS.get("logging.system_level", "INFO")),
            log_dir=os.getenv("LOG_DIR", LOGGING_CONFIGS.get("logging.dir", "logs")),
        )
    return _settings
