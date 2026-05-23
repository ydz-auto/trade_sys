import uuid
from enum import Enum
from typing import Optional, Dict, Any, List, Callable

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from infrastructure.runtime_clock import now_ms, ClockMode


def generate_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:16]}"


def generate_trace_id() -> str:
    return f"trc_{uuid.uuid4().hex[:16]}"


class PipelineEventType(str, Enum):
    RAW_DATA = "raw_data"
    MARKET = "market"
    FEATURE = "feature"
    SIGNAL = "signal"
    NARRATIVE = "narrative"
    DECISION = "decision"
    RISK_CHECKED = "risk_checked"
    ORDER = "order"
    FILL = "fill"
    SYSTEM = "system"
    ERROR = "error"


class EventCategory(str, Enum):
    DATA = "data"
    MARKET = "market"
    FEATURE = "feature"
    SIGNAL = "signal"
    NARRATIVE = "narrative"
    EXECUTION = "execution"
    RISK = "risk"
    SYSTEM = "system"


class EventSource(str, Enum):
    INGESTION_RUNTIME = "ingestion_runtime"
    FEATURE_RUNTIME = "feature_runtime"
    SIGNAL_RUNTIME = "signal_runtime"
    EXECUTION_RUNTIME = "execution_runtime"
    PORTFOLIO_RUNTIME = "portfolio_runtime"
    PROJECTION_RUNTIME = "projection_runtime"
    CORRELATION_RUNTIME = "correlation_runtime"
    REGIME_RUNTIME = "regime_runtime"
    NARRATIVE_RUNTIME = "narrative_runtime"
    REPLAY_RUNTIME = "replay_runtime"
    DATA_SERVICE = "data_service"
    AGGREGATION_SERVICE = "aggregation_service"
    EVENT_SERVICE = "event_service"
    STRATEGY_SERVICE = "strategy_service"
    EXECUTION_SERVICE = "execution_service"
    EXTERNAL = "external"
    SYSTEM = "system"


SCHEMA_VERSION = "2.0"


class BaseEvent(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_timedelta="iso8601",
        arbitrary_types_allowed=True,
    )

    event_id: str = Field(default_factory=generate_event_id)
    trace_id: str = Field(default_factory=generate_trace_id)
    parent_event_id: Optional[str] = Field(default=None)

    schema_version: str = Field(default=SCHEMA_VERSION)

    event_type: str = Field(description="Event type: routing key")
    category: str = Field(description="Event category: grouping")

    source: str = Field(default=EventSource.SYSTEM.value)
    symbol: Optional[str] = Field(default=None)

    event_time_ms: int = Field(description="When the event occurred (exchange/source time)")
    ingest_time_ms: int = Field(default_factory=now_ms, description="When we received it")
    process_time_ms: int = Field(default_factory=now_ms, description="When runtime processed it")

    clock_mode: str = Field(default=ClockMode.LIVE.value)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, v):
        if isinstance(v, list):
            v = v[0] if v else None
        if not v:
            return None
        v = str(v).upper()
        if "/" in v:
            v = v.replace("/", "")
        if "-" in v:
            v = v.replace("-", "")
        return v

    @model_validator(mode="after")
    def validate_event_type_not_empty(self):
        if not self.event_type:
            raise ValueError("event_type must not be empty")
        return self

    def derive_child(self, event_type: str, source: str, clock_ms: Optional[int] = None, **kwargs) -> "BaseEvent":
        child_kwargs = {
            "trace_id": self.trace_id,
            "parent_event_id": self.event_id,
            "event_type": event_type,
            "source": source,
            "symbol": self.symbol,
            "event_time_ms": clock_ms if clock_ms is not None else now_ms(),
            "ingest_time_ms": now_ms(),
            "process_time_ms": now_ms(),
            "clock_mode": self.clock_mode,
        }
        child_kwargs.update(kwargs)
        return self.__class__(**child_kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseEvent":
        return cls(**data)

    def to_trace_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "event_time_ms": self.event_time_ms,
        }

    def with_metadata(self, **kwargs) -> "BaseEvent":
        merged = dict(self.metadata)
        merged.update(kwargs)
        return self.model_copy(update={"metadata": merged})


class RawDataEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.RAW_DATA.value)
    category: str = Field(default=EventCategory.DATA.value)

    data_type: str = Field(default="news", description="news/tweet/trade/kline/orderbook")
    data: Dict[str, Any] = Field(default_factory=dict)
    data_source: str = Field(default="")


class MarketEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.MARKET.value)
    category: str = Field(default=EventCategory.MARKET.value)

    market_type: str = Field(default="spot")
    timeframe: str = Field(default="1m")

    open: Optional[float] = Field(default=None)
    high: Optional[float] = Field(default=None)
    low: Optional[float] = Field(default=None)
    close: Optional[float] = Field(default=None)
    volume: Optional[float] = Field(default=None)
    price: Optional[float] = Field(default=None)
    quantity: Optional[float] = Field(default=None)


class FeatureEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.FEATURE.value)
    category: str = Field(default=EventCategory.FEATURE.value)

    feature_names: List[str] = Field(default_factory=list)
    feature_values: Dict[str, float] = Field(default_factory=dict)
    timeframe: str = Field(default="4h")


class SignalEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.SIGNAL.value)
    category: str = Field(default=EventCategory.SIGNAL.value)

    signal_name: str = Field(default="")
    direction: str = Field(default="neutral")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    strength: float = Field(default=0.5, ge=0.0, le=1.0)

    event_count: int = Field(default=0)
    event_types: List[str] = Field(default_factory=list)
    factors: Dict[str, float] = Field(default_factory=dict)

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and self.event_count >= 3

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.6 and self.event_count >= 2


class NarrativeEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.NARRATIVE.value)
    category: str = Field(default=EventCategory.NARRATIVE.value)

    narrative_type: str = Field(description="etf_inflow/liquidation/hack/...")
    direction: str = Field(default="neutral")
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    affected_symbols: List[str] = Field(default_factory=list)
    raw_data_ids: List[str] = Field(default_factory=list)


class DecisionEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.DECISION.value)
    category: str = Field(default=EventCategory.EXECUTION.value)

    decision_id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    action: str = Field(description="LONG/SHORT/HOLD/CLOSE")
    quantity: float = Field(default=0.0, ge=0.0)
    price: Optional[float] = Field(default=None)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="")
    strategy_id: str = Field(default="")
    signal_id: Optional[str] = Field(default=None)

    @property
    def is_buy(self) -> bool:
        return self.action.upper() in ("LONG", "BUY")

    @property
    def is_sell(self) -> bool:
        return self.action.upper() in ("SHORT", "SELL")

    @property
    def is_hold(self) -> bool:
        return self.action.upper() == "HOLD"

    @property
    def is_actionable(self) -> bool:
        return not self.is_hold and self.confidence >= 0.5


class RiskCheckedEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.RISK_CHECKED.value)
    category: str = Field(default=EventCategory.RISK.value)

    original_decision_id: str = Field()
    approved: bool = Field(default=False)
    risk_level: str = Field(default="low")

    rejection_reason: Optional[str] = Field(default=None)
    warnings: List[str] = Field(default_factory=list)
    check_results: Dict[str, Any] = Field(default_factory=dict)

    @property
    def can_execute(self) -> bool:
        return self.approved


class OrderEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.ORDER.value)
    category: str = Field(default=EventCategory.EXECUTION.value)

    order_id: str = Field()
    client_order_id: Optional[str] = Field(default=None)

    order_type: str = Field(default="limit")
    side: str = Field(description="buy/sell")

    price: Optional[float] = Field(default=None)
    quantity: float = Field()
    filled_quantity: float = Field(default=0.0)

    status: str = Field(default="new")
    decision_id: Optional[str] = Field(default=None)


class FillEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.FILL.value)
    category: str = Field(default=EventCategory.EXECUTION.value)

    fill_id: str = Field(default_factory=lambda: f"fill_{uuid.uuid4().hex[:12]}")
    order_id: str = Field()

    side: str = Field(description="buy/sell")
    price: float = Field()
    quantity: float = Field()
    fee: float = Field(default=0.0)
    fee_currency: str = Field(default="USDT")

    realized_pnl: Optional[float] = Field(default=None)


class SystemEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.SYSTEM.value)
    category: str = Field(default=EventCategory.SYSTEM.value)

    system_type: str = Field()
    severity: str = Field(default="info")
    message: str = Field(default="")


class ErrorEvent(BaseEvent):
    event_type: str = Field(default=PipelineEventType.ERROR.value)
    category: str = Field(default=EventCategory.SYSTEM.value)

    error_code: str = Field(default="UNKNOWN")
    error_message: str = Field(default="")
    error_details: Dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = Field(default=False)


class EventFactory:
    _clock_ms: Optional[Callable[[], int]] = None

    @classmethod
    def set_clock(cls, clock_ms: Callable[[], int]) -> None:
        cls._clock_ms = clock_ms

    @classmethod
    def _now(cls) -> int:
        if cls._clock_ms is not None:
            return cls._clock_ms()
        return now_ms()

    @classmethod
    def create(
        cls,
        event_type: str,
        source: str,
        symbol: Optional[str] = None,
        event_time_ms: Optional[int] = None,
        parent: Optional[BaseEvent] = None,
        **kwargs,
    ) -> BaseEvent:
        if event_time_ms is None:
            event_time_ms = cls._now()

        trace_id = parent.trace_id if parent else generate_trace_id()
        parent_event_id = parent.event_id if parent else None
        clock_mode = parent.clock_mode if parent else ClockMode.LIVE.value

        event_class = EVENT_CLASS_MAP.get(event_type, BaseEvent)
        return event_class(
            event_type=event_type,
            source=source,
            symbol=symbol,
            event_time_ms=event_time_ms,
            ingest_time_ms=cls._now(),
            process_time_ms=cls._now(),
            trace_id=trace_id,
            parent_event_id=parent_event_id,
            clock_mode=clock_mode,
            **kwargs,
        )
