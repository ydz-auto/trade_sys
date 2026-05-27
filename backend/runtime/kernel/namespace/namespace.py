from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from domain.trading_mode import TradingMode
from runtime.trading_mode_manager import get_trading_mode_manager
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

logger = get_logger("runtime.isolation")

SCOPE_SEPARATOR = "/"
KEY_SEPARATOR = ":"
NAMESPACE_PREFIX = "runtime"


class NamespaceScope(str, Enum):
    LIVE = "live"
    PAPER = "paper"
    REPLAY = "replay"
    OPTIMIZATION = "optimization"
    SHADOW = "shadow"


VALID_SCOPES = frozenset(s.value for s in NamespaceScope)


@dataclass(frozen=True)
class RuntimeNamespace:
    scope: str
    identifier: str

    def __post_init__(self):
        if self.scope not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope: {self.scope}, valid: {sorted(VALID_SCOPES)}"
            )

    @property
    def full_key(self) -> str:
        return f"{self.scope}{SCOPE_SEPARATOR}{self.identifier}"


@dataclass
class SessionScope:
    namespace: RuntimeNamespace
    created_at: datetime
    expires_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.fromtimestamp(now_ms() / 1000) > self.expires_at


class IsolationManager:
    _instance: Optional["IsolationManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._sessions: Dict[str, SessionScope] = {}
        logger.info("IsolationManager initialized")

    def create_session(self, scope: str, identifier: str) -> SessionScope:
        ns = RuntimeNamespace(scope=scope, identifier=identifier)
        session = SessionScope(
            namespace=ns,
            created_at=datetime.fromtimestamp(now_ms() / 1000),
        )
        self._sessions[ns.full_key] = session
        logger.info(f"Created session: {ns.full_key}")
        return session

    def get_session(self, scope: str, identifier: str) -> Optional[SessionScope]:
        key = f"{scope}{SCOPE_SEPARATOR}{identifier}"
        session = self._sessions.get(key)
        if session is not None and session.is_expired:
            self.destroy_session(scope, identifier)
            return None
        return session

    def list_sessions(self, scope: str) -> List[SessionScope]:
        return [
            s
            for s in self._sessions.values()
            if s.namespace.scope == scope and not s.is_expired
        ]

    def destroy_session(self, scope: str, identifier: str) -> bool:
        key = f"{scope}{SCOPE_SEPARATOR}{identifier}"
        if key in self._sessions:
            del self._sessions[key]
            logger.info(f"Destroyed session: {key}")
            return True
        return False

    def key_for(
        self, namespace: RuntimeNamespace, resource_type: str, resource_id: str
    ) -> str:
        return (
            f"{namespace.full_key}{KEY_SEPARATOR}{resource_type}{KEY_SEPARATOR}{resource_id}"
        )

    def validate_isolation(
        self, source_namespace: RuntimeNamespace, target_namespace: RuntimeNamespace
    ) -> bool:
        return source_namespace.full_key == target_namespace.full_key


class NamespacePrefix(str, Enum):
    BACKTEST = f"{NAMESPACE_PREFIX}.backtest"
    PAPER = f"{NAMESPACE_PREFIX}.paper"
    LIVE = f"{NAMESPACE_PREFIX}.live"


@dataclass
class IsolatedChannel:
    namespace: str
    channel_type: str
    full_name: str


class RuntimeIsolation:
    _instance: Optional["RuntimeIsolation"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self._mode_manager = get_trading_mode_manager()

        self._namespaces: Dict[TradingMode, str] = {
            TradingMode.BACKTEST: NamespacePrefix.BACKTEST.value,
            TradingMode.PAPER: NamespacePrefix.PAPER.value,
            TradingMode.LIVE: NamespacePrefix.LIVE.value,
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
        return self._namespaces.get(target_mode, f"{NAMESPACE_PREFIX}.unknown")

    def get_channel_name(
        self, channel_type: str, mode: Optional[TradingMode] = None
    ) -> str:
        namespace = self.get_namespace(mode)
        return f"{namespace}.{channel_type}"

    def get_redis_topic(
        self, topic: str, mode: Optional[TradingMode] = None
    ) -> str:
        namespace = self.get_namespace(mode)
        return f"{namespace}.{topic}"

    def get_event_topic(
        self, event_type: str, mode: Optional[TradingMode] = None
    ) -> str:
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

    def set_state(
        self, key: str, value: Any, mode: Optional[TradingMode] = None
    ) -> None:
        target_mode = mode or self._mode_manager.mode
        self._isolated_state[target_mode][key] = value

    def get_state(
        self, key: str, mode: Optional[TradingMode] = None
    ) -> Any:
        target_mode = mode or self._mode_manager.mode
        return self._isolated_state[target_mode].get(key)

    def get_all_state(
        self, mode: Optional[TradingMode] = None
    ) -> Dict[str, Any]:
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


def get_isolation_manager() -> IsolationManager:
    return IsolationManager()


def ns_topic(topic: str, mode: Optional[TradingMode] = None) -> str:
    isolation = get_runtime_isolation()
    return isolation.get_redis_topic(topic, mode)


def ns_event(event_type: str, mode: Optional[TradingMode] = None) -> str:
    isolation = get_runtime_isolation()
    return isolation.get_event_topic(event_type, mode)
