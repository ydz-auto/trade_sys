"""
P0-1: Event Protocol - 事件协议

三种时间语义：
- event_time_ms: 事件发生时间（交易所时间）
- available_time_ms: 特征可用时间（通常 = event_time + 延迟）
- processing_time_ms: 系统处理时间

关键约束：
1. event_time <= available_time <= processing_time
2. 策略只能看到 available_time <= processing_time 的事件
3. 事件一旦创建就不可变（Immutable Event）

Time Authority 规则：
- runtime/ 层: 必须用 RuntimeClock.now_ms()
- domain/ 层: 保持抽象，由调用者注入时间源
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import hashlib
from datetime import datetime

from domain.logging import get_logger

logger = get_logger("domain.event.protocol")

# 时间源类型定义（domain 层保持抽象）
# 调用者注入具体实现（REPLAY: RuntimeClock.now_ms, LIVE: datetime.now）
TimeSource = Callable[[], int]


def _default_time_source() -> int:
    """默认时间源（UTC）"""
    return int(datetime.utcnow().timestamp() * 1000)


# ============================================
# FrozenDict - 不可变字典
# ============================================

class FrozenDict:
    """不可变字典，用于 Immutable Event 的 payload"""
    
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = dict(data or {})
        self._hash = None
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __contains__(self, key):
        return key in self._data
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def keys(self):
        return self._data.keys()
    
    def values(self):
        return self._data.values()
    
    def items(self):
        return self._data.items()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为普通字典（用于序列化）"""
        return dict(self._data)
    
    def __repr__(self):
        return f"FrozenDict({self._data})"
    
    def __len__(self):
        return len(self._data)
    
    def __hash__(self):
        if self._hash is None:
            self._hash = hash(json.dumps(self._data, sort_keys=True))
        return self._hash
    
    def __eq__(self, other):
        if isinstance(other, FrozenDict):
            return self._data == other._data
        return False


# ============================================
# Event Protocol Types
# ============================================

class EventSource(Enum):
    """事件来源"""
    REPLAY = "replay"
    LIVE = "live"
    PAPER = "paper"
    HISTORICAL = "historical"


class EventProtocolVersion(Enum):
    """事件协议版本"""
    V1 = "1.0"
    V2 = "2.0"  # P0 版本


# ============================================
# Immutable Event - 不可变事件
# ============================================

@dataclass(frozen=True)  # frozen=True 保证不可变
class ImmutableEvent:
    """
    不可变事件 - P0-2 核心组件
    
    设计原则：
    - 事件一旦创建，任何字段都不可修改
    - 有 cryptographic hash 验证完整性
    - 三种时间语义完整
    """
    
    # 核心标识
    event_id: str
    event_type: str
    symbol: str
    exchange: str
    
    # ========================================
    # P0-1: 三种时间语义
    # ========================================
    
    # 1. event_time_ms: 事件发生时间（交易所时间）
    # 这是事件实际发生的时间，来自交易所
    event_time_ms: int
    
    # 2. available_time_ms: 特征可用时间
    # 通常 = event_time_ms + 延迟
    # 策略只能看到 available_time_ms <= processing_time_ms 的特征
    available_time_ms: int
    
    # 3. processing_time_ms: 系统处理时间
    # 系统实际处理该事件的时间
    # REPLAY 模式下 = replay_clock，LIVE 模式下 = wall_clock
    processing_time_ms: int
    
    # 数据载荷（不可变）
    payload: FrozenDict
    
    # 元数据
    source: EventSource
    protocol_version: EventProtocolVersion = EventProtocolVersion.V2
    
    # 完整性验证
    verification_hash: str = ""
    
    # 创建时间（不可变）
    created_at_ms: int = 0
    
    def __post_init__(self):
        """
        验证并计算哈希
        
        注意：由于 frozen=True，我们只能通过 object.__setattr__ 来设置
        """
        # 1. 验证时间语义
        self._validate_time_semantics()
        
        # 2. 计算验证哈希
        if not self.verification_hash:
            hash_value = self._compute_hash()
            object.__setattr__(self, 'verification_hash', hash_value)
    
    def _validate_time_semantics(self):
        """
        P0-1: 验证时间语义
        
        约束：
        1. event_time_ms <= available_time_ms
        2. available_time_ms <= processing_time_ms
        3. 所有时间都是正整数
        """
        # 验证时间类型
        for name, value in [
            ("event_time_ms", self.event_time_ms),
            ("available_time_ms", self.available_time_ms),
            ("processing_time_ms", self.processing_time_ms),
        ]:
            if not isinstance(value, int):
                raise TypeError(f"{name} must be int, got {type(value).__name__}")
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")
        
        # 验证时间顺序
        if self.event_time_ms > self.available_time_ms:
            raise ValueError(
                f"event_time_ms ({self.event_time_ms}) > available_time_ms ({self.available_time_ms})"
            )
        
        if self.available_time_ms > self.processing_time_ms:
            raise ValueError(
                f"available_time_ms ({self.available_time_ms}) > processing_time_ms ({self.processing_time_ms})"
            )
    
    def _compute_hash(self) -> str:
        """
        计算内容哈希
        
        用于验证事件完整性
        """
        hash_content = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "event_time_ms": self.event_time_ms,
            "available_time_ms": self.available_time_ms,
            "processing_time_ms": self.processing_time_ms,
            "payload": self.payload.to_dict(),
            "source": self.source.value,
            "protocol_version": self.protocol_version.value,
        }
        
        content_bytes = json.dumps(hash_content, sort_keys=True).encode('utf-8')
        return hashlib.sha256(content_bytes).hexdigest()[:32]
    
    def verify_integrity(self) -> bool:
        """验证事件完整性"""
        return self.verification_hash == self._compute_hash()
    
    def is_available_at(self, clock_time_ms: int) -> bool:
        """
        P0-3: 检查事件在指定时间是否可用
        
        策略只能使用 available_time_ms <= clock_time_ms 的事件
        """
        return self.available_time_ms <= clock_time_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "event_time_ms": self.event_time_ms,
            "available_time_ms": self.available_time_ms,
            "processing_time_ms": self.processing_time_ms,
            "payload": self.payload.to_dict(),
            "source": self.source.value,
            "protocol_version": self.protocol_version.value,
            "verification_hash": self.verification_hash,
            "created_at_ms": self.created_at_ms,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImmutableEvent':
        """从字典创建"""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            event_time_ms=data["event_time_ms"],
            available_time_ms=data["available_time_ms"],
            processing_time_ms=data["processing_time_ms"],
            payload=FrozenDict(data["payload"]),
            source=EventSource(data["source"]),
            protocol_version=EventProtocolVersion(data.get("protocol_version", "2.0")),
            verification_hash=data.get("verification_hash", ""),
            created_at_ms=data.get("created_at_ms", 0),
        )
    
    def __repr__(self):
        return (
            f"ImmutableEvent("
            f"id={self.event_id}, "
            f"type={self.event_type}, "
            f"symbol={self.symbol}, "
            f"event_time={self.event_time_ms}, "
            f"available_time={self.available_time_ms}"
            f")"
        )


