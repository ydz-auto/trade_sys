"""
Strategy V2 Base - Event-Driven + State Machine 架构

核心原则：
- 策略不再直接读取 raw features，而是消费 Events + MarketState
- 配置类型化，不再是散参数字典
- 决策语义清晰（基于 State 的 is_exhausted() 等方法，而非原始值 if 判断）
- 完整的回放一致性保证
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

from domain.config.strategy_config import StrategyConfigV2
from domain.market_state.state import MarketState
from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from infrastructure.logging import get_logger

logger = get_logger("strategy_v2")


class SignalDirection(str, Enum):
    """信号方向"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class SignalStrength(str, Enum):
    """信号强度"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXTREME = "extreme"


@dataclass(frozen=True)
class StrategySignalV2:
    """
    V2 版策略信号 - 类型安全 + 不可变
    
    核心改进：
    - 不再是字典，而是类型明确的 dataclass
    - 显式标记是基于什么事件/状态
    - 记录用于计算的关键特征值（用于回放）
    """
    strategy_id: str
    strategy_name: str
    symbol: str
    direction: SignalDirection
    strength: SignalStrength
    confidence: float
    
    # 触发条件记录（用于回放和调试）
    triggering_event_type: Optional[EventType] = None
    triggering_market_state: Optional[MarketState] = None
    key_features: Dict[str, Any] = field(default_factory=dict)
    
    # 执行相关
    quantity: Optional[float] = None
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # 元数据
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "v2"


class StateAwareStrategy:
    """
    状态感知策略基类 - V2 架构
    
    核心方法：
    - generate_signal_v2(market_state, triggering_event, current_features)
      - 仅根据当前 MarketState 和 Event 做决策
      - 不再在策略内部保留 mutable state（避免回放不一致）
    """
    
    def __init__(self, config: StrategyConfigV2):
        self.config = config
        self._enabled = config.is_active
        self.strategy_id = config.strategy_id
        self.strategy_name = config.strategy_name
        logger.info(f"初始化策略: {self.strategy_name} [{self.strategy_id}]")
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def enable(self):
        self._enabled = True
        logger.debug(f"策略启用: {self.strategy_id}")
    
    def disable(self):
        self._enabled = False
        logger.debug(f"策略禁用: {self.strategy_id}")
    
    def generate_signal_v2(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent] = None,
        current_features: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalV2]:
        """
        V2 核心信号生成方法 - 基于 State + Event
        
        Args:
            market_state: 当前市场状态
            triggering_event: 触发此次评估的事件（可能为 None，比如周期评估）
            current_features: 当前特征快照（辅助用）
        
        Returns:
            StrategySignalV2 或 None
        """
        if not self._enabled:
            return None
        
        # 子类实现具体逻辑
        return self._generate_signal_impl(
            market_state=market_state,
            triggering_event=triggering_event,
            current_features=current_features or {}
        )
    
    def _generate_signal_impl(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent],
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """
        子类实现 - 实际的信号生成逻辑
        
        推荐的实现模式：
        if (market_state.is_exhausted() 
            and market_state.is_liquid_vacuum() 
            and triggering_event.type == EventType.TRADE_PRESSURE_FLUSH):
            
            return StrategySignalV2(...)
        
        而不是：
        if features['pressure_zscore'] < -3 and features['liquidity'] < 0.1:
            ...
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def calculate_position_size(
        self,
        market_state: MarketState,
        signal_confidence: float,
        current_price: float,
        account_balance: float,
    ) -> float:
        """
        计算仓位大小 - 统一在策略层管理
        
        基于：
        - 策略配置的风险参数
        - 当前市场状态的 volatility
        - 信号信心度
        """
        base_pct = self.config.risk_params.position_size_pct
        confidence_multiplier = 0.5 + 0.5 * signal_confidence
        
        # 根据 volatility 调整
        volatility_adjustment = 1.0
        if market_state.volatility in ['elevated', 'extreme']:
            volatility_adjustment = 0.7 if market_state.volatility == 'elevated' else 0.5
        
        position_pct = base_pct * confidence_multiplier * volatility_adjustment
        
        # 转换为实际数量（根据价格和余额）
        position_value = account_balance * position_pct
        position_qty = position_value / current_price if current_price > 0 else 0.0
        
        return max(0.0, position_qty)


class EventDrivenStrategy(StateAwareStrategy):
    """
    事件驱动策略 - 专注于特定类型的 Event
    
    子类只需要：
    1. 定义感兴趣的 event_types
    2. 在 _handle_event 中处理
    """
    
    def __init__(self, config: StrategyConfigV2, interested_event_types: Optional[list[EventType]] = None):
        super().__init__(config)
        self.interested_event_types = interested_event_types or []
        logger.debug(f"事件驱动策略关注事件: {[et.value for et in self.interested_event_types]}")
    
    def _generate_signal_impl(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent],
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        if triggering_event is None:
            return None
        
        if triggering_event.type not in self.interested_event_types:
            return None
        
        return self._handle_event(
            event=triggering_event,
            market_state=market_state,
            current_features=current_features
        )
    
    def _handle_event(
        self,
        event: BaseEvent,
        market_state: MarketState,
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """子类实现 - 处理特定事件"""
        raise NotImplementedError


class RegimeAwareStrategy(StateAwareStrategy):
    """
    状态机感知策略 - 根据市场 Regime 切换行为
    
    例如：
    - 在 TRENDING 下做趋势追踪
    - 在 MEAN_REVERTING 下做反转
    - 在 SQUEEZE/CRASH 下做特殊处理
    """
    
    def __init__(self, config: StrategyConfigV2):
        super().__init__(config)
    
    def _generate_signal_impl(
        self,
        market_state: MarketState,
        triggering_event: Optional[BaseEvent],
        current_features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """根据当前 Regime 分发处理"""
        regime = market_state.regime
        
        if regime == 'trending_up':
            return self._on_trending_up(market_state, triggering_event, current_features)
        elif regime == 'trending_down':
            return self._on_trending_down(market_state, triggering_event, current_features)
        elif regime == 'mean_reverting':
            return self._on_mean_reverting(market_state, triggering_event, current_features)
        elif regime == 'squeeze':
            return self._on_squeeze(market_state, triggering_event, current_features)
        elif regime == 'crash':
            return self._on_crash(market_state, triggering_event, current_features)
        elif regime == 'quiet':
            return self._on_quiet(market_state, triggering_event, current_features)
        
        return None
    
    def _on_trending_up(self, market_state, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_trending_down(self, market_state, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_mean_reverting(self, market_state, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_squeeze(self, market_state, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_crash(self, market_state, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_quiet(self, market_state, event, features) -> Optional[StrategySignalV2]:
        return None
