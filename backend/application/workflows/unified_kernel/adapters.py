"""
Runtime Adapters - 三范式适配器

核心设计原则：
1. 所有 Adapter 共享同一个 Domain Kernel
2. Adapter 只负责连接外部系统，不包含业务逻辑
3. 策略完全不知道是 LIVE/REPLAY/RESEARCH
4. 禁止策略分叉

三个 Adapter：
- LiveRuntimeAdapter: 实盘/模拟盘
- ReplayRuntimeAdapter: 历史回放
- ResearchRuntimeAdapter: 离线研究/回测
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from application.workflows.unified_kernel.runtime_contract import (
    RuntimeAdapter,
    RuntimeContractConfig,
    RuntimeMode,
    RuntimeLifecycle,
)
from application.workflows.unified_kernel.domain_kernel import (
    DomainKernel,
    DomainKernelConfig,
)
from domain.runtime_policy.authority.clock_authority import (
    ClockAuthority,
    ClockMode,
)
from domain.event.kernel_event import RuntimeBus
from infrastructure.logging import get_logger

logger = get_logger("runtime.adapters")


class LiveRuntimeAdapter(RuntimeAdapter):
    """
    LIVE Runtime Adapter - 实盘/模拟盘适配器
    
    特点：
    - 时间来自 ClockAuthority (LIVE mode)
    - 事件流来自实时市场数据
    - 执行连接真实交易所
    """
    
    def __init__(self, config: RuntimeContractConfig):
        super().__init__(config)
        
        self._data_source = None
        self._execution_adapter = None
        self._kernel: Optional[DomainKernel] = None
        self._running = False
    
    async def initialize(self) -> bool:
        """初始化 LIVE Runtime"""
        logger.info("Initializing LiveRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.INITIALIZING)
        
        self._clock_authority = ClockAuthority(mode=ClockMode.LIVE)
        
        self._runtime_bus = RuntimeBus()
        
        kernel_config = DomainKernelConfig(
            symbol=self.config.symbol,
            enabled_strategies=[
                "open_interest_behavior_v2",
                "trade_pressure_exhaustion_v2",
                "funding_extreme_reversal_v2",
                "liquidation_cascade_v2",
                "momentum_ignition_v2",
            ],
        )
        self._kernel = DomainKernel(
            config=kernel_config,
            clock=self._clock_authority,
            bus=self._runtime_bus,
        )
        await self._kernel.initialize()
        
        self._initialize_data_source()
        self._initialize_execution()
        
        self._transition_lifecycle(RuntimeLifecycle.INITIALIZED)
        logger.info("LiveRuntimeAdapter initialized successfully")
        return True
    
    def _initialize_data_source(self) -> None:
        """初始化数据源（连接市场）"""
        logger.info("Initializing LIVE data source...")
    
    def _initialize_execution(self) -> None:
        """初始化执行适配器（连接交易所）"""
        logger.info("Initializing LIVE execution adapter...")
    
    async def run(self) -> None:
        """运行 LIVE 主循环"""
        logger.info("Starting LiveRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.RUNNING)
        self._running = True
        
        try:
            while self._running:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"LiveRuntime error: {e}", exc_info=True)
            self._transition_lifecycle(RuntimeLifecycle.ERROR)
        finally:
            await self.shutdown()
    
    async def pause(self) -> None:
        """暂停 LIVE 运行时"""
        logger.info("Pausing LiveRuntimeAdapter...")
        self._running = False
        self._transition_lifecycle(RuntimeLifecycle.PAUSED)
    
    async def resume(self) -> None:
        """恢复 LIVE 运行时"""
        logger.info("Resuming LiveRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.RUNNING)
        await self.run()
    
    async def shutdown(self) -> None:
        """关闭 LIVE 运行时"""
        logger.info("Shutting down LiveRuntimeAdapter...")
        self._running = False
        self._transition_lifecycle(RuntimeLifecycle.SHUTTING_DOWN)
        
        if self._data_source:
            pass
        if self._execution_adapter:
            pass
        
        self._transition_lifecycle(RuntimeLifecycle.TERMINATED)
        logger.info("LiveRuntimeAdapter shutdown complete")
    
    def publish_event(self, event: BaseEvent) -> None:
        """发布事件"""
        if self._runtime_bus:
            self._runtime_bus.publish_event(event)
    
    def subscribe_events(self, event_type: Optional[EventType], callback: Callable) -> None:
        """订阅事件"""
        if self._runtime_bus:
            self._runtime_bus.subscribe_events(event_type, callback)


class ReplayRuntimeAdapter(RuntimeAdapter):
    """
    REPLAY Runtime Adapter - 历史回放适配器
    
    特点：
    - 时间来自 ClockAuthority (REPLAY mode，手动控制)
    - 事件流来自历史数据
    - 执行是模拟的，不连接真实交易所
    """
    
    def __init__(self, config: RuntimeContractConfig):
        super().__init__(config)
        
        self._historical_data = None
        self._current_index = 0
        self._kernel: Optional[DomainKernel] = None
        self._running = False
    
    async def initialize(self) -> bool:
        """初始化 REPLAY Runtime"""
        logger.info("Initializing ReplayRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.INITIALIZING)
        
        self._clock_authority = ClockAuthority(mode=ClockMode.REPLAY)
        if self.config.start_time_ms:
            self._clock_authority.switch_to_replay_mode(self.config.start_time_ms)
        
        self._runtime_bus = RuntimeBus()
        
        kernel_config = DomainKernelConfig(
            symbol=self.config.symbol,
            enabled_strategies=[
                "open_interest_behavior_v2",
                "trade_pressure_exhaustion_v2",
                "funding_extreme_reversal_v2",
                "liquidation_cascade_v2",
                "momentum_ignition_v2",
            ],
        )
        self._kernel = DomainKernel(
            config=kernel_config,
            clock=self._clock_authority,
            bus=self._runtime_bus,
        )
        await self._kernel.initialize()
        
        await self._load_historical_data()
        
        self._transition_lifecycle(RuntimeLifecycle.INITIALIZED)
        logger.info("ReplayRuntimeAdapter initialized successfully")
        return True
    
    async def _load_historical_data(self) -> None:
        """加载历史数据用于回放"""
        logger.info("Loading historical data...")
        self._historical_data = []
        self._current_index = 0
    
    async def run(self) -> None:
        """运行 REPLAY 主循环"""
        logger.info("Starting ReplayRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.RUNNING)
        self._running = True
        
        try:
            while self._running and self._current_index < len(self._historical_data):
                historical_event = self._historical_data[self._current_index]
                
                timestamp_ms = historical_event.get("timestamp_ms")
                if timestamp_ms:
                    self._clock_authority.advance_to(timestamp_ms)
                
                if self._kernel:
                    event = self._convert_to_base_event(historical_event)
                    features = historical_event.get("features", {})
                    await self._kernel.handle_event(event, features)
                
                self._current_index += 1
                
                await asyncio.sleep(0.001)
                
        except Exception as e:
            logger.error(f"ReplayRuntime error: {e}", exc_info=True)
            self._transition_lifecycle(RuntimeLifecycle.ERROR)
        finally:
            await self.shutdown()
    
    def _convert_to_base_event(self, historical_record: Dict[str, Any]) -> BaseEvent:
        """将历史记录转换为 BaseEvent"""
        event = BaseEvent(
            event_type=historical_record.get("event_type", EventType.MARKET_STRUCTURE_LIQUIDATION),
            timestamp=datetime.utcnow(),
        )
        return event
    
    async def pause(self) -> None:
        """暂停 REPLAY 运行时"""
        logger.info("Pausing ReplayRuntimeAdapter...")
        self._running = False
        self._transition_lifecycle(RuntimeLifecycle.PAUSED)
    
    async def resume(self) -> None:
        """恢复 REPLAY 运行时"""
        logger.info("Resuming ReplayRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.RUNNING)
        await self.run()
    
    async def shutdown(self) -> None:
        """关闭 REPLAY 运行时"""
        logger.info("Shutting down ReplayRuntimeAdapter...")
        self._running = False
        self._transition_lifecycle(RuntimeLifecycle.SHUTTING_DOWN)
        
        self._historical_data = None
        
        self._transition_lifecycle(RuntimeLifecycle.TERMINATED)
        logger.info("ReplayRuntimeAdapter shutdown complete")
    
    def publish_event(self, event: BaseEvent) -> None:
        """发布事件"""
        if self._runtime_bus:
            self._runtime_bus.publish_event(event)
    
    def subscribe_events(self, event_type: Optional[EventType], callback: Callable) -> None:
        """订阅事件"""
        if self._runtime_bus:
            self._runtime_bus.subscribe_events(event_type, callback)


class ResearchRuntimeAdapter(RuntimeAdapter):
    """
    RESEARCH Runtime Adapter - 离线研究/回测适配器
    
    特点：
    - 时钟来自 ClockAuthority (REPLAY mode)
    - 事件流来自批量历史数据
    - 无实时执行，专注于特征/策略研究
    - 可能有向量化优化
    """
    
    def __init__(self, config: RuntimeContractConfig):
        super().__init__(config)
        
        self._batch_data = None
        self._results = []
        self._kernel: Optional[DomainKernel] = None
        self._running = False
    
    async def initialize(self) -> bool:
        """初始化 RESEARCH Runtime"""
        logger.info("Initializing ResearchRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.INITIALIZING)
        
        self._clock_authority = ClockAuthority(mode=ClockMode.REPLAY)
        if self.config.start_time_ms:
            self._clock_authority.switch_to_replay_mode(self.config.start_time_ms)
        
        self._runtime_bus = RuntimeBus()
        
        kernel_config = DomainKernelConfig(
            symbol=self.config.symbol,
            enabled_strategies=[
                "open_interest_behavior_v2",
                "trade_pressure_exhaustion_v2",
                "funding_extreme_reversal_v2",
                "liquidation_cascade_v2",
                "momentum_ignition_v2",
            ],
            validation_enabled=True,
            journaling_enabled=True,
        )
        self._kernel = DomainKernel(
            config=kernel_config,
            clock=self._clock_authority,
            bus=self._runtime_bus,
        )
        await self._kernel.initialize()
        
        await self._load_batch_data()
        
        self._transition_lifecycle(RuntimeLifecycle.INITIALIZED)
        logger.info("ResearchRuntimeAdapter initialized successfully")
        return True
    
    async def _load_batch_data(self) -> None:
        """加载批量数据用于研究/回测"""
        logger.info("Loading batch research data...")
        self._batch_data = []
    
    async def run(self) -> None:
        """运行 RESEARCH 主循环（批量处理）"""
        logger.info("Starting ResearchRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.RUNNING)
        self._running = True
        
        try:
            for i, batch_record in enumerate(self._batch_data):
                if not self._running:
                    break
                
                timestamp_ms = batch_record.get("timestamp_ms")
                if timestamp_ms:
                    self._clock_authority.advance_to(timestamp_ms)
                
                if self._kernel:
                    event = self._convert_to_base_event(batch_record)
                    features = batch_record.get("features", {})
                    await self._kernel.handle_event(event, features)
                    
                    result = self._collect_result(batch_record)
                    self._results.append(result)
        
        except Exception as e:
            logger.error(f"ResearchRuntime error: {e}", exc_info=True)
            self._transition_lifecycle(RuntimeLifecycle.ERROR)
        finally:
            await self.shutdown()
    
    def _convert_to_base_event(self, batch_record: Dict[str, Any]) -> BaseEvent:
        """将批量记录转换为 BaseEvent"""
        return BaseEvent(
            event_type=EventType.MARKET_STRUCTURE_LIQUIDATION,
            timestamp=datetime.utcnow(),
        )
    
    def _collect_result(self, batch_record: Dict[str, Any]) -> Dict[str, Any]:
        """收集研究结果"""
        return {
            "timestamp": batch_record.get("timestamp"),
            "state": self._kernel.current_state.to_dict() if self._kernel and self._kernel.current_state else None,
        }
    
    async def pause(self) -> None:
        """暂停 RESEARCH 运行时"""
        logger.info("Pausing ResearchRuntimeAdapter...")
        self._running = False
        self._transition_lifecycle(RuntimeLifecycle.PAUSED)
    
    async def resume(self) -> None:
        """恢复 RESEARCH 运行时"""
        logger.info("Resuming ResearchRuntimeAdapter...")
        self._transition_lifecycle(RuntimeLifecycle.RUNNING)
        await self.run()
    
    async def shutdown(self) -> None:
        """关闭 RESEARCH 运行时"""
        logger.info("Shutting down ResearchRuntimeAdapter...")
        self._running = False
        self._transition_lifecycle(RuntimeLifecycle.SHUTTING_DOWN)
        
        self._batch_data = None
        
        self._transition_lifecycle(RuntimeLifecycle.TERMINATED)
        logger.info("ResearchRuntimeAdapter shutdown complete")
    
    def publish_event(self, event: BaseEvent) -> None:
        """发布事件"""
        if self._runtime_bus:
            self._runtime_bus.publish_event(event)
    
    def subscribe_events(self, event_type: Optional[EventType], callback: Callable) -> None:
        """订阅事件"""
        if self._runtime_bus:
            self._runtime_bus.subscribe_events(event_type, callback)
    
    def get_results(self) -> List[Dict[str, Any]]:
        """获取研究结果"""
        return self._results.copy()


__all__ = [
    "LiveRuntimeAdapter",
    "ReplayRuntimeAdapter",
    "ResearchRuntimeAdapter",
]
