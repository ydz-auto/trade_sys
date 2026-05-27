"""
MarketContext - 统一市场上下文层

核心设计原则：
1. 单一真相源（Single Source of Truth）：市场状态唯一来源
2. 事件驱动更新：只有经过这里的事件才能更新状态
3. 只读消费层：策略只能消费上下文，不能直接修改
4. 所有 runtime 对齐：replay/backtest/live 必须使用同一个

这解决了之前的问题：
- ❌ 分散式隐式上下文 → ✅ 集中式显式上下文
- ❌ 策略自己解释市场 → ✅ 系统统一解释，策略只能消费
- ❌ 双 context 体系 → ✅ 单一 context 权威层
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum, auto

from domain.market_state.state import (
    RegimeType,
    LiquidityState,
    PressureState,
    VolatilityState,
    TrendState,
)
from domain.market_state.state import MarketState

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketContext:
    """
    统一市场上下文（唯一真相源）
    
    这是所有策略和运行时的唯一市场状态输入，
    禁止策略从其他地方读取市场状态。
    
    结构设计：
    - core: 核心状态机状态（从 MarketStateMachine 来）
    - features: 特征快照（只读，用于辅助，但决策应主要依赖 core）
    - events: 最近事件历史（用于上下文理解）
    """
    
    # 核心状态机状态（权威层）
    core: MarketState
    
    # 特征快照（辅助层，只读，不作为主要决策依据）
    features: Dict[str, float] = field(default_factory=dict)
    
    # 最近事件历史（用于上下文理解）
    recent_events: list = field(default_factory=list)
    
    # 生成时间戳
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    # ============== 语义化接口（策略只能消费这个）==============
    
    def is_exhausted(self) -> bool:
        """是否处于压力耗尽状态"""
        return self.core.pressure == PressureState.EXHAUSTED
    
    def is_liquid_vacuum(self) -> bool:
        """是否处于流动性真空"""
        return self.core.liquidity == LiquidityState.VACUUM
    
    def is_high_confidence_trend(self) -> bool:
        """是否有高置信度趋势"""
        return self.core.confidence > 0.75 and self.core.regime in (
            RegimeType.TRENDING_UP,
            RegimeType.TRENDING_DOWN
        )
    
    def is_flush(self) -> bool:
        """是否刚经历流动性 flush"""
        return self.core.pressure == PressureState.FLUSHED
    
    def is_squeeze(self) -> bool:
        """是否处于挤压 regime"""
        return self.core.regime == RegimeType.SQUEEZE
    
    def is_quiet(self) -> bool:
        """是否处于低波动安静状态"""
        return self.core.regime == RegimeType.QUIET
    
    def get_trend_strength(self) -> float:
        """获取趋势强度（0-1）"""
        if self.core.trend in (TrendState.STRONG_UP, TrendState.STRONG_DOWN):
            return self.core.confidence
        elif self.core.trend in (TrendState.WEAK_UP, TrendState.WEAK_DOWN):
            return self.core.confidence * 0.6
        return 0.0
    
    def get_liquidity_quality(self) -> float:
        """获取流动性质量（0-1）"""
        liquidity_score = {
            LiquidityState.NORMAL: 1.0,
            LiquidityState.THIN: 0.6,
            LiquidityState.VACUUM: 0.3,
            LiquidityState.FLOODED: 0.8,
        }
        return liquidity_score.get(self.core.liquidity, 0.5)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化（用于回放/存储）"""
        return {
            "core": self.core.to_dict(),
            "features": self.features,
            "recent_events": [str(e) for e in self.recent_events],
            "generated_at": self.generated_at.isoformat(),
        }


class MarketContextAuthority:
    """
    市场上下文权威层
    
    职责：
    1. 唯一负责更新 MarketContext
    2. 确保所有 runtime 对齐
    3. 提供统一的上下文消费接口
    4. 禁止绕过该层直接访问状态
    """
    
    def __init__(self, state_machine):
        self._state_machine = state_machine
        self._current_context: Optional[MarketContext] = None
        self._context_history: list[MarketContext] = []
        self._max_history = 1000  # 保留最近 1000 个上下文快照
    
    def update(
        self,
        event,
        features: Dict[str, float],
        recent_events: Optional[list] = None,
        timestamp: Optional[datetime] = None,
    ) -> MarketContext:
        """
        更新市场上下文（唯一入口）
        
        所有外部更新必须通过此方法，
        禁止直接修改状态机或上下文。
        """
        # 更新状态机（权威更新）
        self._state_machine.update(
            event_type=getattr(event, 'event_type', None),
            features=features,
            timestamp=timestamp,
        )
        
        # 生成新的统一上下文
        context = MarketContext(
            core=self._state_machine.current_state,
            features=features.copy(),
            recent_events=recent_events or [],
            generated_at=timestamp or datetime.utcnow(),
        )
        
        # 保存历史（用于回放/验证）
        self._current_context = context
        self._context_history.append(context)
        
        # 限制历史长度
        if len(self._context_history) > self._max_history:
            self._context_history.pop(0)
        
        logger.debug(f"MarketContext updated at {context.generated_at}")
        return context
    
    def get_current_context(self) -> Optional[MarketContext]:
        """
        获取当前市场上下文（只读）
        
        策略只能通过这个方法获取市场状态，
        禁止其他方式。
        """
        return self._current_context
    
    def get_context_history(self, limit: int = 100) -> list[MarketContext]:
        """
        获取上下文历史（用于策略回顾/验证）
        """
        return self._context_history[-limit:]
    
    def clear_history(self):
        """清空历史（用于重置/测试）"""
        self._context_history = []
        self._current_context = None


# ============== 导出接口 ==============

__all__ = [
    "MarketContext",
    "MarketContextAuthority",
]