# ============================================
# Event Builder - 事件构建器
# ============================================

class ImmutableEventBuilder:
    """
    不可变事件构建器
    
    用于安全地创建 ImmutableEvent
    支持 Time Authority：调用者注入时间源
    """
    
    def __init__(self):
        self._event_id: Optional[str] = None
        self._event_type: Optional[str] = None
        self._symbol: Optional[str] = None
        self._exchange: Optional[str] = None
        self._event_time_ms: Optional[int] = None
        self._available_time_ms: Optional[int] = None
        self._processing_time_ms: Optional[int] = None
        self._payload: Dict[str, Any] = {}
        self._source: EventSource = EventSource.LIVE
        self._created_at_ms: Optional[int] = None
        self._time_source: TimeSource = _default_time_source  # 可注入的时间源
    
    def event_id(self, event_id: str) -> 'ImmutableEventBuilder':
        self._event_id = event_id
        return self
    
    def event_type(self, event_type: str) -> 'ImmutableEventBuilder':
        self._event_type = event_type
        return self
    
    def symbol(self, symbol: str) -> 'ImmutableEventBuilder':
        self._symbol = symbol
        return self
    
    def exchange(self, exchange: str) -> 'ImmutableEventBuilder':
        self._exchange = exchange
        return self
    
    def event_time_ms(self, event_time_ms: int) -> 'ImmutableEventBuilder':
        self._event_time_ms = event_time_ms
        return self
    
    def available_time_ms(self, available_time_ms: int) -> 'ImmutableEventBuilder':
        self._available_time_ms = available_time_ms
        return self
    
    def available_after_ms(self, delay_ms: int) -> 'ImmutableEventBuilder':
        """设置 available_time = event_time + delay"""
        if self._event_time_ms is None:
            raise ValueError("event_time_ms must be set first")
        self._available_time_ms = self._event_time_ms + delay_ms
        return self
    
    def processing_time_ms(self, processing_time_ms: int) -> 'ImmutableEventBuilder':
        self._processing_time_ms = processing_time_ms
        return self
    
    def payload(self, payload: Dict[str, Any]) -> 'ImmutableEventBuilder':
        self._payload = payload.copy()
        return self
    
    def source(self, source: EventSource) -> 'ImmutableEventBuilder':
        self._source = source
        return self
    
    def created_at_ms(self, created_at_ms: int) -> 'ImmutableEventBuilder':
        self._created_at_ms = created_at_ms
        return self
    
    def time_source(self, time_source: TimeSource) -> 'ImmutableEventBuilder':
        """注入时间源（用于 RuntimeClock 集成）"""
        self._time_source = time_source
        return self
    
    def build(self) -> ImmutableEvent:
        """构建 ImmutableEvent"""
        # 验证必填字段
        required = [
            ("event_id", self._event_id),
            ("event_type", self._event_type),
            ("symbol", self._symbol),
            ("exchange", self._exchange),
            ("event_time_ms", self._event_time_ms),
        ]
        
        for name, value in required:
            if value is None:
                raise ValueError(f"{name} is required")
        
        # 默认值处理
        if self._available_time_ms is None:
            self._available_time_ms = self._event_time_ms
        
        if self._processing_time_ms is None:
            self._processing_time_ms = self._available_time_ms
        
        if self._created_at_ms is None:
            self._created_at_ms = self._time_source()  # 使用注入的时间源
        
        return ImmutableEvent(
            event_id=self._event_id,
            event_type=self._event_type,
            symbol=self._symbol,
            exchange=self._exchange,
            event_time_ms=self._event_time_ms,
            available_time_ms=self._available_time_ms,
            processing_time_ms=self._processing_time_ms,
            payload=FrozenDict(self._payload),
            source=self._source,
            created_at_ms=self._created_at_ms,
        )


