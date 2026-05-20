"""
Runtime Isolation - Runtime 隔离

核心职责:
1. 为每种模式提供独立的 namespace
2. 隔离 Redis topic、Event bus、Signal channel、Execution queue
3. 防止 Replay 污染实盘

Namespace 结构:
    runtime.backtest.*
    runtime.paper.*
    runtime.live.*

Event 示例:
    runtime.paper.signal
    runtime.live.execution.order
    runtime.backtest.replay.tick
"""
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass
import asyncio

from domain.trading_mode import TradingMode, get_trading_mode_manager
from infrastructure.logging import get_logger

logger = get_logger("runtime.isolation")


class RuntimeNamespace(str, Enum):
    BACKTEST = "runtime.backtest"
    PAPER = "runtime.paper"
    LIVE = "runtime.live"


@dataclass
class IsolatedChannel:
    namespace: str
    channel_type: str
    full_name: str


class RuntimeIsolation:
    _instance: Optional['RuntimeIsolation'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._mode_manager = get_trading_mode_manager()
        
        self._namespaces: Dict[TradingMode, str] = {
            TradingMode.BACKTEST: RuntimeNamespace.BACKTEST.value,
            TradingMode.PAPER: RuntimeNamespace.PAPER.value,
            TradingMode.LIVE: RuntimeNamespace.LIVE.value,
        }
        
        self._channels: Dict[str, asyncio.Queue] = {}
        self._event_handlers: Dict[str, list[Callable]] = {}
        
        self._isolated_state: Dict[TradingMode, Dict[str, Any]] = {
            TradingMode.BACKTEST: {},
            TradingMode.PAPER: {},
            TradingMode.LIVE: {},
        }
        
        self._stats = {
            "events_published": 0,
            "events_consumed": 0,
            "cross_namespace_blocked": 0,
        }
        
        logger.info("RuntimeIsolation initialized")

    def get_namespace(self, mode: Optional[TradingMode] = None) -> str:
        target_mode = mode or self._mode_manager.mode
        return self._namespaces.get(target_mode, "runtime.unknown")

    def get_channel_name(self, channel_type: str, mode: Optional[TradingMode] = None) -> str:
        namespace = self.get_namespace(mode)
        return f"{namespace}.{channel_type}"

    def get_redis_topic(self, topic: str, mode: Optional[TradingMode] = None) -> str:
        namespace = self.get_namespace(mode)
        return f"{namespace}.{topic}"

    def get_event_topic(self, event_type: str, mode: Optional[TradingMode] = None) -> str:
        namespace = self.get_namespace(mode)
        return f"{namespace}.event.{event_type}"

    def create_isolated_channel(
        self,
        channel_type: str,
        mode: Optional[TradingMode] = None,
        maxsize: int = 1000,
    ) -> IsolatedChannel:
        full_name = self.get_channel_name(channel_type, mode)
        
        if full_name not in self._channels:
            self._channels[full_name] = asyncio.Queue(maxsize=maxsize)
            logger.info(f"Created isolated channel: {full_name}")
        
        return IsolatedChannel(
            namespace=self.get_namespace(mode),
            channel_type=channel_type,
            full_name=full_name,
        )

    async def publish(
        self,
        channel_type: str,
        data: Any,
        mode: Optional[TradingMode] = None,
    ) -> bool:
        full_name = self.get_channel_name(channel_type, mode)
        
        if full_name not in self._channels:
            self.create_isolated_channel(channel_type, mode)
        
        try:
            self._channels[full_name].put_nowait(data)
            self._stats["events_published"] += 1
            return True
        except asyncio.QueueFull:
            logger.warning(f"Channel full: {full_name}")
            return False

    async def subscribe(
        self,
        channel_type: str,
        mode: Optional[TradingMode] = None,
    ) -> Any:
        full_name = self.get_channel_name(channel_type, mode)
        
        if full_name not in self._channels:
            return None
        
        try:
            data = await self._channels[full_name].get()
            self._stats["events_consumed"] += 1
            return data
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return None

    def register_event_handler(
        self,
        event_type: str,
        handler: Callable,
        mode: Optional[TradingMode] = None,
    ) -> str:
        topic = self.get_event_topic(event_type, mode)
        
        if topic not in self._event_handlers:
            self._event_handlers[topic] = []
        
        self._event_handlers[topic].append(handler)
        logger.info(f"Registered event handler for: {topic}")
        
        return topic

    async def emit_event(
        self,
        event_type: str,
        data: Any,
        mode: Optional[TradingMode] = None,
    ) -> None:
        topic = self.get_event_topic(event_type, mode)
        
        handlers = self._event_handlers.get(topic, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def set_state(self, key: str, value: Any, mode: Optional[TradingMode] = None) -> None:
        target_mode = mode or self._mode_manager.mode
        self._isolated_state[target_mode][key] = value

    def get_state(self, key: str, mode: Optional[TradingMode] = None) -> Any:
        target_mode = mode or self._mode_manager.mode
        return self._isolated_state[target_mode].get(key)

    def get_all_state(self, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        target_mode = mode or self._mode_manager.mode
        return self._isolated_state[target_mode].copy()

    def clear_state(self, mode: Optional[TradingMode] = None) -> None:
        target_mode = mode or self._mode_manager.mode
        self._isolated_state[target_mode] = {}
        logger.info(f"Cleared state for mode: {target_mode.value}")

    def validate_cross_namespace_access(
        self,
        from_mode: TradingMode,
        to_mode: TradingMode,
    ) -> bool:
        if from_mode == to_mode:
            return True
        
        self._stats["cross_namespace_blocked"] += 1
        logger.warning(
            f"Cross-namespace access blocked: {from_mode.value} -> {to_mode.value}"
        )
        return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_namespace": self.get_namespace(),
            "current_mode": self._mode_manager.mode.value,
            "channels": list(self._channels.keys()),
            "event_topics": list(self._event_handlers.keys()),
            "stats": self._stats.copy(),
        }


def get_runtime_isolation() -> RuntimeIsolation:
    return RuntimeIsolation()


def ns_topic(topic: str, mode: Optional[TradingMode] = None) -> str:
    isolation = get_runtime_isolation()
    return isolation.get_redis_topic(topic, mode)


def ns_event(event_type: str, mode: Optional[TradingMode] = None) -> str:
    isolation = get_runtime_isolation()
    return isolation.get_event_topic(event_type, mode)
