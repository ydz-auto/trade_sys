"""
DomainKernel - 唯一的业务真相（三范式共享）

核心设计原则（强制约束）：
1. LIVE/REPLAY/RESEARCH 共享同一个 Kernel
2. 所有业务逻辑在 Kernel，不在 Adapter
3. MarketContext 是唯一真相源（Single Source of Truth）
4. 策略只能消费 MarketContext，不能自己解释市场
5. 禁止策略分叉
6. 禁止绕过 MarketContextBuilder 直接访问状态

数据流架构（按照用户定义）：
    raw data
         ↓
    features_by_tf
         ↓
    MarketContextBuilder
         ↓
    MarketContext
         ↓
    StrategyV2
         ↓
    Signal
         ↓
    Risk / Execution

周期设计（严格执行）：
    4h: 大方向/风险状态（决定风险乘数）
    1h: 环境过滤（决定是否允许做多/做空）
    15m: 主交易周期（生成 candidate signal）
    5m: 触发确认（增强/降低置信度）
    1m: 执行/微结构（入场时机、滑点、流动性）
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

from engines.compute.context import (
    MarketContext,
    MarketContextBuilder,
    STANDARD_TIMEFRAMES,
)
from engines.compute.strategy_v2 import (
    StrategyV2,
    Signal,
    StrategyMeta,
    StrategyRegistry,
)
from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from domain.runtime_policy.authority.clock_authority import (
    ClockAuthority,
    ClockMode,
)
from domain.event.kernel_event import RuntimeBus
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
    enabled_strategy_ids: List[str] = field(default_factory=list)
    
    validation_enabled: bool = True
    journaling_enabled: bool = True


class DomainKernel:
    """
    Domain Kernel - 唯一的业务真相
    
    核心职责（强制约束）：
    1. 管理 MarketContextBuilder（唯一真相源）
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
        
        self._context_builder: MarketContextBuilder = MarketContextBuilder(config.symbol)
        
        self._strategies: Dict[str, StrategyV2] = {}
        
        self._context_history: List[MarketContext] = []
        
        logger.info(f"DomainKernel initialized for: {config.symbol}")
    
    async def initialize(self) -> bool:
        """初始化 Kernel"""
        logger.info("Initializing DomainKernel...")
        self._mode = KernelMode.PROCESSING
        
        self._initialize_strategies()
        
        self._mode = KernelMode.IDLE
        logger.info("DomainKernel initialized successfully")
        return True
    
    def _initialize_strategies(self) -> None:
        """初始化策略（三范式共享同一套策略）"""
        StrategyRegistry.load_strategies()
        
        for strategy_id in self.config.enabled_strategy_ids:
            strategy_instance = StrategyRegistry.create_instance(
                strategy_id,
                self.config.symbol
            )
            if strategy_instance:
                self._strategies[strategy_id] = strategy_instance
                logger.info(f"Strategy initialized: {strategy_id}")
            else:
                logger.warning(f"Strategy not found: {strategy_id}")
    
    async def handle_event(self, event: BaseEvent, features_by_tf: Dict[str, Dict[str, Any]]) -> None:
        """
        处理事件（唯一入口）
        
        强制流程（按照用户定义）：
        1. 获取时间（从 ClockAuthority）
        2. 更新 MarketContext（通过 MarketContextBuilder，唯一入口）
        3. 运行策略（策略只能消费 MarketContext）
        4. 发布信号
        
        禁止策略自己解释市场！
        """
        self._mode = KernelMode.PROCESSING
        
        try:
            current_time_ms = self._clock.now_ms()
            current_time = datetime.fromtimestamp(current_time_ms / 1000)
            
            market_context = self._context_builder.build(
                features_by_tf=features_by_tf,
                timestamp=current_time_ms
            )
            
            self._context_history.append(market_context)
            if len(self._context_history) > 1000:
                self._context_history.pop(0)
            
            await self._run_strategies(market_context, event)
            
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
            self._mode = KernelMode.ERROR
        finally:
            self._mode = KernelMode.IDLE
    
    async def _run_strategies(
        self,
        market_context: MarketContext,
        event: BaseEvent,
    ) -> None:
        """
        运行策略（策略只能消费 MarketContext）
        
        强制约束：
        - 策略只能接收 MarketContext
        - 策略禁止直接访问 raw features
        - 策略只能消费 MarketContext，不能自己解释市场
        """
        for strategy_id, strategy in self._strategies.items():
            try:
                is_valid, errors = strategy.validate_requirements(market_context)
                if not is_valid:
                    logger.warning(f"Strategy {strategy_id} context validation failed: {errors}")
                    continue
                
                signal = strategy.generate_signal(market_context)
                
                if not signal.is_none:
                    await self._bus.publish_signal(signal)
                    logger.info(f"Signal generated from {strategy_id}: {signal}")
                
            except Exception as e:
                logger.error(f"Error running strategy {strategy_id}: {e}", exc_info=True)
    
    def get_current_context(self) -> Optional[MarketContext]:
        """
        获取当前市场上下文（唯一方式）
        
        禁止直接访问 _context_builder 内部
        """
        return self._context_history[-1] if self._context_history else None
    
    def get_context_history(self, limit: int = 100) -> List[MarketContext]:
        """获取上下文历史（用于验证/回放）"""
        return self._context_history[-limit:] if self._context_history else []
    
    @property
    def mode(self) -> KernelMode:
        """当前内核模式"""
        return self._mode


__all__ = [
    "KernelMode",
    "DomainKernelConfig",
    "DomainKernel",
    "STANDARD_TIMEFRAMES",
]
