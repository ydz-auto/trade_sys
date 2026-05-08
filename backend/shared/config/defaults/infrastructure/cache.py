"""
Cache 配置 - 基础设施配置
"""

from shared.config.enums import CacheStrategy


CACHE_CONFIGS = {
    "cache.key_prefix": "tradeagent",
    "cache.default_ttl": 60,
    "cache.redis_url": "redis://localhost:6379/0",
    "cache.host": "localhost",
    "cache.port": 6379,
    "cache.db": 0,
    "cache.password": None,
    "cache.max_connections": 50,
    "cache.socket_timeout": 5.0,
    "cache.socket_connect_timeout": 5.0,
    "cache.retry_on_timeout": True,
    "cache.market_price_ttl": 1,
    "cache.market_depth_ttl": 5,
    "cache.market_kline_ttl": 60,
    "cache.factor_score_ttl": 60,
    "cache.factor_regime_ttl": 60,
    "cache.factor_composite_ttl": 60,
    "cache.news_list_ttl": 300,
    "cache.social_list_ttl": 300,
    "cache.sentiment_ttl": 300,
    "cache.user_config_ttl": 3600,
    "cache.user_session_ttl": 86400,
    "cache.system_health_ttl": 30,
    "cache.system_status_ttl": 60,
    "cache.regime_current_ttl": 60,
    "cache.regime_risk_ttl": 60,
    "cache.regime_history_ttl": 86400,
    "cache.decision_signal_ttl": 60,
    "cache.decision_last_ttl": 60,
    "cache.decision_block_ttl": 300,
}


CACHE_TTL = {
    "market_price": 1,
    "market_depth": 5,
    "market_kline": 60,
    "factor_score": 60,
    "factor_regime": 60,
    "factor_composite": 60,
    "news_list": 300,
    "social_list": 300,
    "sentiment": 300,
    "user_config": 3600,
    "user_session": 86400,
    "system_health": 30,
    "system_status": 60,
    "regime_current": 60,
    "regime_risk": 60,
    "regime_history": 86400,
    "decision_signal": 60,
    "decision_last": 60,
    "decision_block": 300,
}


DEFAULT_TTL = 60


CACHE_DB_ALLOCATION = {
    0: "实时状态",
    1: "缓存数据",
    2: "Session",
    3: "分布式锁",
    4: "Pub/Sub",
}


KEY_NAMING_CONVENTION = "{prefix}:{service}:{entity}:{id}:{field}"


CACHE_KEY_PATTERNS = {
    "price": "market:price:{symbol}",
    "depth": "market:depth:{symbol}",
    "kline": "market:kline:{symbol}:{timeframe}",
    "etf": "data:etf:{symbol}",
    "macro": "data:macro:{type}",
    "factor_score": "factor:score:{symbol}",
    "factor_regime": "factor:regime:{symbol}",
    "factor_composite": "factor:composite:{symbol}",
    "regime_current": "regime:current:{symbol}",
    "regime_risk": "regime:risk:{symbol}",
    "regime_history": "regime:history:{symbol}",
    "user_config": "user:config:{user_id}",
    "user_session": "user:session:{session_id}",
    "user_rate": "user:rate:{user_id}",
    "system_health": "system:health",
    "system_status": "system:status:{service}",
    "decision_signal": "decision:signal:{symbol}",
    "decision_last": "decision:last:{symbol}",
    "decision_block": "decision:block:{symbol}",
}
