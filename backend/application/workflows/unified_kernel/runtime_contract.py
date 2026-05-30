"""
RuntimeContract - 强约束的运行时契约

所有三范式（LIVE/REPLAY/RESEARCH）必须实现此契约

核心设计原则：
1. 唯一的业务真相在 Domain Kernel
2. 三套范式 = 三个 Adapter，不是三套系统
3. 策略完全不知道范式
4. 禁止策略分叉
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)
from datetime import datetime

from domain.event.base_event import BaseEvent
from domain.event.event_type import EventType
from domain.runtime_policy.authority.clock_authority import (
    ClockAuthority,
    ClockMode,
)
from domain.event.kernel_event import RuntimeBus
from infrastructure.logging import get_logger

logger = get_logger("runtime.contract")


class RuntimeMode(Enum):
    """运行时模式（三范式）"""
    LIVE = auto()
    REPLAY = auto()
    RESEARCH = auto()


class RuntimeLifecycle(Enum):
    """运行时生命周期"""
    CREATED = auto()
    INITIALIZING = auto()
    INITIALIZED = auto()
    RUNNING = auto()
    PAUSED = auto()
    SHUTTING_DOWN = auto()
    TERMINATED = auto()
    ERROR = auto()


@runtime_checkable
class ExecutionAdapterProtocol(Protocol):
    """执行适配器协议"""
    def execute_order(self, order: Any) -> Any: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def get_positions(self) -> Dict[str, Any]: ...


@dataclass
class RuntimeContractConfig:
    """运行时契约配置"""
    mode: RuntimeMode
    symbol: str
    config: Dict[str, Any] = field(default_factory=dict)
    
    clock_mode: ClockMode = ClockMode.LIVE
    start_time_ms: Optional[int] = None
    end_time_ms: Optional[int] = None
    
    execution_enabled: bool = True
    simulation_enabled: bool = False
    
    def __post_init__(self):
        if self.mode == RuntimeMode.LIVE:
            self.clock_mode = ClockMode.LIVE
        elif self.mode == RuntimeMode.REPLAY:
            self.clock_mode = ClockMode.REPLAY
        elif self.mode == RuntimeMode.RESEARCH:
            self.clock_mode = ClockMode.REPLAY


class RuntimeAdapter(ABC):
    """
    运行时适配器基类
    
    核心约束：
    1. 所有 Adapter 必须实现此接口
    2. 所有 Adapter 共享同一个 Domain Kernel
    3. Adapter 只负责连接外部系统，不包含业务逻辑
    """
    
    def __init__(self, config: RuntimeContractConfig):
        self.config = config
        self._lifecycle = RuntimeLifecycle.CREATED
        self._clock_authority: Optional[ClockAuthority] = None
        self._runtime_bus: Optional[RuntimeBus] = None
        self._execution_adapter: Optional[ExecutionAdapterProtocol] = None
        
        logger.info(f"RuntimeAdapter initialized: {self.__class__.__name__}, mode: {config.mode}")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化运行时"""
        raise NotImplementedError()
    
    @abstractmethod
    async def run(self) -> None:
        """运行主循环"""
        raise NotImplementedError()
    
    @abstractmethod
    async def pause(self) -> None:
        """暂停运行"""
        raise NotImplementedError()
    
    @abstractmethod
    async def resume(self) -> None:
        """恢复运行"""
        raise NotImplementedError()
    
    @abstractmethod
    async def shutdown(self) -> None:
        """关闭运行时"""
        raise NotImplementedError()
    
    @abstractmethod
    def publish_event(self, event: BaseEvent) -> None:
        """发布事件"""
        raise NotImplementedError()
    
    @abstractmethod
    def subscribe_events(self, event_type: Optional[EventType], callback: Callable) -> None:
        """订阅事件"""
        raise NotImplementedError()
    
    @property
    def mode(self) -> RuntimeMode:
        """运行时模式"""
        return self.config.mode
    
    @property
    def lifecycle(self) -> RuntimeLifecycle:
        """生命周期"""
        return self._lifecycle
    
    @property
    def clock(self) -> ClockAuthority:
        """时钟权威"""
        if self._clock_authority is None:
            raise RuntimeError("ClockAuthority not initialized")
        return self._clock_authority
    
    @property
    def bus(self) -> RuntimeBus:
        """运行时总线"""
        if self._runtime_bus is None:
            raise RuntimeError("RuntimeBus not initialized")
        return self._runtime_bus
    
    def _transition_lifecycle(self, target: RuntimeLifecycle) -> None:
        """生命周期状态转换"""
        logger.debug(f"Lifecycle transition: {self._lifecycle} → {target}")
        self._lifecycle = target
    
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._lifecycle in (
            RuntimeLifecycle.INITIALIZED,
            RuntimeLifecycle.RUNNING,
            RuntimeLifecycle.PAUSED,
        )
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._lifecycle == RuntimeLifecycle.RUNNING
    
    def is_paused(self) -> bool:
        """是否已暂停"""
        return self._lifecycle == RuntimeLifecycle.PAUSED
    
    def is_live_mode(self) -> bool:
        """是否是 LIVE 模式"""
        return self.mode == RuntimeMode.LIVE
    
    def is_replay_mode(self) -> bool:
        """是否是 REPLAY 模式"""
        return self.mode == RuntimeMode.REPLAY
    
    def is_research_mode(self) -> bool:
        """是否是 RESEARCH 模式"""
        return self.mode == RuntimeMode.RESEARCH


def create_runtime_adapter(
    mode: RuntimeMode,
    symbol: str,
    config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> RuntimeAdapter:
    """
    工厂函数：根据模式创建对应的 RuntimeAdapter
    
    Args:
        mode: 运行时模式
        symbol: 交易对
        config: 配置
        **kwargs: 额外参数
    
    Returns:
        RuntimeAdapter 实例
    """
    contract_config = RuntimeContractConfig(
        mode=mode,
        symbol=symbol,
        config=config or {},
        **kwargs,
    )
    
    if mode == RuntimeMode.LIVE:
        from application.workflows.unified_kernel.adapters import LiveRuntimeAdapter
        return LiveRuntimeAdapter(contract_config)
    
    elif mode == RuntimeMode.REPLAY:
        from application.workflows.unified_kernel.adapters import ReplayRuntimeAdapter
        return ReplayRuntimeAdapter(contract_config)
    
    elif mode == RuntimeMode.RESEARCH:
        from application.workflows.unified_kernel.adapters import ResearchRuntimeAdapter
        return ResearchRuntimeAdapter(contract_config)
    
    else:
        raise ValueError(f"Unknown RuntimeMode: {mode}")


__all__ = [
    "RuntimeMode",
    "RuntimeLifecycle",
    "RuntimeContractConfig",
    "ExecutionAdapterProtocol",
    "RuntimeAdapter",
    "create_runtime_adapter",
]
