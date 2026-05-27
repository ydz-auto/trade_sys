"""
Strategy V2 Base - Event-Driven + State Machine 架构

核心原则：
- 策略不再直接读取 raw features，而是消费 Events + MarketContext
- 配置类型化，不再是散参数字典
- 决策语义清晰（基于 Context 的 is_exhausted() 等方法，而非原始值 if 判断）
- 完整的回放一致性保证
- StrategyInfo 定义策略的周期依赖和上下文需求

新定位（按照用户定义）：
- required_features: 原料依赖（用于声明需要哪些特征来生成上下文）
- required_context: 需要的上下文路径（如 "tfs.15m.flow", "derivatives.oi"）
- primary_timeframe: 主交易周期（如 "15m"）
- confirm_timeframes: 确认周期（如 ["5m", "1h"]）
- execution_timeframe: 执行周期（如 "1m"）
"""
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

from domain.config.strategy_config import StrategyConfigV2
from domain.market_state import MarketContext
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
    key_context_paths: List[str] = field(default_factory=list)
    
    # 执行相关
    quantity: Optional[float] = None
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # 元数据
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "v2"


@dataclass(frozen=True)
class StrategyInfo:
    """
    策略元信息 - 定义策略的依赖和周期配置
    
    按照用户定义的新定位：
    - required_features: 原料依赖（哪些特征用于生成上下文）
    - required_context: 需要的上下文路径（策略消费的上下文）
    - primary_timeframe: 主交易周期（生成候选信号）
    - confirm_timeframes: 确认周期（验证信号）
    - execution_timeframe: 执行周期（入场时间）
    """
    strategy_id: str
    strategy_name: str
    
    # 原料依赖（用于声明需要哪些特征来生成上下文）
    required_features: List[str] = field(default_factory=list)
    
    # 需要的上下文路径（策略消费的上下文）
    required_context: List[str] = field(default_factory=list)
    
    # 周期配置
    primary_timeframe: str = "15m"
    confirm_timeframes: List[str] = field(default_factory=lambda: ["5m", "1h"])
    execution_timeframe: str = "1m"
    
    # 策略类型标签
    tags: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        # 验证时间周期
        valid_tfs = {"1m", "5m", "15m", "1h", "4h"}
        if self.primary_timeframe not in valid_tfs:
            raise ValueError(f"Invalid primary_timeframe: {self.primary_timeframe}")
        if self.execution_timeframe not in valid_tfs:
            raise ValueError(f"Invalid execution_timeframe: {self.execution_timeframe}")
        for tf in self.confirm_timeframes:
            if tf not in valid_tfs:
                raise ValueError(f"Invalid confirm_timeframe: {tf}")


class StateAwareStrategy:
    """
    状态感知策略基类 - V2 架构
    
    核心方法：
    - generate_signal(market_context, triggering_event, features)
      - 仅根据当前 MarketContext 和 Event 做决策
      - 不再在策略内部保留 mutable state（避免回放不一致）
      - 新策略禁止直接 features.get(...)，只能读 market_context
    """
    
    def __init__(self, config: StrategyConfigV2):
        self.config = config
        self._enabled = config.is_active
        self.strategy_id = config.strategy_id
        self.strategy_name = config.strategy_name
        
        # 创建策略元信息
        self.strategy_info = self._define_strategy_info()
        
        logger.info(f"初始化策略: {self.strategy_name} [{self.strategy_id}]")
        logger.info(f"  主周期: {self.strategy_info.primary_timeframe}")
        logger.info(f"  确认周期: {self.strategy_info.confirm_timeframes}")
        logger.info(f"  执行周期: {self.strategy_info.execution_timeframe}")
    
    def _define_strategy_info(self) -> StrategyInfo:
        """
        定义策略元信息（子类必须实现）
        
        示例：
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=["oi_delta", "oi_zscore", "funding_rate"],
            required_context=[
                "tfs.15m.flow",
                "tfs.1h.trend_state",
                "derivatives.oi"
            ],
            primary_timeframe="15m",
            confirm_timeframes=["5m", "1h"],
            execution_timeframe="1m",
            tags={"derivatives", "oi_behavior"}
        )
        """
        return StrategyInfo(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            required_features=[],
            required_context=[],
            primary_timeframe="15m",
            confirm_timeframes=["5m", "1h"],
            execution_timeframe="1m",
            tags=set()
        )
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def enable(self):
        self._enabled = True
        logger.debug(f"策略启用: {self.strategy_id}")
    
    def disable(self):
        self._enabled = False
        logger.debug(f"策略禁用: {self.strategy_id}")
    
    def generate_signal(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent] = None,
        features: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalV2]:
        """
        V2 核心信号生成方法 - 基于 MarketContext + Event
        
        Args:
            market_context: 当前市场上下文（唯一真相源）
            triggering_event: 触发此次评估的事件
            features: 当前特征快照（过渡期保留，新策略不应使用）
        
        Returns:
            StrategySignalV2 或 None
        """
        if not self._enabled:
            return None
        
        # 子类实现具体逻辑
        return self._generate_signal_impl(
            market_context=market_context,
            triggering_event=triggering_event,
            features=features or {}
        )
    
    def _generate_signal_impl(
        self,
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """
        子类实现 - 实际的信号生成逻辑
        
        推荐的实现模式（新策略）：
        if (market_context.is_exhausted() 
            and market_context.is_liquid_vacuum()):
            
            return StrategySignalV2(...)
        
        而不是（旧模式，新策略禁止）：
        if features['pressure_zscore'] < -3 and features['liquidity'] < 0.1:
            ...
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def calculate_position_size(
        self,
        market_context: MarketContext,
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
        vol_state = market_context.tf_1h().volatility_state.name
        if vol_state == 'EXPANDED':
            volatility_adjustment = 0.7
        elif vol_state == 'EXTREME':
            volatility_adjustment = 0.5
        
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
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        if triggering_event is None:
            return None
        
        if triggering_event.type not in self.interested_event_types:
            return None
        
        return self._handle_event(
            event=triggering_event,
            market_context=market_context,
            features=features
        )
    
    def _handle_event(
        self,
        event: BaseEvent,
        market_context: MarketContext,
        features: Dict[str, Any],
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
        market_context: MarketContext,
        triggering_event: Optional[BaseEvent],
        features: Dict[str, Any],
    ) -> Optional[StrategySignalV2]:
        """根据当前 Regime 分发处理"""
        regime = market_context.regime.state
        
        if regime == 'trending_up':
            return self._on_trending_up(market_context, triggering_event, features)
        elif regime == 'trending_down':
            return self._on_trending_down(market_context, triggering_event, features)
        elif regime == 'mean_reverting':
            return self._on_mean_reverting(market_context, triggering_event, features)
        elif regime == 'squeeze':
            return self._on_squeeze(market_context, triggering_event, features)
        elif regime == 'crash':
            return self._on_crash(market_context, triggering_event, features)
        elif regime == 'quiet':
            return self._on_quiet(market_context, triggering_event, features)
        
        return None
    
    def _on_trending_up(self, market_context, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_trending_down(self, market_context, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_mean_reverting(self, market_context, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_squeeze(self, market_context, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_crash(self, market_context, event, features) -> Optional[StrategySignalV2]:
        return None
    
    def _on_quiet(self, market_context, event, features) -> Optional[StrategySignalV2]:
        return None


# ============== 导出接口 ==============

__all__ = [
    "SignalDirection",
    "SignalStrength",
    "StrategySignalV2",
    "StrategyInfo",
    "StateAwareStrategy",
    "EventDrivenStrategy",
    "RegimeAwareStrategy",
]
