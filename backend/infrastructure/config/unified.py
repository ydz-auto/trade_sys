"""
统一配置访问接口

提供统一的配置访问方式，自动处理：
1. ConfigService (动态配置 - Redis)
2. 环境变量
3. 代码默认值

优先级：ConfigService > 环境变量 > 默认值

使用方式：
    from infrastructure.config import get_config, get_exchange_credentials, get_llm_credentials
    
    # 获取静态配置
    kafka_servers = await get_config("kafka.bootstrap_servers")
    
    # 获取交易所配置
    binance_config = await get_exchange_credentials("binance")
    
    # 获取 LLM 配置
    openai_config = await get_llm_credentials("openai")
    
    # 获取策略参数
    weight = await get_config("strategy.momentum_weight")
    
    # 获取 API URL
    api_url = await get_api_url("binance")
"""

import os
import logging
from typing import Any, Optional, Dict
from infrastructure.config.manager import get_config_manager

logger = logging.getLogger("config.unified")


# =============================================================================
# API Key 环境变量映射
# =============================================================================

LLM_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qianfan": "QIANFAN_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}

EXCHANGE_API_KEY_ENV = {
    "binance": ("BINANCE_API_KEY", "BINANCE_SECRET_KEY"),
    "okx": ("OKX_API_KEY", "OKX_API_SECRET", "OKX_PASSPHRASE"),
    "bybit": ("BYBIT_API_KEY", "BYBIT_API_SECRET"),
    "gate": ("GATE_API_KEY", "GATE_API_SECRET"),
}

API_URL_ENV = {
    "binance": "BINANCE_SPOT_API_URL",
    "binance_futures": "BINANCE_FUTURES_API_URL",
    "okx": "OKX_API_URL",
    "bybit": "BYBIT_API_URL",
    "gate": "GATE_API_URL",
    "openai": "OPENAI_API_URL",
    "anthropic": "ANTHROPIC_API_URL",
    "zhipu": "ZHIPU_API_URL",
    "deepseek": "DEEPSEEK_API_URL",
    "ollama": "OLLAMA_API_URL",
    "odaily": "ODAILY_BASE_URL",
}


# =============================================================================
# 默认值
# =============================================================================

# 从 external_apis.py 导入默认 API URL
from infrastructure.config.defaults.infrastructure.external_apis import (
    BINANCE_REST_API,
    BINANCE_WS_URL,
    OKX_REST_API,
    BYBIT_REST_API,
    GATE_REST_API,
    OPENAI_API_URL,
    ANTHROPIC_API_URL,
    ZHIPU_API_URL,
    DEEPSEEK_API_URL,
    OLLAMA_API_URL,
    ODAILY_BASE_URL,
)

DEFAULT_API_URLS = {
    "binance": BINANCE_REST_API,
    "binance_futures": "https://fapi.binance.com",
    "okx": OKX_REST_API,
    "bybit": BYBIT_REST_API,
    "gate": GATE_REST_API,
    "openai": OPENAI_API_URL,
    "anthropic": ANTHROPIC_API_URL,
    "zhipu": ZHIPU_API_URL,
    "deepseek": DEEPSEEK_API_URL,
    "ollama": OLLAMA_API_URL,
    "odaily": ODAILY_BASE_URL,
}

DEFAULT_STRATEGY_CONFIG = {
    "momentum_weight": float(os.environ.get("STRATEGY_MOMENTUM_WEIGHT", "0.3")),
    "trend_weight": float(os.environ.get("STRATEGY_TREND_WEIGHT", "0.3")),
    "flow_weight": float(os.environ.get("STRATEGY_FLOW_WEIGHT", "0.2")),
    "sentiment_weight": float(os.environ.get("STRATEGY_SENTIMENT_WEIGHT", "0.2")),
}


# =============================================================================
# 统一配置获取接口
# =============================================================================

async def get_config(key: str, default: Any = None) -> Any:
    """
    统一配置获取接口
    
    配置键格式：
    - 静态配置: `kafka.bootstrap_servers`, `redis.url`
    - 策略参数: `strategy.momentum_weight`
    - 动态配置: `exchange.{name}.api_key`, `llm.{provider}.api_key`
    
    Args:
        key: 配置键
        default: 默认值
    
    Returns:
        配置值
    """
    # 1. 策略参数
    if key.startswith("strategy."):
        return await _get_strategy_config(key, default)
    
    # 2. API URL
    if key.endswith(".api_url") or key == "api_url":
        service = key.replace(".api_url", "").replace("api_url", "")
        return await get_api_url(service or None, default)
    
    # 3. 动态配置 (exchange.*, llm.*)
    if key.startswith("exchange."):
        return await _get_exchange_config(key, default)
    
    if key.startswith("llm."):
        return await _get_llm_config(key, default)
    
    # 4. 静态配置 (ConfigManager)
    config_manager = get_config_manager()
    return config_manager.get(key, default)


