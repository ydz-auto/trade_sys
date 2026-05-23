"""
Config 管理器实现
"""

import time
import json
from typing import Dict, List, Optional, Any, Callable

from infrastructure.config.defaults.index import (
    DEFAULT_CONFIGS,
    CONFIG_SCHEMAS,
    CONFIG_CATEGORIES,
)
from infrastructure.config.schemas import (
    ConfigEntry,
    ConfigVersion,
    ConfigSchema,
)
from infrastructure.config.enums import (
    ConfigCategory,
    ConfigScope,
)


class ConfigValidationError(Exception):
    pass


class ConfigNotFoundError(Exception):
    pass


class ConfigVersionConflictError(Exception):
    pass


class ConfigManager:
    def __init__(self, redis_client=None, db_client=None):
        self._redis = redis_client
        self._db = db_client
        self._memory_config: Dict[str, Any] = {}
        self._schemas: Dict[str, ConfigSchema] = {}
        for key, schema_dict in CONFIG_SCHEMAS.items():
            schema_dict_copy = schema_dict.copy()
            schema_dict_copy.setdefault('category', 'general')
            self._schemas[key] = ConfigSchema(**schema_dict_copy, key=key)
        self._versions: Dict[str, List[ConfigVersion]] = {}
        self._subscribers: Dict[str, List[Callable]] = {}

    def set_redis(self, redis_client):
        self._redis = redis_client

    def set_db(self, db_client):
        self._db = db_client

    def register_schema(self, schema: ConfigSchema):
        self._schemas[schema.key] = schema

    def get_schema(self, key: str) -> Optional[ConfigSchema]:
        return self._schemas.get(key)

    def get(self, key: str, default: Any = None, user_id: Optional[str] = None) -> Any:
        scope_key = f"{key}:{user_id}" if user_id else key

        if scope_key in self._memory_config:
            return self._memory_config[scope_key]

        if key in self._memory_config:
            return self._memory_config[key]

        if self._redis:
            cached = self._redis.get(f"config:{scope_key}")
            if cached:
                return json.loads(cached) if isinstance(cached, str) else cached

        if self._db:
            pass

        return DEFAULT_CONFIGS.get(key, default)

    def set(
        self,
        key: str,
        value: Any,
        user_id: Optional[str] = None,
        changed_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ConfigEntry:
        schema = self._schemas.get(key)
        if schema:
            valid, error_msg = schema.validate(value)
            if not valid:
                raise ConfigValidationError(error_msg)

        old_value = self.get(key, user_id=user_id)

        scope_key = f"{key}:{user_id}" if user_id else key
        self._memory_config[scope_key] = value

        if self._redis:
            self._redis.set(f"config:{scope_key}", json.dumps(value))

        self._record_version(key, old_value, value, changed_by, reason)

        self._notify_subscribers(key, value, old_value)

        entry = ConfigEntry(
            key=key,
            value=value,
            category=schema.category if schema else "general",
            scope=schema.scope if schema else ConfigScope.GLOBAL.value,
            version=self._get_version(key),
            created_at=int(time.time()),
            updated_at=int(time.time()),
            created_by=changed_by,
            updated_by=changed_by,
        )

        return entry

    def _record_version(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
        changed_by: Optional[str],
        reason: Optional[str],
    ):
        if key not in self._versions:
            self._versions[key] = []

        version = ConfigVersion(
            version=len(self._versions[key]) + 1,
            config_key=key,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by or "system",
            changed_at=int(time.time()),
            reason=reason,
        )

        self._versions[key].append(version)

        if len(self._versions[key]) > 100:
            self._versions[key] = self._versions[key][-100:]

    def _get_version(self, key: str) -> int:
        return len(self._versions.get(key, []))

    def get_versions(self, key: str, limit: int = 100) -> List[ConfigVersion]:
        return self._versions.get(key, [])[-limit:]

    def get_history(
        self,
        key: str,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        versions = self.get_versions(key, limit)
        return [v.to_dict() for v in versions]

    def delete(self, key: str, user_id: Optional[str] = None):
        scope_key = f"{key}:{user_id}" if user_id else key

        if scope_key in self._memory_config:
            del self._memory_config[scope_key]

        if self._redis:
            self._redis.delete(f"config:{scope_key}")

    def get_category(self, category: ConfigCategory) -> Dict[str, Any]:
        keys = CONFIG_CATEGORIES.get(category, [])
        result = {}
        for key in keys:
            result[key] = self.get(key)
        return result

    def get_all(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        all_keys = set(DEFAULT_CONFIGS.keys()) | set(self._memory_config.keys())

        result = {}
        for key in all_keys:
            value = self.get(key, user_id=user_id)
            if value is not None:
                result[key] = value

        return result

    def reset_to_default(self, key: str, user_id: Optional[str] = None):
        default_value = DEFAULT_CONFIGS.get(key)
        if default_value is not None:
            self.set(key, default_value, user_id=user_id, reason="Reset to default")

    def reset_all(self, user_id: Optional[str] = None):
        for key in DEFAULT_CONFIGS.keys():
            self.reset_to_default(key, user_id)

    def subscribe(self, key: str, callback: Callable):
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(callback)

    def unsubscribe(self, key: str, callback: Callable):
        if key in self._subscribers and callback in self._subscribers[key]:
            self._subscribers[key].remove(callback)

    def _notify_subscribers(self, key: str, new_value: Any, old_value: Any):
        if key in self._subscribers:
            for callback in self._subscribers[key]:
                try:
                    callback(key, new_value, old_value)
                except Exception:
                    pass

    def export_config(self) -> str:
        return json.dumps(self.get_all(), indent=2)

    def import_config(self, config_json: str, user_id: Optional[str] = None):
        config = json.loads(config_json)
        for key, value in config.items():
            try:
                self.set(key, value, user_id=user_id, reason="Import config")
            except ConfigValidationError:
                pass

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        errors = {}
        for key, value in config.items():
            schema = self._schemas.get(key)
            if schema:
                valid, error_msg = schema.validate(value)
                if not valid:
                    errors[key] = [error_msg]
        return errors


class StrategyConfigManager(ConfigManager):
    def get_strategy_config(self, strategy_id: str) -> Dict[str, Any]:
        return self.get(f"strategy:{strategy_id}", user_id=strategy_id)

    def set_strategy_config(
        self,
        strategy_id: str,
        config: Dict[str, Any],
        changed_by: Optional[str] = None,
    ):
        for key, value in config.items():
            full_key = f"strategy:{strategy_id}:{key}"
            self.set(full_key, value, user_id=strategy_id, changed_by=changed_by)

    def get_strategy_parameter(self, strategy_id: str, param: str) -> Any:
        return self.get(f"strategy:{strategy_id}:{param}", user_id=strategy_id)

    def set_strategy_parameter(
        self,
        strategy_id: str,
        param: str,
        value: Any,
        changed_by: Optional[str] = None,
    ):
        full_key = f"strategy:{strategy_id}:{param}"
        self.set(full_key, value, user_id=strategy_id, changed_by=changed_by)


class UserConfigManager(ConfigManager):
    def get_user_config(self, user_id: str, key: str) -> Any:
        return self.get(key, user_id=user_id)

    def set_user_config(
        self,
        user_id: str,
        key: str,
        value: Any,
        changed_by: Optional[str] = None,
    ):
        self.set(key, value, user_id=user_id, changed_by=changed_by)

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        return self.get_all(user_id=user_id)


class DataSourceConfigManager(ConfigManager):
    def get_symbols(self) -> List[str]:
        return self.get("datasource.symbols")

    def set_symbols(self, symbols: List[str], changed_by: Optional[str] = None):
        self.set("datasource.symbols", symbols, changed_by=changed_by, reason="Update symbols")

    def get_exchanges(self) -> List[str]:
        return self.get("datasource.exchanges")

    def set_exchanges(self, exchanges: List[str], changed_by: Optional[str] = None):
        self.set("datasource.exchanges", exchanges, changed_by=changed_by, reason="Update exchanges")

    def get_check_interval(self) -> int:
        return self.get("datasource.check_interval")

    def set_check_interval(self, interval: int, changed_by: Optional[str] = None):
        self.set("datasource.check_interval", interval, changed_by=changed_by, reason="Update check interval")

    def get_news_feeds(self) -> Dict[str, str]:
        return self.get("datasource.news.feeds")

    def set_news_feed(self, source: str, url: str, changed_by: Optional[str] = None):
        feeds = self.get_news_feeds()
        feeds[source] = url
        self.set("datasource.news.feeds", feeds, changed_by=changed_by, reason=f"Add news feed: {source}")

    def remove_news_feed(self, source: str, changed_by: Optional[str] = None):
        feeds = self.get_news_feeds()
        if source in feeds:
            del feeds[source]
            self.set("datasource.news.feeds", feeds, changed_by=changed_by, reason=f"Remove news feed: {source}")

    def get_news_check_interval(self) -> int:
        return self.get("datasource.news.check_interval")

    def get_macro_check_interval(self) -> int:
        return self.get("datasource.macro.check_interval")

    def get_macro_apis(self) -> Dict[str, str]:
        return {
            "gold": self.get("datasource.macro.gold_api"),
            "oil": self.get("datasource.macro.oil_api"),
        }

    def get_etf_enabled(self) -> bool:
        return self.get("datasource.etf.enabled")

    def get_etf_check_interval(self) -> int:
        return self.get("datasource.etf.check_interval")

    def get_etf_symbols(self) -> list:
        return self.get("datasource.etf.symbols")

    def get_etf_api_farside(self) -> str:
        return self.get("datasource.etf.api_farside")

    def is_exchange_enabled(self, exchange: str) -> bool:
        return self.get(f"datasource.exchange.{exchange}.enabled", default=True)

    def get_all_datasource_config(self) -> Dict[str, Any]:
        return {
            "symbols": self.get_symbols(),
            "exchanges": self.get_exchanges(),
            "check_interval": self.get_check_interval(),
            "news_feeds": self.get_news_feeds(),
            "news_check_interval": self.get_news_check_interval(),
            "macro_apis": self.get_macro_apis(),
            "macro_check_interval": self.get_macro_check_interval(),
            "etf_enabled": self.get_etf_enabled(),
            "etf_check_interval": self.get_etf_check_interval(),
            "etf_symbols": self.get_etf_symbols(),
            "etf_api_farside": self.get_etf_api_farside(),
        }


_config_manager: Optional[ConfigManager] = None
_strategy_config_manager: Optional[StrategyConfigManager] = None
_user_config_manager: Optional[UserConfigManager] = None
_datasource_config_manager: Optional[DataSourceConfigManager] = None


def get_config_manager() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_strategy_config_manager() -> StrategyConfigManager:
    global _strategy_config_manager
    if _strategy_config_manager is None:
        _strategy_config_manager = StrategyConfigManager()
    return _strategy_config_manager


def get_user_config_manager() -> UserConfigManager:
    global _user_config_manager
    if _user_config_manager is None:
        _user_config_manager = UserConfigManager()
    return _user_config_manager


def get_datasource_config_manager() -> DataSourceConfigManager:
    global _datasource_config_manager
    if _datasource_config_manager is None:
        _datasource_config_manager = DataSourceConfigManager()
    return _datasource_config_manager