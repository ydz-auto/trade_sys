"""
Data Service Cache - 数据服务缓存封装
"""

from typing import Optional, Dict, Any
from infrastructure.cache import CacheManager, get_cache_manager
from infrastructure.cache.keys import CacheKey

CACHE_TTL_SHORT = 30
CACHE_TTL_MEDIUM = 300
CACHE_TTL_LONG = 1800


class DataServiceCache:
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()
        self._ttl_short = CACHE_TTL_SHORT
        self._ttl_medium = CACHE_TTL_MEDIUM
        self._ttl_long = CACHE_TTL_LONG

    async def get_price(self, symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
        key = f"data:price:{symbol}:{exchange}"
        return await self._cache.get(key)

    async def set_price(self, symbol: str, exchange: str, data: Dict[str, Any], ttl: int = None):
        key = f"data:price:{symbol}:{exchange}"
        await self._cache.set(key, data, ttl=ttl or self._ttl_short)

    async def get_all_prices(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = f"data:prices:{symbol}"
        return await self._cache.get(key)

    async def set_all_prices(self, symbol: str, data: Dict[str, Any], ttl: int = None):
        key = f"data:prices:{symbol}"
        await self._cache.set(key, data, ttl=ttl or self._ttl_short)

    async def get_etf_flow(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = f"data:etf:{symbol}"
        return await self._cache.get(key)

    async def set_etf_flow(self, symbol: str, data: Dict[str, Any], ttl: int = None):
        key = f"data:etf:{symbol}"
        await self._cache.set(key, data, ttl=ttl or self._ttl_medium)

    async def get_macro_data(self, asset: str) -> Optional[Dict[str, Any]]:
        key = f"data:macro:{asset}"
        return await self._cache.get(key)

    async def set_macro_data(self, asset: str, data: Dict[str, Any], ttl: int = None):
        key = f"data:macro:{asset}"
        await self._cache.set(key, data, ttl=ttl or self._ttl_medium)

    async def get_news_list(self, sentiment: str = None, limit: int = 20) -> Optional[list]:
        key = f"data:news:{sentiment or 'all'}:{limit}"
        return await self._cache.get(key)

    async def set_news_list(self, news: list, sentiment: str = None, limit: int = 20, ttl: int = None):
        key = f"data:news:{sentiment or 'all'}:{limit}"
        await self._cache.set(key, news, ttl=ttl or self._ttl_short)

    async def get_trader_sentiment(self) -> Optional[Dict[str, Any]]:
        key = "data:trader:sentiment"
        return await self._cache.get(key)

    async def set_trader_sentiment(self, data: Dict[str, Any], ttl: int = None):
        key = "data:trader:sentiment"
        await self._cache.set(key, data, ttl=ttl or self._ttl_medium)

    async def get_crypto_stocks(self) -> Optional[list]:
        key = "data:crypto_stocks"
        return await self._cache.get(key)

    async def set_crypto_stocks(self, data: list, ttl: int = None):
        key = "data:crypto_stocks"
        await self._cache.set(key, data, ttl=ttl or self._ttl_medium)

    async def get_social_posts(self, platform: str, limit: int = 20) -> Optional[list]:
        key = f"data:social:{platform}:{limit}"
        return await self._cache.get(key)

    async def set_social_posts(self, platform: str, posts: list, limit: int = 20, ttl: int = None):
        key = f"data:social:{platform}:{limit}"
        await self._cache.set(key, posts, ttl=ttl or self._ttl_short)

    async def invalidate_price(self, symbol: str, exchange: str = None):
        if exchange:
            await self._cache.delete(f"data:price:{symbol}:{exchange}")
        else:
            await self._cache.delete_pattern(f"data:price:{symbol}:*")
        await self._cache.delete(f"data:prices:{symbol}")

    async def invalidate_etf(self, symbol: str):
        await self._cache.delete(f"data:etf:{symbol}")

    async def invalidate_macro(self, asset: str):
        await self._cache.delete(f"data:macro:{asset}")

    async def invalidate_news(self):
        await self._cache.delete_pattern("data:news:*")

    async def invalidate_trader_sentiment(self):
        await self._cache.delete("data:trader:sentiment")

    async def invalidate_crypto_stocks(self):
        await self._cache.delete("data:crypto_stocks")

    async def invalidate_social(self, platform: str = None):
        if platform:
            await self._cache.delete_pattern(f"data:social:{platform}:*")
        else:
            await self._cache.delete_pattern("data:social:*")

    async def cache_or_fetch(
        self,
        key: str,
        fetch_func,
        ttl: int = None,
    ):
        return await self._cache.cache_aside(
            key=key,
            compute_func=fetch_func,
            ttl=ttl,
        )


_data_cache: Optional[DataServiceCache] = None


def get_data_cache() -> DataServiceCache:
    global _data_cache
    if _data_cache is None:
        _data_cache = DataServiceCache()
    return _data_cache
