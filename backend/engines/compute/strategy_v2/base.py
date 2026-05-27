"""
Strategy V2 Base - 策略基类

核心设计原则：
1. 策略只接收 MarketContext，不直接读 features
2. 每个策略必须声明 StrategyMeta
3. 信号生成遵循固定流程：过滤 → 判断 → 计算置信度
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Any

from engines.compute.context import MarketContext

from .metadata import StrategyMeta


# ============== 信号类型 ==============

class SignalType(Enum):
    LONG = auto()
    SHORT = auto()
    NONE = auto()
    EXIT = auto()


@dataclass(frozen=True)
class Signal:
    """
    策略信号
    
    设计原则：
    1. 不可变对象
    2. 包含方向、置信度、理由
    3. 支持比较和哈希
    """
    
    type: SignalType
    confidence: float = 0.0
    reason: str = ""
    metadata: dict = field(default_factory=dict)
    
    @classmethod
    def long(cls, confidence: float = 0.5, reason: str = "", **kwargs) -> "Signal":
        return cls(
            type=SignalType.LONG,
            confidence=min(1.0, max(0.0, confidence)),
            reason=reason,
            metadata=kwargs,
        )
    
    @classmethod
    def short(cls, confidence: float = 0.5, reason: str = "", **kwargs) -> "Signal":
        return cls(
            type=SignalType.SHORT,
            confidence=min(1.0, max(0.0, confidence)),
            reason=reason,
            metadata=kwargs,
        )
    
    @classmethod
    def none(cls, reason: str = "") -> "Signal":
        return cls(
            type=SignalType.NONE,
            confidence=0.0,
            reason=reason,
        )
    
    @classmethod
    def exit(cls, reason: str = "") -> "Signal":
        return cls(
            type=SignalType.EXIT,
            confidence=1.0,
            reason=reason,
        )
    
    @property
    def is_long(self) -> bool:
        return self.type == SignalType.LONG
    
    @property
    def is_short(self) -> bool:
        return self.type == SignalType.SHORT
    
    @property
    def is_none(self) -> bool:
        return self.type == SignalType.NONE
    
    @property
    def is_exit(self) -> bool:
        return self.type == SignalType.EXIT


# ============== 策略基类 ==============

class StrategyV2(ABC):
    """
    策略 V2 基类
    
    核心约定：
    1. 子类必须定义 meta 类属性
    2. 策略只接收 MarketContext，不直接访问 raw features
    3. 信号生成必须通过 generate_signal 方法
    """
    
    meta: StrategyMeta
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        
        # 验证策略元数据
        if not hasattr(self, 'meta') or not isinstance(self.meta, StrategyMeta):
            raise ValueError(f"策略 {self.__class__.__name__} 必须定义 meta 属性")
    
    @abstractmethod
    def generate_signal(self, ctx: MarketContext) -> Signal:
        """
        生成交易信号
        
        Args:
            ctx: MarketContext 实例
        
        Returns:
            Signal 实例
        """
        pass
    
    def get_required_features(self) -> list:
        """
        获取策略所需的原料特征列表
        
        Returns:
            特征名称列表
        """
        from engines.compute.context import get_required_features
        return get_required_features(self.meta.required_context)
    
    def validate_requirements(self, ctx: MarketContext) -> tuple[bool, list[str]]:
        """
        验证上下文是否满足策略需求
        
        Args:
            ctx: MarketContext 实例
        
        Returns:
            (是否满足, 错误消息列表)
        """
        from engines.compute.context import validate_strategy_requirements
        return validate_strategy_requirements(self.meta.required_context, ctx)


# ============== 辅助函数 ==============

def combine_signals(signals: list[Signal]) -> Signal:
    """
    组合多个信号
    
    Args:
        signals: 信号列表
    
    Returns:
        综合信号
    """
    if not signals:
        return Signal.none()
    
    # 过滤有效信号
    valid_signals = [s for s in signals if s.type in [SignalType.LONG, SignalType.SHORT]]
    
    if not valid_signals:
        return Signal.none()
    
    # 如果有 exit 信号，优先返回
    exit_signals = [s for s in signals if s.is_exit]
    if exit_signals:
        return exit_signals[0]
    
    # 计算综合置信度
    long_confidence = sum(s.confidence for s in valid_signals if s.is_long)
    short_confidence = sum(s.confidence for s in valid_signals if s.is_short)
    
    if long_confidence > short_confidence:
        return Signal.long(
            confidence=min(1.0, long_confidence / len(valid_signals)),
            reason="combined_long"
        )
    else:
        return Signal.short(
            confidence=min(1.0, short_confidence / len(valid_signals)),
            reason="combined_short"
        )


__all__ = [
    "SignalType",
    "Signal",
    "StrategyV2",
    "combine_signals",
]