# ============================================
# Convenience Functions
# ============================================

def create_event(
    event_type: str,
    symbol: str,
    exchange: str,
    event_time_ms: int,
    payload: Dict[str, Any],
    available_time_ms: Optional[int] = None,
    processing_time_ms: Optional[int] = None,
    source: EventSource = EventSource.LIVE,
    time_source: Optional[TimeSource] = None,
) -> ImmutableEvent:
    """
    便捷函数：创建 ImmutableEvent
    
    Time Authority:
    - REPLAY 模式: 使用 RuntimeClock.now_ms() 作为 time_source
    - LIVE 模式: 使用 datetime.utcnow() 或 exchange_time
    
    Args:
        event_type: 事件类型
        symbol: 交易对
        exchange: 交易所
        event_time_ms: 事件发生时间（交易所时间）
        payload: 数据载荷
        available_time_ms: 可用时间（默认 = event_time_ms）
        processing_time_ms: 处理时间（默认 = available_time_ms）
        source: 事件来源
        time_source: 时间源函数（默认使用 UTC 时间）
    """
    event_id = f"{event_type}_{symbol}_{event_time_ms}"
    
    builder = ImmutableEventBuilder()
    builder.event_id(event_id)
    builder.event_type(event_type)
    builder.symbol(symbol)
    builder.exchange(exchange)
    builder.event_time_ms(event_time_ms)
    
    if available_time_ms is not None:
        builder.available_time_ms(available_time_ms)
    
    if processing_time_ms is not None:
        builder.processing_time_ms(processing_time_ms)
    
    builder.payload(payload)
    builder.source(source)
    
    # 使用注入的时间源
    if time_source is not None:
        builder.time_source(time_source)
    
    return builder.build()


def create_replay_event(
    event_type: str,
    symbol: str,
    exchange: str,
    event_time_ms: int,
    payload: Dict[str, Any],
    replay_clock_ms: int,
    network_delay_ms: int = 100,
    processing_delay_ms: int = 50,
) -> ImmutableEvent:
    """
    REPLAY 模式专用：创建事件
    
    Time Authority 规则：
    - event_time_ms: 来自回放数据
    - available_time_ms: event_time_ms + network_delay_ms + processing_delay_ms
    - processing_time_ms: replay_clock_ms（当前回放时间）
    """
    available_time_ms = event_time_ms + network_delay_ms + processing_delay_ms
    
    # REPLAY 模式下，processing_time_ms = replay_clock
    return create_event(
        event_type=event_type,
        symbol=symbol,
        exchange=exchange,
        event_time_ms=event_time_ms,
        payload=payload,
        available_time_ms=available_time_ms,
        processing_time_ms=replay_clock_ms,
        source=EventSource.REPLAY,
    )


def create_live_event(
    event_type: str,
    symbol: str,
    exchange: str,
    event_time_ms: int,
    payload: Dict[str, Any],
    processing_delay_ms: int = 50,
) -> ImmutableEvent:
    """
    LIVE 模式专用：创建事件
    
    Time Authority 规则：
    - event_time_ms: 来自交易所
    - available_time_ms: event_time_ms + processing_delay_ms
    - processing_time_ms: 当前 UTC 时间
    """
    import time
    processing_time_ms = int(time.time() * 1000)
    available_time_ms = event_time_ms + processing_delay_ms
    
    return create_event(
        event_type=event_type,
        symbol=symbol,
        exchange=exchange,
        event_time_ms=event_time_ms,
        payload=payload,
        available_time_ms=available_time_ms,
        processing_time_ms=processing_time_ms,
        source=EventSource.LIVE,
    )


def verify_event(event: ImmutableEvent) -> tuple[bool, list[str]]:
    """
    验证事件
    
    Returns:
        (is_valid, issues)
    """
    issues = []
    
    # 1. 验证完整性
    if not event.verify_integrity():
        issues.append("Integrity verification failed: hash mismatch")
    
    # 2. 验证时间语义（__post_init__ 已经做了，但这里再检查一次）
    try:
        if event.event_time_ms > event.available_time_ms:
            issues.append("event_time > available_time")
        
        if event.available_time_ms > event.processing_time_ms:
            issues.append("available_time > processing_time")
    except Exception as e:
        issues.append(f"Time validation error: {e}")
    
    return len(issues) == 0, issues
