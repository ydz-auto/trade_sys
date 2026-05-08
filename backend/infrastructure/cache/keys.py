"""
缓存 Key 规范定义
"""

from typing import Dict, Optional
from enum import Enum

from infrastructure.cache.config import CACHE_KEY_PREFIX, CACHE_KEY_PATTERNS


class KeyPattern(str, Enum):
    MARKET_PRICE = "market:price:{symbol}"
    MARKET_DEPTH = "market:depth:{symbol}"
    MARKET_KLINE = "market:kline:{symbol}:{timeframe}"
    DATA_ETF = "data:etf:{symbol}"
    DATA_MACRO = "data:macro:{type}"
    FACTOR_SCORE = "factor:score:{symbol}"
    FACTOR_REGIME = "factor:regime:{symbol}"
    FACTOR_COMPOSITE = "factor:composite:{symbol}"
    REGIME_CURRENT = "regime:current:{symbol}"
    REGIME_RISK = "regime:risk:{symbol}"
    REGIME_HISTORY = "regime:history:{symbol}"
    USER_CONFIG = "user:config:{user_id}"
    USER_SESSION = "user:session:{session_id}"
    USER_RATE = "user:rate:{user_id}"
    SYSTEM_HEALTH = "system:health"
    SYSTEM_STATUS = "system:status:{service}"
    DECISION_SIGNAL = "decision:signal:{symbol}"
    DECISION_LAST = "decision:last:{symbol}"
    DECISION_BLOCK = "decision:block:{symbol}"


class CacheKey:
    def __init__(
        self,
        prefix: str = CACHE_KEY_PREFIX,
        service: Optional[str] = None,
        entity: Optional[str] = None,
        id: Optional[str] = None,
        field: Optional[str] = None,
    ):
        self.prefix = prefix
        self.service = service
        self.entity = entity
        self.id = id
        self.field = field
        self._key_parts = []

    def with_service(self, service: str) -> "CacheKey":
        self.service = service
        return self

    def with_entity(self, entity: str) -> "CacheKey":
        self.entity = entity
        return self

    def with_id(self, id: str) -> "CacheKey":
        self.id = id
        return self

    def with_field(self, field: str) -> "CacheKey":
        self.field = field
        return self

    def build(self) -> str:
        parts = [self.prefix]

        if self.service:
            parts.append(self.service)
        if self.entity:
            parts.append(self.entity)
        if self.id:
            parts.append(self.id)
        if self.field:
            parts.append(self.field)

        return ":".join(parts)

    @classmethod
    def from_pattern(
        cls,
        pattern: str,
        **kwargs,
    ) -> str:
        key = pattern
        for param, value in kwargs.items():
            key = key.replace(f"{{{param}}}", str(value))
        return key

    @classmethod
    def price(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["price"], symbol=symbol)

    @classmethod
    def depth(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["depth"], symbol=symbol)

    @classmethod
    def kline(cls, symbol: str, timeframe: str) -> str:
        return cls.from_pattern(
            CACHE_KEY_PATTERNS["kline"],
            symbol=symbol,
            timeframe=timeframe,
        )

    @classmethod
    def etf(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["etf"], symbol=symbol)

    @classmethod
    def macro(cls, data_type: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["macro"], type=data_type)

    @classmethod
    def factor_score(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["factor_score"], symbol=symbol)

    @classmethod
    def factor_regime(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["factor_regime"], symbol=symbol)

    @classmethod
    def factor_composite(cls, symbol: str) -> str:
        return cls.from_pattern(
            CACHE_KEY_PATTERNS["factor_composite"], symbol=symbol
        )

    @classmethod
    def regime_current(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["regime_current"], symbol=symbol)

    @classmethod
    def regime_risk(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["regime_risk"], symbol=symbol)

    @classmethod
    def regime_history(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["regime_history"], symbol=symbol)

    @classmethod
    def user_config(cls, user_id: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["user_config"], user_id=user_id)

    @classmethod
    def user_session(cls, session_id: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["user_session"], session_id=session_id)

    @classmethod
    def user_rate(cls, user_id: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["user_rate"], user_id=user_id)

    @classmethod
    def system_health(cls) -> str:
        return CACHE_KEY_PATTERNS["system_health"]

    @classmethod
    def system_status(cls, service: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["system_status"], service=service)

    @classmethod
    def decision_signal(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["decision_signal"], symbol=symbol)

    @classmethod
    def decision_last(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["decision_last"], symbol=symbol)

    @classmethod
    def decision_block(cls, symbol: str) -> str:
        return cls.from_pattern(CACHE_KEY_PATTERNS["decision_block"], symbol=symbol)


def price_key(symbol: str) -> str:
    return CacheKey.price(symbol)


def depth_key(symbol: str) -> str:
    return CacheKey.depth(symbol)


def kline_key(symbol: str, timeframe: str) -> str:
    return CacheKey.kline(symbol, timeframe)


def factor_key(symbol: str) -> str:
    return CacheKey.factor_composite(symbol)


def regime_key(symbol: str) -> str:
    return CacheKey.regime_current(symbol)


def user_config_key(user_id: str) -> str:
    return CacheKey.user_config(user_id)


def session_key(session_id: str) -> str:
    return CacheKey.user_session(session_id)