"""
Market State Types
市场状态类型定义

定义所有市场状态的枚举和不可变状态对象。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Any, Optional


class RegimeType(str, Enum):
    """市场状态类型"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    MEAN_REVERTING = "mean_reverting"
    BREAKOUT = "breakout"
    CRASH = "crash"
    SQUEEZE = "squeeze"
    QUIET = "quiet"
    AUCTION = "auction"
    UNKNOWN = "unknown"


class LiquidityState(str, Enum):
    """流动性状态"""
    NORMAL = "normal"
    THIN = "thin"
    VACUUM = "vacuum"
    FLOODED = "flooded"
    DRYING = "drying"


class PressureState(str, Enum):
    """交易压力状态"""
    BUILDUP = "buildup"
    EXHAUSTED = "exhausted"
    FLUSHED = "flushed"
    ABSORBED = "absorbed"
    DIVERGENCE = "divergence"
    NEUTRAL = "neutral"


class VolatilityState(str, Enum):
    """波动率状态"""
    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    EXTREME = "extreme"


class TrendState(str, Enum):
    """趋势状态"""
    STRONG_UP = "strong_up"
    WEAK_UP = "weak_up"
    SIDEWAYS = "sideways"
    WEAK_DOWN = "weak_down"
    STRONG_DOWN = "strong_down"


@dataclass(frozen=True)
class MarketState:
    """
    不可变的市场状态对象
    
    核心特性：
    - 完全不可变
    - 包含所有维度的市场状态
    - 提供便利的状态查询方法
    - 支持序列化
    """
    timestamp: datetime
    symbol: str
    
    # 核心状态
    regime: RegimeType
    liquidity: LiquidityState
    pressure: PressureState
    volatility: VolatilityState
    trend: TrendState
    
    # 信心度
    confidence: float = 0.0
    
    # 最后发生的事件
    last_major_event: Optional[str] = None
    
    # 特征快照（用于状态转换计算）
    feature_snapshot: Dict[str, float] = field(default_factory=dict)
    
    # 辅助指标
    oi_regime: str = "neutral"
    funding_regime: str = "normal"
    
    # 元数据
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # 基本验证
        assert 0.0 <= self.confidence <= 1.0, "confidence must be between 0 and 1"
        assert self.symbol, "symbol cannot be empty"
    
    # === 便利查询方法 ===
    def is_exhausted(self) -> bool:
        """是否处于耗尽状态"""
        return self.pressure == PressureState.EXHAUSTED
    
    def is_liquid_vacuum(self) -> bool:
        """是否处于流动性真空"""
        return self.liquidity == LiquidityState.VACUUM
    
    def is_high_confidence(self) -> bool:
        """是否为高信心状态"""
        return self.confidence > 0.7
    
    def is_trending_up(self) -> bool:
        """是否处于上升趋势"""
        return self.regime == RegimeType.TRENDING_UP or self.trend in [TrendState.STRONG_UP, TrendState.WEAK_UP]
    
    def is_trending_down(self) -> bool:
        """是否处于下降趋势"""
        return self.regime == RegimeType.TRENDING_DOWN or self.trend in [TrendState.STRONG_DOWN, TrendState.WEAK_DOWN]
    
    def is_sideways(self) -> bool:
        """是否处于横盘"""
        return self.trend == TrendState.SIDEWAYS or self.regime == RegimeType.QUIET
    
    def is_squeeze(self) -> bool:
        """是否处于挤压状态"""
        return self.regime == RegimeType.SQUEEZE
    
    def is_crash(self) -> bool:
        """是否处于崩溃状态"""
        return self.regime == RegimeType.CRASH
    
    def is_quiet(self) -> bool:
        """是否处于安静状态"""
        return self.regime == RegimeType.QUIET or self.volatility == VolatilityState.LOW
    
    def has_pressure_buildup(self) -> bool:
        """是否有压力积聚"""
        return self.pressure == PressureState.BUILDUP
    
    def has_pressure_flush(self) -> bool:
        """是否有压力释放"""
        return self.pressure == PressureState.FLUSHED
    
    def has_pressure_absorption(self) -> bool:
        """是否有压力吸收"""
        return self.pressure == PressureState.ABSORBED
    
    def has_pressure_divergence(self) -> bool:
        """是否有压力背离"""
        return self.pressure == PressureState.DIVERGENCE
    
    def has_extreme_volatility(self) -> bool:
        """是否有极端波动率"""
        return self.volatility == VolatilityState.EXTREME
    
    def has_elevated_volatility(self) -> bool:
        """是否有升高的波动率"""
        return self.volatility in [VolatilityState.ELEVATED, VolatilityState.EXTREME]
    
    def has_thin_liquidity(self) -> bool:
        """流动性是否稀薄"""
        return self.liquidity in [LiquidityState.THIN, LiquidityState.VACUUM]
    
    def has_flooded_liquidity(self) -> bool:
        """流动性是否充沛"""
        return self.liquidity == LiquidityState.FLOODED
    
    # === 序列化 ===
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于序列化"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "regime": self.regime.value,
            "liquidity": self.liquidity.value,
            "pressure": self.pressure.value,
            "volatility": self.volatility.value,
            "trend": self.trend.value,
            "confidence": self.confidence,
            "last_major_event": self.last_major_event,
            "feature_snapshot": self.feature_snapshot,
            "oi_regime": self.oi_regime,
            "funding_regime": self.funding_regime,
            "version": self.version,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketState":
        """从字典创建 MarketState"""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            symbol=data["symbol"],
            regime=RegimeType(data["regime"]),
            liquidity=LiquidityState(data["liquidity"]),
            pressure=PressureState(data["pressure"]),
            volatility=VolatilityState(data["volatility"]),
            trend=TrendState(data["trend"]),
            confidence=data.get("confidence", 0.0),
            last_major_event=data.get("last_major_event"),
            feature_snapshot=data.get("feature_snapshot", {}),
            oi_regime=data.get("oi_regime", "neutral"),
            funding_regime=data.get("funding_regime", "normal"),
            version=data.get("version", 1),
            metadata=data.get("metadata", {}),
        )
    
    def __repr__(self) -> str:
        return (
            f"MarketState(symbol={self.symbol!r}, "
            f"regime={self.regime.value!r}, "
            f"pressure={self.pressure.value!r}, "
            f"trend={self.trend.value!r}, "
            f"confidence={self.confidence:.2f})"
        )
