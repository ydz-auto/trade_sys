"""
Signal Domain Models - 信号领域核心模型
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class SignalDirection(str, Enum):
    """信号方向"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class SignalType(str, Enum):
    """信号类型"""
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    NARRATIVE = "narrative"
    ORDERBOOK = "orderbook"
    MACRO = "macro"
    LIQUIDATION = "liquidation"
    CUSTOM = "custom"


class SignalState(str, Enum):
    """信号状态（生命周期）"""
    PENDING = "pending"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass
class SignalConfidence:
    """信号置信度"""
    value: float  # 0.0-1.0
    source_weights: Dict[str, float] = field(default_factory=dict)  # 各来源权重
    evidence_count: int = 0  # 支持的证据数量
    contradictory_evidence: int = 0  # 矛盾的证据数量
    
    def __post_init__(self):
        self.value = max(0.0, min(1.0, self.value))
    
    def is_strong(self, threshold: float = 0.7) -> bool:
        return self.value >= threshold
    
    def is_weak(self, threshold: float = 0.3) -> bool:
        return self.value <= threshold


@dataclass
class SignalStrength:
    """信号强度"""
    magnitude: float  # 0.0-1.0
    volatility_adjusted: float = 0.0
    regime_adjusted: float = 0.0
    historical_success_rate: float = 0.0
    
    def __post_init__(self):
        self.magnitude = max(0.0, min(1.0, self.magnitude))


@dataclass
class Signal:
    """统一信号模型 - 系统核心真相之一（仅次于 Feature Matrix）"""
    # 核心信息（必需参数）
    symbol: str
    timeframe: str
    direction: SignalDirection
    type: SignalType
    
    # 质量指标（必需参数）
    confidence: SignalConfidence
    strength: SignalStrength
    
    # 可选参数
    signal_id: UUID = field(default_factory=uuid4)
    state: SignalState = SignalState.PENDING
    generated_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    ttl_seconds: Optional[int] = None
    source_features: List[str] = field(default_factory=list)  # 依赖的特征
    source_signals: List[UUID] = field(default_factory=list)  # 依赖的其他信号
    strategy_id: Optional[str] = None  # 生成策略（如果有）
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    
    def activate(self) -> None:
        """激活信号"""
        if self.state == SignalState.PENDING:
            self.state = SignalState.ACTIVE
            self.activated_at = datetime.utcnow()
    
    def deactivate(self) -> None:
        """停用信号"""
        if self.state == SignalState.ACTIVE:
            self.state = SignalState.DEACTIVATED
    
    def expire(self) -> None:
        """过期信号"""
        self.state = SignalState.EXPIRED
    
    def is_active(self) -> bool:
        """是否活跃"""
        if self.state != SignalState.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def is_expired(self) -> bool:
        """是否过期"""
        if self.state == SignalState.EXPIRED:
            return True
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    def remaining_ttl(self) -> Optional[float]:
        """剩余TTL（秒）"""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0.0, delta.total_seconds())
    
    def age_seconds(self) -> float:
        """信号年龄（秒）"""
        return (datetime.utcnow() - self.generated_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": str(self.signal_id),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "type": self.type.value,
            "confidence": {
                "value": self.confidence.value,
                "source_weights": self.confidence.source_weights,
                "evidence_count": self.confidence.evidence_count,
            },
            "strength": {
                "magnitude": self.strength.magnitude,
                "historical_success_rate": self.strength.historical_success_rate,
            },
            "state": self.state.value,
            "generated_at": self.generated_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "source_features": self.source_features,
            "source_signals": [str(s) for s in self.source_signals],
            "strategy_id": self.strategy_id,
            "metadata": self.metadata,
            "version": self.version,
        }