async def _get_strategy_config(key: str, default: Any = None) -> Any:
    """获取策略配置
    
    ARCHITECTURE NOTE: infrastructure → application 反向依赖
    此处使用 lazy import + try/except 降级到本地默认值。
    TODO: 应改为依赖注入，由 application 层注入 ConfigService 实例。
    """
    try:
        from application.queries.config_queries import get_config_service
        
        field = key.replace("strategy.", "")
        service = get_config_service()
        config = await service.get_strategy_config()
        return config.get(field, default if default is not None else DEFAULT_STRATEGY_CONFIG.get(field))
    except Exception as e:
        logger.debug(f"Failed to get strategy config {key}: {e}")
        field = key.replace("strategy.", "")
        return default if default is not None else DEFAULT_STRATEGY_CONFIG.get(field)


async def _get_exchange_config(key: str, default: Any = None) -> Any:
    try:
        from application.queries.config_queries import get_config_service

        parts = key.split(".")
        if len(parts) < 3:
            return default
        
        exchange = parts[1]
        field = parts[2]
        
        service = get_config_service()
        config = await service.get_exchange_config(exchange)
        
        if config and field in config:
            return config[field]
        
        return default
    except Exception as e:
        logger.debug(f"Failed to get exchange config {key}: {e}")
        return default


async def _get_llm_config(key: str, default: Any = None) -> Any:
    try:
        from application.queries.config_queries import get_config_service

        parts = key.split(".")
        if len(parts) < 3:
            return default
        
        provider = parts[1]
        field = parts[2]
        
        service = get_config_service()
        config = await service.get_llm_provider_config(provider)
        
        if config and field in config:
            return config[field]
        
        return default
    except Exception as e:
        logger.debug(f"Failed to get LLM config {key}: {e}")
        return default


# =============================================================================
# 便捷方法
# =============================================================================

async def get_exchange_credentials(exchange: str) -> Optional[Dict[str, str]]:
    """
    获取交易所凭证
    
    优先级：ConfigService > 环境变量
    
    Args:
        exchange: 交易所名称 (binance, okx, bybit)
    
    Returns:
        {'api_key': '...', 'secret': '...', 'api_url': '...', 'testnet': bool} 或 None
    """
    result = {}

    try:
        from application.queries.config_queries import get_config_service

        service = get_config_service()
        config = await service.get_exchange_config(exchange)
        if config:
            result.update(config)
    except Exception as e:
        logger.debug(f"Failed to get exchange config from ConfigService: {e}")
    
    # 2. 从环境变量获取（如果 ConfigService 没有）
    if not result.get("api_key"):
        env_keys = EXCHANGE_API_KEY_ENV.get(exchange, ())
        if env_keys:
            result["api_key"] = os.environ.get(env_keys[0], "")
            if len(env_keys) > 1:
                result["secret"] = os.environ.get(env_keys[1], "")
            if len(env_keys) > 2:
                result["passphrase"] = os.environ.get(env_keys[2], "")
    
    # 3. 获取 API URL
    if not result.get("api_url"):
        result["api_url"] = await get_api_url(exchange)
    
    return result if result.get("api_key") else None


async def get_llm_credentials(provider: str) -> Optional[Dict[str, Any]]:
    """
    获取 LLM 凭证
    
    优先级：ConfigService > 环境变量
    
    Args:
        provider: 提供商名称 (openai, anthropic, zhipu)
    
    Returns:
        {'api_key': '...', 'model': '...', 'api_url': '...'} 或 None
    """
    result = {}

    try:
        from application.queries.config_queries import get_config_service

        service = get_config_service()
        config = await service.get_llm_provider_config(provider)
        if config:
            result.update(config)
    except Exception as e:
        logger.debug(f"Failed to get LLM config from ConfigService: {e}")
    
    # 2. 从环境变量获取 API Key（如果 ConfigService 没有）
    if not result.get("api_key"):
        env_name = LLM_API_KEY_ENV.get(provider)
        if env_name:
            result["api_key"] = os.environ.get(env_name, "")
    
    # 3. 获取 API URL
    if not result.get("api_url"):
        result["api_url"] = await get_api_url(provider)
    
    return result if result.get("api_key") or provider == "ollama" else None


async def get_api_url(service: str = None, default: str = None) -> str:
    """
    获取 API URL
    
    优先级：ConfigService > 环境变量 > 默认值
    
    Args:
        service: 服务名称 (如 'binance', 'openai', 'odaily')
        default: 默认值
    
    Returns:
        API URL
    """
    if not service:
        return default or ""

    try:
        from application.queries.config_queries import get_config_service

        cs = get_config_service()
        url = await cs.get_api_url(service)
        if url:
            return url
    except Exception as e:
        logger.debug(f"Failed to get API URL from ConfigService: {e}")
    
    # 2. 从环境变量获取
    env_name = API_URL_ENV.get(service)
    if env_name:
        url = os.environ.get(env_name)
        if url:
            return url
    
    # 3. 返回默认值
    return default or DEFAULT_API_URLS.get(service, "")


async def get_strategy_weights() -> Dict[str, float]:
    """
    获取策略权重配置
    
    Returns:
        {'momentum_weight': 0.3, 'trend_weight': 0.3, ...}
    """
    try:
        from application.queries.config_queries import get_config_service

        service = get_config_service()
        return await service.get_strategy_config()
    except Exception as e:
        logger.debug(f"Failed to get strategy config: {e}")
        return DEFAULT_STRATEGY_CONFIG.copy()
