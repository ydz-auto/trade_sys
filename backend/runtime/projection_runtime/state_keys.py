from typing import Final


class ProjectionKeys:
    NAMESPACE: Final[str] = "projection"

    @classmethod
    def _key(cls, domain: str, entity: str = "", identifier: str = "") -> str:
        parts = [cls.NAMESPACE, domain]
        if entity:
            parts.append(entity)
        if identifier:
            parts.append(identifier)
        return ":".join(parts)

    @classmethod
    def dashboard_state(cls) -> str:
        return cls._key("dashboard", "state")

    @classmethod
    def dashboard_prices(cls) -> str:
        return cls._key("dashboard", "prices")

    @classmethod
    def dashboard_factors(cls) -> str:
        return cls._key("dashboard", "factors")

    @classmethod
    def dashboard_regime(cls, symbol: str = "BTC") -> str:
        return cls._key("dashboard", "regime", symbol)

    @classmethod
    def decision_latest(cls, symbol: str = "") -> str:
        if symbol:
            return cls._key("decision", "latest", symbol)
        return cls._key("decision", "latest")

    @classmethod
    def decision_history(cls, symbol: str = "") -> str:
        if symbol:
            return cls._key("decision", "history", symbol)
        return cls._key("decision", "history")

    @classmethod
    def decision_stats(cls) -> str:
        return cls._key("decision", "stats")

    @classmethod
    def risk_state(cls) -> str:
        return cls._key("risk", "state")

    @classmethod
    def risk_level(cls) -> str:
        return cls._key("risk", "level")

    @classmethod
    def risk_checks(cls) -> str:
        return cls._key("risk", "checks")

    @classmethod
    def risk_daily_metrics(cls) -> str:
        return cls._key("risk", "daily_metrics")

    @classmethod
    def position_current(cls) -> str:
        return cls._key("position", "current")

    @classmethod
    def position_by_symbol(cls, symbol: str) -> str:
        return cls._key("position", "symbol", symbol)

    @classmethod
    def position_history(cls) -> str:
        return cls._key("position", "history")

    @classmethod
    def position_pnl(cls) -> str:
        return cls._key("position", "pnl")

    @classmethod
    def timeline_events(cls) -> str:
        return cls._key("timeline", "events")

    @classmethod
    def timeline_by_symbol(cls, symbol: str) -> str:
        return cls._key("timeline", "symbol", symbol)

    @classmethod
    def timeline_by_type(cls, event_type: str) -> str:
        return cls._key("timeline", "type", event_type)

    @classmethod
    def metrics_worker(cls, worker_name: str) -> str:
        return cls._key("metrics", "worker", worker_name)

    @classmethod
    def metrics_system(cls) -> str:
        return cls._key("metrics", "system")

    @classmethod
    def metrics_kafka_lag(cls) -> str:
        return cls._key("metrics", "kafka_lag")

    @classmethod
    def signal_latest(cls, symbol: str = "") -> str:
        if symbol:
            return cls._key("signal", "latest", symbol)
        return cls._key("signal", "latest")

    @classmethod
    def signal_history(cls, symbol: str = "") -> str:
        if symbol:
            return cls._key("signal", "history", symbol)
        return cls._key("signal", "history")

    @classmethod
    def order_active(cls) -> str:
        return cls._key("order", "active")

    @classmethod
    def order_history(cls) -> str:
        return cls._key("order", "history")

    @classmethod
    def fill_today(cls) -> str:
        return cls._key("fill", "today")


class ProjectionChannels:
    NAMESPACE: Final[str] = "channel"

    @classmethod
    def _channel(cls, domain: str, sub: str = "") -> str:
        if sub:
            return f"{cls.NAMESPACE}:{domain}:{sub}"
        return f"{cls.NAMESPACE}:{domain}"

    @classmethod
    def prices(cls) -> str:
        return cls._channel("prices")

    @classmethod
    def dashboard(cls) -> str:
        return cls._channel("dashboard")

    @classmethod
    def decision(cls) -> str:
        return cls._channel("decision")

    @classmethod
    def risk(cls) -> str:
        return cls._channel("risk")

    @classmethod
    def position(cls) -> str:
        return cls._channel("position")

    @classmethod
    def timeline(cls) -> str:
        return cls._channel("timeline")

    @classmethod
    def signal(cls, symbol: str = "") -> str:
        if symbol:
            return cls._channel("signal", symbol)
        return cls._channel("signal")

    @classmethod
    def order(cls) -> str:
        return cls._channel("order")

    @classmethod
    def all(cls) -> list:
        return [
            cls.prices(),
            cls.dashboard(),
            cls.decision(),
            cls.risk(),
            cls.position(),
            cls.timeline(),
            cls.signal(),
            cls.order(),
        ]
