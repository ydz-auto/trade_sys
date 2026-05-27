"""
DomainKernel - 唯一的业务真相（三范式共享）

核心设计原则（强制约束）：
1. LIVE/REPLAY/RESEARCH 共享同一个 Kernel
2. 所有业务逻辑在 Kernel，不在 Adapter
3. MarketContext 是唯一真相源（Single Source of Truth）
4. 策略只能消费 MarketContext，不能自己解释市场
5. 禁止策略分叉
6. 禁止绕过 MarketContextAuthority 直接访问状态

这解决了之前的问题：
- ❌ 分散式隐式上下文 → ✅ 集中式显式上下文
- ❌ 双 context 体系 → ✅ 单一 context 权威层
- ❌ 策略自己解释市场 → ✅ 系统统一解释，策略只能消费
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

from domain.market_state import (
    MarketState,
    MarketStateMachine,
    MarketContext,
    MarketContextAuthority,
)
from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from engines.compute.strategy.v2_base import StateAwareStrategy
from engines.compute.strategy.v2_core_strategies import create_v2_configs
from runtime.kernel.authority.clock_authority import (
    ClockAuthority,
    ClockMode,
)
from runtime.kernel.event.runtime_bus import RuntimeBus
from runtime.kernel.unified.runtime_contract import (
    RuntimeContractConfig,
    RuntimeMode,
)
from infrastructure.logging import get_logger

logger = get_logger("domain.kernel")


class KernelMode(Enum):
    """内核模式"""
    IDLE = auto()
    PROCESSING = auto()
    ERROR = auto()


@dataclass
class DomainKernelConfig:
    """Domain Kernel 配置"""
    symbol: str
    enabled_strategies: List[str] = field(default_factory=list)
    
    # 状态机配置（强制启用，不再可选）
    state_machine_enabled: bool = True  # 现在强制启用，不能关闭
    
    # 验证配置
    validation_enabled: bool = True
    journaling_enabled: bool = True


class DomainKernel:
    """
    Domain Kernel - 唯一的业务真相
    
    核心职责（强制约束）：
    1. 管理 MarketContextAuthority（唯一真相源）
    2. 管理策略实例（三范式共享）
    3. 处理事件 -> 更新 MarketContext -> 信号生成
    4. 策略只能消费 MarketContext，不能自己解释市场
    5. 完全不区分 LIVE/REPLAY/RESEARCH
    """
    
    def __init__(
        self,
        config: DomainKernelConfig,
        clock: ClockAuthority,
        bus: RuntimeBus,
    ):
        self.config = config
        self._clock = clock
        self._bus = bus
        self._mode = KernelMode.IDLE
        
        # ============== 核心组件 ==============
        # MarketStateMachine（被 MarketContextAuthority 包装）
        self._state_machine: MarketStateMachine = MarketStateMachine(symbol=config.symbol)
        
        # MarketContextAuthority（唯一真相源，强制依赖）
        self._context_authority: MarketContextAuthority = MarketContextAuthority(self._state_machine)
        
        # 策略实例
        self._strategies: Dict[str, StateAwareStrategy] = {}
        
        # 事件处理
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        
        logger.info(f"DomainKernel initialized for: {config.symbol}")
    
    async def initialize(self) -> bool:
        """初始化 Kernel"""
        logger.info("Initializing DomainKernel...")
        self._mode = KernelMode.PROCESSING
        
        # 注意：MarketStateMachine 和 MarketContextAuthority 已经在 __init__ 中初始化
        logger.info("MarketStateMachine + MarketContextAuthority initialized (强制依赖)")
        
        # 初始化策略（三范式共享同一套策略）
        await self._initialize_strategies()
        
        # 注册事件处理器
        self._register_event_handlers()
        
        self._mode = KernelMode.IDLE
        logger.info("DomainKernel initialized successfully")
        return True
    
    async def _initialize_strategies(self) -> None:
        """初始化策略（三范式共享同一套策略）"""
        strategy_configs = create_v2_configs()
        
        # 策略导入延迟到此处，避免循环依赖
        from engines.compute.strategy.v2_core_strategies import (
            OpenInterestBehaviorV2,
            TradePressureExhaustionV2,
            FundingExtremeReversalV2,
            LiquidationCascadeV2,
            MomentumIgnitionV2,
        )
        
        strategy_classes = {
            "open_interest_behavior_v2": OpenInterestBehaviorV2,
            "trade_pressure_exhaustion_v2": TradePressureExhaustionV2,
            "funding_extreme_reversal_v2": FundingExtremeReversalV2,
            "liquidation_cascade_v2": LiquidationCascadeV2,
            "momentum_ignition_v2": MomentumIgnitionV2,
        }
        
        # 初始化配置的策略
        for strategy_id in self.config.enabled_strategies:
            if strategy_id in strategy_classes and strategy_id in strategy_configs:
                config = strategy_configs[strategy_id]
                strategy_class = strategy_classes[strategy_id]
                self._strategies[strategy_id] = strategy_class(config)
                logger.info(f"Strategy initialized: {strategy_id}")
    
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        # 注册 Market Structure 事件
        structure_events = [
            EventType.TRADE_PRESSURE_FLUSH,
            EventType.TRADE_PRESSURE_EXHAUSTION,
            EventType.TRADE_PRESSURE_SQUEEZE,
            EventType.MARKET_STRUCTURE_LIQUIDATION,
            EventType.LIQUIDITY_VACUUM,
        ]
        
        for event_type in structure_events:
            self._event_handlers[event_type] = [self._handle_market_structure_event]
    
    async def handle_event(self, event: BaseEvent, features: Dict[str, Any]) -> None:
        """
        处理事件（唯一入口）
        
        强制流程：
        1. 获取时间（从 ClockAuthority）
        2. 更新 MarketContext（通过 MarketContextAuthority，唯一入口）
        3. 运行策略（策略只能消费 MarketContext）
        4. 发布事件
        
        禁止策略自己解释市场！
        """
        self._mode = KernelMode.PROCESSING
        
        try:
            # Step 1: 获取当前时间（从 ClockAuthority，三范式对齐）
            current_time_ms = self._clock.now_ms()
            current_time = datetime.fromtimestamp(current_time_ms / 1000)
            
            # Step 2: 更新 MarketContext（通过 ContextAuthority，唯一真相源）
            # ❌ 禁止绕过这个！
            market_context = self._context_authority.update(
                event=event,
                features=features,
                recent_events=[],  # 可以传入最近事件列表
                timestamp=current_time,
            )
            
            # Step 3: 运行策略（策略只能消费 MarketContext）
            await self._run_strategies(market_context, event, features)
            
            # Step 4: 调用事件处理器
            await self._dispatch_event(event, features)
            
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
            self._mode = KernelMode.ERROR
        finally:
            self._mode = KernelMode.IDLE
    
    async def _run_strategies(
        self,
        market_context: MarketContext,
        event: BaseEvent,
        features: Dict[str, Any],
    ) -> None:
        """
        运行策略（策略只能消费 MarketContext）
        
        强制约束：
        - 策略输入只能是 MarketContext + Event
        - ❌ 禁止策略直接访问 features（除非作为辅助）
        - ❌ 禁止策略自己解释市场
        """
        for strategy_id, strategy in self._strategies.items():
            try:
                # 策略只能消费 MarketContext，不能自己解释市场
                signal = strategy.generate_signal(
                    market_state=market_context.core,  # 从 context 来
                    event=event,
                    features=features,  # 这个是可选辅助，但主要应依赖 market_state
                )
                
                if signal:
                    # 发布信号
                    await self._bus.publish_signal(signal)
                    logger.info(f"Signal generated from {strategy_id}: {signal}")
            
            except Exception as e:
                logger.error(f"Error running strategy {strategy_id}: {e}", exc_info=True)
    
    async def _dispatch_event(self, event: BaseEvent, features: Dict[str, Any]) -> None:
        """分发事件到注册的处理器"""
        if event.event_type in self._event_handlers:
            for handler in self._event_handlers[event.event_type]:
                try:
                    await handler(event, features)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}", exc_info=True)
    
    async def _handle_market_structure_event(self, event: BaseEvent, features: Dict[str, Any]) -> None:
        """处理市场结构事件"""
        logger.debug(f"Handling market structure event: {event.event_type}")
    
    # ============== 公共接口（只读访问）==============
    
    def get_current_context(self) -> Optional[MarketContext]:
        """
        获取当前市场上下文（唯一方式）
        
        ❌ 禁止直接访问 _state_machine 或 _context_authority
        """
        return self._context_authority.get_current_context()
    
    def get_context_history(self, limit: int = 100) -> List[MarketContext]:
        """获取上下文历史（用于验证/回放）"""
        return self._context_authority.get_context_history(limit)
    
    @property
    def mode(self) -> KernelMode:
        """当前内核模式"""
        return self._mode


# ============== 导出接口 ==============

__all__ = [
    "KernelMode",
    "DomainKernelConfig",
    "DomainKernel",
]
