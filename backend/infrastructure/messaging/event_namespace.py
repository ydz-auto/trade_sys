"""
Event Namespace - 事件命名空间

核心职责:
1. 统一所有事件 topic 命名
2. 按 runtime 模式隔离
3. 防止 topic 混乱

命名规范:
    runtime.{mode}.{domain}.{event}

示例:
    runtime.live.market.trade
    runtime.paper.signal.triggered
    runtime.backtest.execution.order

架构:
    Infrastructure 层无状态原语。
    mode_provider 通过构造函数注入，避免 INFRA → RUNTIME 依赖。
"""
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

from domain.trading_mode import TradingMode
from infrastructure.logging import get_logger

logger = get_logger("infrastructure.event_namespace")


class EventDomain(str, Enum):
    MARKET = "market"
    FEATURE = "feature"
    BEHAVIOUR = "behaviour"
    SIGNAL = "signal"
    EXECUTION = "execution"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    AI = "ai"
    SYSTEM = "system"


class EventType(str, Enum):
    TRADE = "trade"
    TICK = "tick"
    CANDLE = "candle"
    ORDERBOOK = "orderbook"
    LIQUIDATION = "liquidation"
    FUNDING = "funding"

    FEATURE_UPDATE = "feature_update"
    BEHAVIOUR_DETECTED = "behaviour_detected"

    SIGNAL_TRIGGERED = "signal_triggered"
    SIGNAL_EXPIRED = "signal_expired"

    ORDER_CREATED = "order_created"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"

    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"

    RISK_WARNING = "risk_warning"
    RISK_CRITICAL = "risk_critical"
    CIRCUIT_BREAKER = "circuit_breaker"

    NARRATIVE_UPDATE = "narrative_update"
    SENTIMENT_UPDATE = "sentiment_update"

    MODE_CHANGED = "mode_changed"
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_STOPPED = "runtime_stopped"


@dataclass
class EventTopic:
    full: str
    namespace: str
    domain: str
    event: str
    mode: str


class EventNamespace:
    _instance: Optional['EventNamespace'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, mode_provider: Optional[Callable[[], TradingMode]] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        self._mode_provider = mode_provider

        self._prefix = "runtime"

        self._topic_registry: Dict[str, EventTopic] = {}

        self._stats = {
            "topics_created": 0,
        }

        logger.info("EventNamespace initialized")

    def _get_current_mode(self, mode: Optional[TradingMode] = None) -> TradingMode:
        if mode is not None:
            return mode
        if self._mode_provider is not None:
            return self._mode_provider()
        raise ValueError(
            "mode is required when no mode_provider is configured. "
            "Pass mode explicitly or configure mode_provider at construction."
        )

    def _get_mode_prefix(self, mode: Optional[TradingMode] = None) -> str:
        target_mode = self._get_current_mode(mode)
        return f"{self._prefix}.{target_mode.value}"

    def topic(
        self,
        domain: EventDomain,
        event: EventType,
        mode: Optional[TradingMode] = None,
    ) -> str:
        target_mode = self._get_current_mode(mode)
        mode_prefix = f"{self._prefix}.{target_mode.value}"
        full_topic = f"{mode_prefix}.{domain.value}.{event.value}"

        if full_topic not in self._topic_registry:
            self._topic_registry[full_topic] = EventTopic(
                full=full_topic,
                namespace=mode_prefix,
                domain=domain.value,
                event=event.value,
                mode=target_mode.value,
            )
            self._stats["topics_created"] += 1

        return full_topic

    def market_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.MARKET, event, mode)

    def signal_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.SIGNAL, event, mode)

    def execution_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.EXECUTION, event, mode)

    def portfolio_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.PORTFOLIO, event, mode)

    def risk_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.RISK, event, mode)

    def ai_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.AI, event, mode)

    def system_topic(self, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(EventDomain.SYSTEM, event, mode)

    def parse_topic(self, full_topic: str) -> Optional[EventTopic]:
        return self._topic_registry.get(full_topic)

    def get_all_topics(self) -> List[str]:
        return list(self._topic_registry.keys())

    def get_topics_by_domain(self, domain: EventDomain) -> List[str]:
        return [
            t for t in self._topic_registry.keys()
            if f".{domain.value}." in t
        ]

    def get_topics_by_mode(self, mode: TradingMode) -> List[str]:
        prefix = f"{self._prefix}.{mode.value}"
        return [
            t for t in self._topic_registry.keys()
            if t.startswith(prefix)
        ]

    def redis_channel(self, domain: EventDomain, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(domain, event, mode)

    def ws_channel(self, domain: EventDomain, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return f"ws.{self.topic(domain, event, mode)}"

    def kafka_topic(self, domain: EventDomain, event: EventType, mode: Optional[TradingMode] = None) -> str:
        return self.topic(domain, event, mode).replace(".", "_")

    def get_stats(self) -> Dict[str, Any]:
        current_mode = None
        if self._mode_provider:
            try:
                current_mode = self._mode_provider().value
            except Exception:
                current_mode = "unknown"
        return {
            "prefix": self._prefix,
            "current_mode": current_mode,
            "topics_registered": len(self._topic_registry),
            "stats": self._stats.copy(),
        }


def get_event_namespace(mode_provider: Optional[Callable[[], TradingMode]] = None) -> EventNamespace:
    return EventNamespace(mode_provider=mode_provider)


def ns_topic(domain: EventDomain, event: EventType, mode: Optional[TradingMode] = None) -> str:
    ns = get_event_namespace()
    return ns.topic(domain, event, mode)


def ns_market(event: EventType, mode: Optional[TradingMode] = None) -> str:
    ns = get_event_namespace()
    return ns.market_topic(event, mode)


def ns_signal(event: EventType, mode: Optional[TradingMode] = None) -> str:
    ns = get_event_namespace()
    return ns.signal_topic(event, mode)


def ns_execution(event: EventType, mode: Optional[TradingMode] = None) -> str:
    ns = get_event_namespace()
    return ns.execution_topic(event, mode)


TOPICS = {
    "market_trade": lambda mode: ns_market(EventType.TRADE, mode),
    "market_tick": lambda mode: ns_market(EventType.TICK, mode),
    "market_liquidation": lambda mode: ns_market(EventType.LIQUIDATION, mode),
    "signal_triggered": lambda mode: ns_signal(EventType.SIGNAL_TRIGGERED, mode),
    "signal_expired": lambda mode: ns_signal(EventType.SIGNAL_EXPIRED, mode),
    "order_created": lambda mode: ns_execution(EventType.ORDER_CREATED, mode),
    "order_filled": lambda mode: ns_execution(EventType.ORDER_FILLED, mode),
    "position_opened": lambda mode: ns_execution(EventType.POSITION_OPENED, mode),
    "position_closed": lambda mode: ns_execution(EventType.POSITION_CLOSED, mode),
    "risk_warning": lambda mode: ns_execution(EventType.RISK_WARNING, mode),
    "circuit_breaker": lambda mode: ns_execution(EventType.CIRCUIT_BREAKER, mode),
}
