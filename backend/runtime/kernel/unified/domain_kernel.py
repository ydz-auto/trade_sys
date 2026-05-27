"""
DomainKernel - 唯一的业务真相（三范式共享）

核心设计原则：
1. LIVE/REPLAY/RESEARCH 共享同一个 Kernel
2. 所有业务逻辑在 Kernel，不在 Adapter
3. 策略完全不知道是 LIVE/REPLAY/RESEARCH
4. 禁止策略分叉
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from domain.market_state import MarketState, MarketStateMachine
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
    
    # 状态机配置
    state_machine_enabled: bool = True
    
    # 验证配置
    validation_enabled: bool = True
    journaling_enabled: bool = True


class DomainKernel:
    """
    Domain Kernel - 唯一的业务真相
    
    核心职责：
    1. 管理 Market State Machine
    2. 管理策略实例（三范式共享）
    3. 处理事件 -> 状态转换 -> 信号生成
    4. 完全不区分 LIVE/REPLAY/RESEARCH
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
        
        # 核心组件
        self._state_machine: Optional[MarketStateMachine] = None
        self._strategies: Dict[str, StateAwareStrategy] = {}
        
        # 事件处理
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        
        logger.info(f"DomainKernel initialized for: {config.symbol}")
    
    async def initialize(self) -> bool:
        """初始化 Kernel"""
        logger.info("Initializing DomainKernel...")
        self._mode = KernelMode.PROCESSING
        
        # 初始化状态机
        if self.config.state_machine_enabled:
            self._state_machine = MarketStateMachine(symbol=self.config.symbol)
            logger.info("MarketStateMachine initialized")
        
        # 初始化策略（三范式共享）
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
        
        所有事件必须经过这里，禁止绕过
        
        流程：
        1. 更新 Market State Machine（使用 ClockAuthority 获取时间）
        2. 运行策略生成信号
        3. 发布结果事件
        
        策略完全不知道是 LIVE/REPLAY/RESEARCH
        """
        self._mode = KernelMode.PROCESSING
        
        try:
            # 获取当前时间（通过 ClockAuthority，确保三范式一致性）
            current_time_ms = self._clock.now_ms()
            current_time = datetime.fromtimestamp(current_time_ms / 1000)
            
            # Step 1: 更新状态机（如果启用）
            if self._state_machine:
                self._state_machine.update(
                    event_type=event.event_type,
                    features=features,
                    timestamp=current_time,
                )
            
            # Step 2: 运行策略（策略完全不知道是 LIVE/REPLAY/RESEARCH）
            await self._run_strategies(event, features)
            
            # Step 3: 调用事件处理器
            await self._dispatch_event(event, features)
            
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
            self._mode = KernelMode.ERROR
        finally:
            self._mode = KernelMode.IDLE
    
    async def _run_strategies(
        self,
        event: BaseEvent,
        features: Dict[str, Any],
    ) -> None:
        """运行策略（策略完全不知道范式）"""
        for strategy_id, strategy in self._strategies.items():
            if not strategy.is_enabled:
                continue
            
            # 策略只看到：Event + State + Features
            # 策略完全不知道是 LIVE/REPLAY/RESEARCH
            try:
                state = self._state_machine.current_state if self._state_machine else None
                signal = strategy.generate_signal_v2(
                    market_state=state,
                    triggering_event=event,
                    current_features=features,
                )
                
                if signal:
                    logger.debug(f"Strategy {strategy_id} generated signal: {signal.direction}")
                    # 这里可以发布信号事件
                
            except Exception as e:
                logger.error(f"Strategy {strategy_id} error: {e}", exc_info=True)
    
    async def _dispatch_event(
        self,
        event: BaseEvent,
        features: Dict[str, Any],
    ) -> None:
        """分发事件到处理器"""
        event_type = getattr(event, "event_type", None)
        if not event_type:
            return
        
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    await handler(event, features)
                except Exception as e:
                    logger.error(f"Handler error: {e}", exc_info=True)
    
    async def _handle_market_structure_event(
        self,
        event: BaseEvent,
        features: Dict[str, Any],
    ) -> None:
        """处理市场结构事件"""
        logger.debug(f"Market structure event: {getattr(event, 'event_type', 'unknown')}")
    
    # ==== 状态查询 ====
    @property
    def current_state(self) -> Optional[MarketState]:
        """当前市场状态"""
        return self._state_machine.current_state if self._state_machine else None
    
    @property
    def mode(self) -> KernelMode:
        """内核模式"""
        return self._mode
    
    @property
    def strategies(self) -> Dict[str, StateAwareStrategy]:
        """策略字典"""
        return self._strategies.copy()
    
    def get_strategy(self, strategy_id: str) -> Optional[StateAwareStrategy]:
        """获取策略"""
        return self._strategies.get(strategy_id)


__all__ = [
    "DomainKernel",
    "DomainKernelConfig",
    "KernelMode",
]
