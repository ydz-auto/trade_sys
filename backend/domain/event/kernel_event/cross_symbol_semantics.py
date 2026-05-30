from dataclasses import dataclass, field
from infrastructure.logging import get_logger
from domain.event.kernel_event.event_time_manager import (
    EventTimeManager,
    get_event_time_manager,
)
from domain.event.time_types import EventTimeRecord, EventSource

logger = get_logger("runtime.kernel.event.cross_symbol_semantics")


@dataclass
class SymbolAvailability:
    symbol: str = ""
    last_exchange_time: int = 0
    last_receive_time: int = 0
    last_available_at: int = 0
    is_ready: bool = False
    pending_events: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "last_exchange_time": self.last_exchange_time,
            "last_receive_time": self.last_receive_time,
            "last_available_at": self.last_available_at,
            "is_ready": self.is_ready,
            "pending_events": self.pending_events,
            "latency_ms": self.latency_ms,
        }


@dataclass
class CrossSymbolAvailability:
    query_time: int = 0
    symbols: dict = field(default_factory=dict)
    all_ready: bool = False
    ready_symbols: list = field(default_factory=list)
    pending_symbols: list = field(default_factory=list)
    min_available_time: int = 0
    max_latency_ms: int = 0

    def get_safe_query_time(self) -> int:
        if not self.symbols:
            return self.query_time
        return min(s.last_available_at for s in self.symbols.values())

    def to_dict(self) -> dict:
        return {
            "query_time": self.query_time,
            "all_ready": self.all_ready,
            "ready_symbols": self.ready_symbols,
            "pending_symbols": self.pending_symbols,
            "min_available_time": self.min_available_time,
            "max_latency_ms": self.max_latency_ms,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
        }


class CrossSymbolEventSemantics:

    def __init__(self, symbols: list):
        self.symbols = set(symbols)
        self._symbol_availability: dict = {}
        self._event_time_managers: dict = {}
        for symbol in symbols:
            self._symbol_availability[symbol] = SymbolAvailability(
                symbol=symbol,
                last_exchange_time=0,
                last_receive_time=0,
                last_available_at=0,
                is_ready=False,
            )
            self._event_time_managers[symbol] = EventTimeManager()
        self._cross_symbol_features: dict = {}
        self._leakage_log: list = []

    def register_cross_symbol_feature(self, feature_name: str, required_symbols: list):
        self._cross_symbol_features[feature_name] = set(required_symbols)
        logger.info(f"Registered cross-symbol feature: {feature_name} requires {required_symbols}")

    def update_symbol_availability(self, symbol: str, exchange_time: int, receive_time: int = None, network_delay_ms: int = 100, processing_delay_ms: int = 50):
        if symbol not in self.symbols:
            logger.warning(f"Unknown symbol: {symbol}")
            return
        if receive_time is None:
            from datetime import datetime
            receive_time = int(datetime.utcnow().timestamp() * 1000)
        available_at = receive_time + processing_delay_ms
        current = self._symbol_availability[symbol]
        self._symbol_availability[symbol] = SymbolAvailability(
            symbol=symbol,
            last_exchange_time=max(current.last_exchange_time, exchange_time),
            last_receive_time=max(current.last_receive_time, receive_time),
            last_available_at=max(current.last_available_at, available_at),
            is_ready=True,
            latency_ms=receive_time - exchange_time + processing_delay_ms,
        )

    def check_cross_symbol_availability(self, query_time: int, required_symbols: list = None) -> CrossSymbolAvailability:
        symbols_to_check = set(required_symbols) if required_symbols else self.symbols
        symbol_states: dict = {}
        ready_symbols = []
        pending_symbols = []
        for symbol in symbols_to_check:
            if symbol not in self._symbol_availability:
                pending_symbols.append(symbol)
                continue
            state = self._symbol_availability[symbol]
            symbol_states[symbol] = state
            if state.last_available_at <= query_time:
                ready_symbols.append(symbol)
            else:
                pending_symbols.append(symbol)
        all_ready = len(pending_symbols) == 0
        min_available_time = 0
        max_latency_ms = 0
        if symbol_states:
            min_available_time = min(s.last_available_at for s in symbol_states.values())
            max_latency_ms = max(s.latency_ms for s in symbol_states.values())
        return CrossSymbolAvailability(
            query_time=query_time,
            symbols=symbol_states,
            all_ready=all_ready,
            ready_symbols=ready_symbols,
            pending_symbols=pending_symbols,
            min_available_time=min_available_time,
            max_latency_ms=max_latency_ms,
        )

    def check_feature_availability(self, feature_name: str, query_time: int):
        required_symbols = self._cross_symbol_features.get(feature_name)
        if required_symbols is None:
            return True, self.check_cross_symbol_availability(query_time, [])
        availability = self.check_cross_symbol_availability(query_time, list(required_symbols))
        if not availability.all_ready:
            self._log_leakage_attempt(feature_name=feature_name, query_time=query_time, pending_symbols=availability.pending_symbols)
        return availability.all_ready, availability

    def get_safe_query_time(self, required_symbols: list = None, query_time: int = None) -> int:
        availability = self.check_cross_symbol_availability(query_time or 0, required_symbols)
        return availability.get_safe_query_time()

    def compute_cross_symbol_feature(self, feature_name: str, compute_fn, query_time: int, strict: bool = True):
        is_available, availability = self.check_feature_availability(feature_name, query_time)
        if not is_available:
            msg = f"Cross-symbol feature {feature_name} not available at {query_time}. Pending symbols: {availability.pending_symbols}"
            if strict:
                raise ValueError(msg)
            logger.warning(msg)
            return None, availability
        try:
            result = compute_fn()
            return result, availability
        except Exception as e:
            logger.error(f"Error computing cross-symbol feature {feature_name}: {e}")
            return None, availability

    def _log_leakage_attempt(self, feature_name: str, query_time: int, pending_symbols: list):
        from datetime import datetime
        self._leakage_log.append({
            "feature_name": feature_name,
            "query_time": query_time,
            "pending_symbols": pending_symbols,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_leakage_report(self) -> dict:
        feature_counts: dict = {}
        for log in self._leakage_log:
            feature = log["feature_name"]
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
        return {
            "total_attempts": len(self._leakage_log),
            "feature_counts": feature_counts,
            "recent_attempts": self._leakage_log[-10:],
        }

    def get_symbol_status(self) -> dict:
        return {symbol: state.to_dict() for symbol, state in self._symbol_availability.items()}


_semantics_instances: dict = {}


def get_cross_symbol_semantics(symbols: list, instance_id: str = "default") -> CrossSymbolEventSemantics:
    if symbols is None:
        symbols = []
    key = f"{instance_id}_{'_'.join(sorted(symbols))}"
    if key not in _semantics_instances:
        _semantics_instances[key] = CrossSymbolEventSemantics(symbols)
    return _semantics_instances[key]
