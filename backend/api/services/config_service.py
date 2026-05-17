"""
Config Service - Configuration Management Service
配置管理服务 - 管理新闻源、API Keys、数据源配置
"""
import json
import hashlib
import secrets
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from infrastructure.cache.redis_client import RedisClient, init_redis
from infrastructure.logging import get_logger

logger = get_logger("config_service")


class ConfigService:
    """配置管理服务"""

    NEWS_SOURCES_KEY = "config:news_sources"
    API_KEYS_KEY = "config:api_keys"
    DATA_SOURCES_KEY = "config:data_sources"
    LLM_CONFIG_KEY = "config:llm"

    def __init__(self):
        self._redis: Optional[RedisClient] = None

    async def ensure_connection(self):
        """确保Redis连接"""
        if self._redis is None or not self._redis.is_connected:
            self._redis = await init_redis()
            await self._ensure_defaults()

    @property
    def redis(self) -> RedisClient:
        if self._redis is None:
            raise RuntimeError("Redis not connected. Call ensure_connection() first.")
        return self._redis

    def _hash_key(self, key: str) -> str:
        """简单哈希存储，不存储完整key"""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _mask_key(self, key: str) -> str:
        """显示key的前4后4位"""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}...{key[-4:]}"

    async def init(self):
        """初始化默认配置"""
        await self._ensure_defaults()

    async def _ensure_defaults(self):
        """确保默认配置存在"""
        existing = await self.redis.get(self.NEWS_SOURCES_KEY)
        if not existing:
            defaults = self._get_default_news_sources()
            await self.redis.set_json(self.NEWS_SOURCES_KEY, defaults)
            logger.info("Initialized default news sources")

    def _get_default_news_sources(self) -> List[Dict]:
        """获取默认新闻源"""
        return [
            {
                "id": str(uuid4()),
                "name": "CoinDesk RSS",
                "type": "rss",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                "enabled": True,
                "priority": 1,
                "keywords": ["bitcoin", "btc", "crypto", "ethereum", "eth"],
                "blacklist": ["ads", "sponsored"],
                "update_interval": 300,
                "status": "active",
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": str(uuid4()),
                "name": "The Block RSS",
                "type": "rss",
                "url": "https://www.theblock.co/rss.xml",
                "enabled": True,
                "priority": 2,
                "keywords": ["crypto", "blockchain", "defi", "nft"],
                "blacklist": ["advertisement"],
                "update_interval": 300,
                "status": "active",
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": str(uuid4()),
                "name": "CryptoNews API",
                "type": "api",
                "url": "https://cryptonews-api.com/api/v1/category?section=alltickers&page=1",
                "enabled": False,
                "priority": 3,
                "keywords": ["bitcoin", "ethereum", "solana", "bnb"],
                "blacklist": [],
                "update_interval": 600,
                "status": "inactive",
                "created_at": datetime.now().isoformat(),
            },
        ]

    async def get_news_sources(self) -> List[Dict]:
        """获取所有新闻源"""
        data = await self.redis.get(self.NEWS_SOURCES_KEY)
        if data:
            if isinstance(data, str):
                return json.loads(data)
            return data
        return self._get_default_news_sources()

    async def get_news_source(self, source_id: str) -> Optional[Dict]:
        """获取单个新闻源"""
        sources = await self.get_news_sources()
        for s in sources:
            if s.get("id") == source_id:
                return s
        return None

    async def create_news_source(self, source_data: Dict) -> Dict:
        """创建新闻源"""
        sources = await self.get_news_sources()

        new_source = {
            "id": str(uuid4()),
            **source_data,
            "status": "active" if source_data.get("enabled", True) else "inactive",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        sources.append(new_source)
        await self.redis.set_json(self.NEWS_SOURCES_KEY, sources)
        logger.info(f"Created news source: {new_source['name']}")

        return new_source

    async def update_news_source(self, source_id: str, updates: Dict) -> Optional[Dict]:
        """更新新闻源"""
        sources = await self.get_news_sources()

        for i, s in enumerate(sources):
            if s.get("id") == source_id:
                sources[i].update(updates)
                sources[i]["updated_at"] = datetime.now().isoformat()

                if "enabled" in updates:
                    sources[i]["status"] = "active" if updates["enabled"] else "inactive"

                await self.redis.set_json(self.NEWS_SOURCES_KEY, sources)
                logger.info(f"Updated news source: {source_id}")
                return sources[i]

        return None

    async def delete_news_source(self, source_id: str) -> bool:
        """删除新闻源"""
        sources = await self.get_news_sources()
        original_len = len(sources)

        sources = [s for s in sources if s.get("id") != source_id]

        if len(sources) < original_len:
            await self.redis.set_json(self.NEWS_SOURCES_KEY, sources)
            logger.info(f"Deleted news source: {source_id}")
            return True

        return False

    async def get_api_keys(self) -> List[Dict]:
        """获取所有API Keys(不返回完整key)"""
        data = await self.redis.get(self.API_KEYS_KEY)
        if data:
            if isinstance(data, str):
                return json.loads(data)
            return data
        return []

    async def get_api_key(self, key_id: str) -> Optional[Dict]:
        """获取单个API Key"""
        keys = await self.get_api_keys()
        for k in keys:
            if k.get("id") == key_id:
                return k
        return None

    async def create_api_key(self, key_data: Dict) -> Dict:
        """创建API Key"""
        keys = await self.get_api_keys()

        api_key = key_data.get("api_key", "")
        secret = key_data.get("secret", "")

        new_key = {
            "id": str(uuid4()),
            "name": key_data.get("name"),
            "type": key_data.get("type"),
            "provider": key_data.get("provider"),
            "key_hint": self._mask_key(api_key) if api_key else "",
            "key_hash": self._hash_key(api_key) if api_key else "",
            "secret_hash": self._hash_key(secret) if secret else "",
            "enabled": key_data.get("enabled", True),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        keys.append(new_key)
        await self.redis.set_json(self.API_KEYS_KEY, keys)
        logger.info(f"Created API key: {new_key['name']}")

        result = new_key.copy()
        result.pop("key_hash", None)
        result.pop("secret_hash", None)

        return result

    async def update_api_key(self, key_id: str, updates: Dict) -> Optional[Dict]:
        """更新API Key"""
        keys = await self.get_api_keys()

        for i, k in enumerate(keys):
            if k.get("id") == key_id:
                if "api_key" in updates:
                    keys[i]["key_hint"] = self._mask_key(updates["api_key"])
                    keys[i]["key_hash"] = self._hash_key(updates["api_key"])
                if "secret" in updates:
                    keys[i]["secret_hash"] = self._hash_key(updates["secret"])

                keys[i].update({k: v for k, v in updates.items() if k not in ["api_key", "secret"]})
                keys[i]["updated_at"] = datetime.now().isoformat()

                await self.redis.set_json(self.API_KEYS_KEY, keys)
                logger.info(f"Updated API key: {key_id}")

                result = keys[i].copy()
                result.pop("key_hash", None)
                result.pop("secret_hash", None)
                return result

        return None

    async def delete_api_key(self, key_id: str) -> bool:
        """删除API Key"""
        keys = await self.get_api_keys()
        original_len = len(keys)

        keys = [k for k in keys if k.get("id") != key_id]

        if len(keys) < original_len:
            await self.redis.set_json(self.API_KEYS_KEY, keys)
            logger.info(f"Deleted API key: {key_id}")
            return True

        return False

    async def get_llm_config(self) -> Dict:
        """获取LLM配置"""
        data = await self.redis.get(self.LLM_CONFIG_KEY)
        if data:
            if isinstance(data, str):
                return json.loads(data)
            return data
        return {}

    async def update_llm_config(self, config: Dict) -> Dict:
        """更新LLM配置"""
        await self.redis.set_json(self.LLM_CONFIG_KEY, config)
        logger.info("Updated LLM config")
        return config

    async def get_data_sources(self) -> List[Dict]:
        """获取数据源配置"""
        data = await self.redis.get(self.DATA_SOURCES_KEY)
        if data:
            if isinstance(data, str):
                return json.loads(data)
            return data
        return []

    async def update_data_sources(self, sources: List[Dict]) -> List[Dict]:
        """更新数据源配置"""
        await self.redis.set_json(self.DATA_SOURCES_KEY, sources)
        logger.info("Updated data sources")
        return sources


_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
