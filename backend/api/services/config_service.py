"""
Config Service - Configuration Management Service
配置管理服务 - 管理新闻源、API Keys、数据源配置
"""
import json
import hashlib
import secrets
import base64
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from infrastructure.cache.redis_client import RedisClient, init_redis
from infrastructure.logging import get_logger

logger = get_logger("config_service")


class ConfigService:
    """配置管理服务"""

    NEWS_SOURCES_KEY = "config:news_sources"
    API_KEYS_KEY = "config:api_keys"
    DATA_SOURCES_KEY = "config:data_sources"
    LLM_CONFIG_KEY = "config:llm"
    EXCHANGE_CONFIG_KEY = "config:exchanges"
    STRATEGY_CONFIG_KEY = "config:strategy"
    API_URLS_KEY = "config:api_urls"
    TWITTER_CONFIG_KEY = "config:twitter"
    TELEGRAM_CONFIG_KEY = "config:telegram"
    
    ENCRYPTION_KEY_ENV = "CONFIG_ENCRYPTION_KEY"

    def __init__(self):
        self._redis: Optional[RedisClient] = None
        self._fernet: Optional[Fernet] = None

    async def ensure_connection(self):
        """确保Redis连接"""
        if self._redis is None or not self._redis.is_connected:
            self._redis = await init_redis()
            self._init_encryption()
            await self._ensure_defaults()

    def _init_encryption(self):
        """初始化加密"""
        import os
        key = os.environ.get(self.ENCRYPTION_KEY_ENV)
        if not key:
            key = secrets.token_urlsafe(32)
            logger.warning(f"Generated new encryption key. Set {self.ENCRYPTION_KEY_ENV} for production.")
        
        key_bytes = key.encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'tradeagent_config_salt',
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
        self._fernet = Fernet(derived_key)

    def _encrypt(self, value: str) -> str:
        """加密值"""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, encrypted: str) -> str:
        """解密值"""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        return self._fernet.decrypt(encrypted.encode()).decode()

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

    async def get_decrypted_api_key(self, provider: str) -> Optional[Dict[str, str]]:
        """
        获取解密后的 API Key（供服务使用）
        
        Args:
            provider: 提供商名称（如 'binance', 'openai', 'okx'）
        
        Returns:
            {'api_key': '...', 'secret': '...'} 或 None
        """
        keys = await self.get_api_keys()
        for k in keys:
            if k.get("provider") == provider and k.get("enabled", True):
                result = {}
                if k.get("encrypted_key"):
                    result["api_key"] = self._decrypt(k["encrypted_key"])
                if k.get("encrypted_secret"):
                    result["secret"] = self._decrypt(k["encrypted_secret"])
                return result if result else None
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
            "secret_hint": self._mask_key(secret) if secret else "",
            "encrypted_key": self._encrypt(api_key) if api_key else "",
            "encrypted_secret": self._encrypt(secret) if secret else "",
            "enabled": key_data.get("enabled", True),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        keys.append(new_key)
        await self.redis.set_json(self.API_KEYS_KEY, keys)
        logger.info(f"Created API key: {new_key['name']}")

        result = new_key.copy()
        result.pop("encrypted_key", None)
        result.pop("encrypted_secret", None)

        return result

    async def update_api_key(self, key_id: str, updates: Dict) -> Optional[Dict]:
        """更新API Key"""
        keys = await self.get_api_keys()

        for i, k in enumerate(keys):
            if k.get("id") == key_id:
                if "api_key" in updates:
                    keys[i]["key_hint"] = self._mask_key(updates["api_key"])
                    keys[i]["encrypted_key"] = self._encrypt(updates["api_key"])
                if "secret" in updates:
                    keys[i]["secret_hint"] = self._mask_key(updates["secret"])
                    keys[i]["encrypted_secret"] = self._encrypt(updates["secret"])
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
        return {
            "default_provider": "openai",
            "providers": {
                "openai": {"model": "gpt-4", "api_key_id": None},
                "anthropic": {"model": "claude-3-opus", "api_key_id": None},
                "zhipu": {"model": "glm-4", "api_key_id": None},
                "deepseek": {"model": "deepseek-chat", "api_key_id": None},
                "ollama": {"model": "llama2", "base_url": "http://localhost:11434"},
            }
        }

    async def update_llm_config(self, config: Dict) -> Dict:
        """更新LLM配置"""
        await self.redis.set_json(self.LLM_CONFIG_KEY, config)
        logger.info("Updated LLM config")
        return config

    async def get_llm_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        获取 LLM Provider 的完整配置（包含解密后的 API Key）
        
        Args:
            provider: 提供商名称（如 'openai', 'anthropic', 'zhipu'）
        
        Returns:
            {'model': '...', 'api_key': '...', 'base_url': '...'} 或 None
        """
        config = await self.get_llm_config()
        providers = config.get("providers", {})
        
        if provider not in providers:
            return None
        
        provider_config = providers[provider].copy()
        
        # 如果有关联的 API Key ID，获取解密后的 key
        api_key_id = provider_config.get("api_key_id")
        if api_key_id:
            key_data = await self.get_api_key(api_key_id)
            if key_data:
                if key_data.get("encrypted_key"):
                    provider_config["api_key"] = self._decrypt(key_data["encrypted_key"])
        else:
            # 尝试通过 provider 名称获取
            decrypted = await self.get_decrypted_api_key(provider)
            if decrypted:
                provider_config.update(decrypted)
        
        return provider_config

    async def get_exchange_config(self, exchange: str) -> Optional[Dict[str, Any]]:
        """
        获取交易所配置（包含解密后的 API Key）
        
        Args:
            exchange: 交易所名称（如 'binance', 'okx', 'bybit'）
        
        Returns:
            {'api_key': '...', 'secret': '...', 'passphrase': '...', 'testnet': bool} 或 None
        """
        decrypted = await self.get_decrypted_api_key(exchange)
        if not decrypted:
            return None
        
        config = decrypted.copy()
        
        # 获取额外配置
        all_config = await self.redis.get(self.EXCHANGE_CONFIG_KEY)
        if all_config:
            if isinstance(all_config, str):
                all_config = json.loads(all_config)
            exchange_config = all_config.get(exchange, {})
            config.update(exchange_config)
        
        return config

    async def update_exchange_config(self, exchange: str, config: Dict) -> Dict:
        """更新交易所配置"""
        all_config = await self.redis.get(self.EXCHANGE_CONFIG_KEY)
        if all_config:
            if isinstance(all_config, str):
                all_config = json.loads(all_config)
        else:
            all_config = {}
        
        all_config[exchange] = config
        await self.redis.set_json(self.EXCHANGE_CONFIG_KEY, all_config)
        logger.info(f"Updated exchange config: {exchange}")
        return config

    async def get_strategy_config(self) -> Dict:
        """获取策略配置"""
        data = await self.redis.get(self.STRATEGY_CONFIG_KEY)
        if data:
            if isinstance(data, str):
                return json.loads(data)
            return data
        return {
            "momentum_weight": 0.3,
            "trend_weight": 0.3,
            "flow_weight": 0.2,
            "sentiment_weight": 0.2,
        }

    async def update_strategy_config(self, config: Dict) -> Dict:
        """更新策略配置"""
        await self.redis.set_json(self.STRATEGY_CONFIG_KEY, config)
        logger.info("Updated strategy config")
        return config

    async def get_api_url(self, service: str, default: str = None) -> Optional[str]:
        """
        获取 API URL
        
        Args:
            service: 服务名称 (如 'binance', 'openai', 'odaily')
            default: 默认值
        
        Returns:
            API URL 或 None
        """
        data = await self.redis.get(self.API_URLS_KEY)
        if data:
            if isinstance(data, str):
                data = json.loads(data)
            return data.get(service, default)
        return default

    async def set_api_url(self, service: str, url: str) -> None:
        """设置 API URL"""
        data = await self.redis.get(self.API_URLS_KEY)
        if data:
            if isinstance(data, str):
                data = json.loads(data)
        else:
            data = {}
        
        data[service] = url
        await self.redis.set_json(self.API_URLS_KEY, data)
        logger.info(f"Updated API URL for {service}")

    async def get_all_api_urls(self) -> Dict[str, str]:
        """获取所有 API URL"""
        data = await self.redis.get(self.API_URLS_KEY)
        if data:
            if isinstance(data, str):
                return json.loads(data)
            return data
        return {}

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

    async def get_twitter_config(self) -> Dict:
        """获取 Twitter Cookie Monitor 配置"""
        data = await self.redis.get(self.TWITTER_CONFIG_KEY)
        if data:
            if isinstance(data, str):
                config = json.loads(data)
            else:
                config = data
        else:
            config = self._get_default_twitter_config()
        
        import os
        has_auth = bool(os.getenv("TWITTER_AUTH_TOKEN") and os.getenv("TWITTER_CT0"))
        
        config["has_auth"] = has_auth
        
        try:
            from services.data_service.collectors.twitter_cookie_monitor import get_twitter_cookie_monitor
            monitor = get_twitter_cookie_monitor()
            config["stats"] = monitor.get_stats()
        except Exception:
            config["stats"] = {}
        
        return config
    
    def _get_default_twitter_config(self) -> Dict:
        """获取默认 Twitter 配置"""
        return {
            "enabled": True,
            "poll_interval": 60,
            "accounts": [
                {"username": "elonmusk", "display_name": "Elon Musk", "enabled": True, "priority": 1, "keywords": [], "is_p0": True},
                {"username": "cz_binance", "display_name": "CZ", "enabled": True, "priority": 1, "keywords": [], "is_p0": True},
                {"username": "VitalikButerin", "display_name": "Vitalik Buterin", "enabled": True, "priority": 1, "keywords": [], "is_p0": True},
                {"username": "saylor", "display_name": "Michael Saylor", "enabled": True, "priority": 1, "keywords": [], "is_p0": True},
                {"username": "binance", "display_name": "Binance", "enabled": True, "priority": 2, "keywords": [], "is_p0": False},
                {"username": "Cointelegraph", "display_name": "Cointelegraph", "enabled": True, "priority": 2, "keywords": [], "is_p0": False},
            ]
        }
    
    async def update_twitter_config(self, updates: Dict) -> Dict:
        """更新 Twitter 配置"""
        config = await self.get_twitter_config()
        config.update(updates)
        config.pop("has_auth", None)
        config.pop("stats", None)
        await self.redis.set_json(self.TWITTER_CONFIG_KEY, config)
        logger.info("Updated Twitter config")
        return config
    
    async def get_twitter_accounts(self) -> List[Dict]:
        """获取 Twitter 监控账号列表"""
        config = await self.get_twitter_config()
        return config.get("accounts", [])
    
    async def create_twitter_account(self, account_data: Dict) -> Dict:
        """添加 Twitter 监控账号"""
        config = await self.redis.get(self.TWITTER_CONFIG_KEY)
        if config:
            if isinstance(config, str):
                config = json.loads(config)
        else:
            config = self._get_default_twitter_config()
        
        username = account_data.get("username", "").lstrip("@").lower()
        
        accounts = config.get("accounts", [])
        for acc in accounts:
            if acc.get("username", "").lower() == username:
                return acc
        
        new_account = {
            "username": username,
            "display_name": account_data.get("display_name", username),
            "enabled": account_data.get("enabled", True),
            "priority": account_data.get("priority", 2),
            "keywords": account_data.get("keywords", []),
            "is_p0": account_data.get("is_p0", False),
        }
        
        accounts.append(new_account)
        config["accounts"] = accounts
        await self.redis.set_json(self.TWITTER_CONFIG_KEY, config)
        logger.info(f"Added Twitter account: @{username}")
        
        return new_account
    
    async def update_twitter_account(self, username: str, updates: Dict) -> Optional[Dict]:
        """更新 Twitter 监控账号"""
        config = await self.redis.get(self.TWITTER_CONFIG_KEY)
        if config:
            if isinstance(config, str):
                config = json.loads(config)
        else:
            return None
        
        username = username.lstrip("@").lower()
        accounts = config.get("accounts", [])
        
        for i, acc in enumerate(accounts):
            if acc.get("username", "").lower() == username:
                accounts[i].update(updates)
                config["accounts"] = accounts
                await self.redis.set_json(self.TWITTER_CONFIG_KEY, config)
                logger.info(f"Updated Twitter account: @{username}")
                return accounts[i]
        
        return None
    
    async def delete_twitter_account(self, username: str) -> bool:
        """删除 Twitter 监控账号"""
        config = await self.redis.get(self.TWITTER_CONFIG_KEY)
        if config:
            if isinstance(config, str):
                config = json.loads(config)
        else:
            return False
        
        username = username.lstrip("@").lower()
        accounts = config.get("accounts", [])
        original_len = len(accounts)
        
        accounts = [acc for acc in accounts if acc.get("username", "").lower() != username]
        
        if len(accounts) < original_len:
            config["accounts"] = accounts
            await self.redis.set_json(self.TWITTER_CONFIG_KEY, config)
            logger.info(f"Deleted Twitter account: @{username}")
            return True
        
        return False

    async def get_telegram_config(self) -> Dict:
        """获取 Telegram 配置"""
        data = await self.redis.get(self.TELEGRAM_CONFIG_KEY)
        if data:
            if isinstance(data, str):
                config = json.loads(data)
            else:
                config = data
        else:
            config = self._get_default_telegram_config()
        
        import os
        has_api = bool(os.getenv("TG_API_ID") and os.getenv("TG_API_HASH"))
        config["has_api_credentials"] = has_api
        
        try:
            from services.data_service.collectors.telegram_adapter import TelegramAdapter
            config["stats"] = {"is_running": False}
        except Exception:
            config["stats"] = {}
        
        return config
    
    def _get_default_telegram_config(self) -> Dict:
        """获取默认 Telegram 配置"""
        return {
            "enabled": False,
            "channels": [
                {"channel_id": "WuBlockchain", "channel_name": "吴说区块链", "enabled": True, "priority": 1, "keywords": []},
                {"channel_id": "jinse_lab", "channel_name": "金十数据", "enabled": True, "priority": 1, "keywords": []},
                {"channel_id": "PANews", "channel_name": "PANews", "enabled": True, "priority": 2, "keywords": []},
                {"channel_id": "odaily", "channel_name": "Odaily星球日报", "enabled": True, "priority": 2, "keywords": []},
            ],
            "keywords": ["BTC", "ETH", "Bitcoin", "Ethereum", "ETF", "SEC"],
            "crypto_keywords": ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "AVAX", "LINK"],
        }
    
    async def update_telegram_config(self, updates: Dict) -> Dict:
        """更新 Telegram 配置"""
        config = await self.get_telegram_config()
        config.update(updates)
        config.pop("has_api_credentials", None)
        config.pop("stats", None)
        await self.redis.set_json(self.TELEGRAM_CONFIG_KEY, config)
        logger.info("Updated Telegram config")
        return config
    
    async def get_telegram_channels(self) -> List[Dict]:
        """获取 Telegram 监控频道列表"""
        config = await self.get_telegram_config()
        return config.get("channels", [])
    
    async def create_telegram_channel(self, channel_data: Dict) -> Dict:
        """添加 Telegram 监控频道"""
        config = await self.redis.get(self.TELEGRAM_CONFIG_KEY)
        if config:
            if isinstance(config, str):
                config = json.loads(config)
        else:
            config = self._get_default_telegram_config()
        
        channel_id = channel_data.get("channel_id", "").lstrip("@")
        
        channels = config.get("channels", [])
        for ch in channels:
            if ch.get("channel_id", "").lower() == channel_id.lower():
                return ch
        
        new_channel = {
            "channel_id": channel_id,
            "channel_name": channel_data.get("channel_name", channel_id),
            "enabled": channel_data.get("enabled", True),
            "priority": channel_data.get("priority", 2),
            "keywords": channel_data.get("keywords", []),
        }
        
        channels.append(new_channel)
        config["channels"] = channels
        await self.redis.set_json(self.TELEGRAM_CONFIG_KEY, config)
        logger.info(f"Added Telegram channel: {channel_id}")
        
        return new_channel
    
    async def update_telegram_channel(self, channel_id: str, updates: Dict) -> Optional[Dict]:
        """更新 Telegram 监控频道"""
        config = await self.redis.get(self.TELEGRAM_CONFIG_KEY)
        if config:
            if isinstance(config, str):
                config = json.loads(config)
        else:
            return None
        
        channel_id = channel_id.lstrip("@")
        channels = config.get("channels", [])
        
        for i, ch in enumerate(channels):
            if ch.get("channel_id", "").lower() == channel_id.lower():
                channels[i].update(updates)
                config["channels"] = channels
                await self.redis.set_json(self.TELEGRAM_CONFIG_KEY, config)
                logger.info(f"Updated Telegram channel: {channel_id}")
                return channels[i]
        
        return None
    
    async def delete_telegram_channel(self, channel_id: str) -> bool:
        """删除 Telegram 监控频道"""
        config = await self.redis.get(self.TELEGRAM_CONFIG_KEY)
        if config:
            if isinstance(config, str):
                config = json.loads(config)
        else:
            return False
        
        channel_id = channel_id.lstrip("@")
        channels = config.get("channels", [])
        original_len = len(channels)
        
        channels = [ch for ch in channels if ch.get("channel_id", "").lower() != channel_id.lower()]
        
        if len(channels) < original_len:
            config["channels"] = channels
            await self.redis.set_json(self.TELEGRAM_CONFIG_KEY, config)
            logger.info(f"Deleted Telegram channel: {channel_id}")
            return True
        
        return False


_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
