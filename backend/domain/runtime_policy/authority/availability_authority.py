from abc import ABC, abstractmethod
from typing import Dict, Optional
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("runtime.authority.availability")


class EventTypeLatency(Enum):
    CANDLE = 100
    TRADE = 50
    ORDERBOOK = 20
    FUNDING = 200
    LIQUIDATION = 100


class LatencyModel(ABC):

    @abstractmethod
    def get_latency_ms(self, event_type: str, timestamp_ms: int) -> int:
        pass


class FixedLatencyModel(LatencyModel):

    def __init__(self, default_latency_ms: int = 100):
        self._default_latency_ms = default_latency_ms
        self._latency_config: Dict[str, int] = {
            EventTypeLatency.CANDLE.name: EventTypeLatency.CANDLE.value,
            EventTypeLatency.TRADE.name: EventTypeLatency.TRADE.value,
            EventTypeLatency.ORDERBOOK.name: EventTypeLatency.ORDERBOOK.value,
            EventTypeLatency.FUNDING.name: EventTypeLatency.FUNDING.value,
            EventTypeLatency.LIQUIDATION.name: EventTypeLatency.LIQUIDATION.value,
        }

    def set_latency(self, event_type: str, latency_ms: int) -> None:
        self._latency_config[event_type] = latency_ms

    def get_latency_ms(self, event_type: str, timestamp_ms: int) -> int:
        return self._latency_config.get(event_type, self._default_latency_ms)


class AvailabilityAuthority:

    def __init__(self, latency_model: Optional[LatencyModel] = None):
        self._latency_model = latency_model or FixedLatencyModel()

    @property
    def latency_model(self) -> LatencyModel:
        return self._latency_model

    def compute_available_time(
        self,
        event_time_ms: int,
        event_type: str,
    ) -> int:
        latency_ms = self._latency_model.get_latency_ms(event_type, event_time_ms)
        available_time_ms = event_time_ms + latency_ms

        logger.debug(
            f"Computed available_time: event={event_time_ms}, "
            f"latency={latency_ms}, available={available_time_ms}"
        )

        return available_time_ms

    def is_available(
        self,
        available_time_ms: int,
        clock_ms: int,
    ) -> bool:
        return available_time_ms <= clock_ms

    def validate_availability(
        self,
        available_time_ms: int,
        clock_ms: int,
        event_id: str,
    ) -> tuple[bool, Optional[str]]:
        if not self.is_available(available_time_ms, clock_ms):
            error_msg = (
                f"Event {event_id} not available: "
                f"available_time={available_time_ms} > clock_time={clock_ms}"
            )
            logger.warning(error_msg)
            return False, error_msg

        return True, None

    def __repr__(self) -> str:
        return f"AvailabilityAuthority(latency_model={type(self._latency_model).__name__})"
