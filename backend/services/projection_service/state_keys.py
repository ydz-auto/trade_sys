"""
Projection State Keys - Redis Key 定义

所有 Projection 状态的 Redis Key 规范

Key 命名规范：
    projection:{domain}:{entity}:{id}

TTL 策略：
    - 实时状态：无 TTL（持久化）
    - 临时状态：根据业务设置 TTL
"""

from typing import Final


class ProjectionKeys:
    """
    Projection Redis Key 定义
    
    分层设计：
    - dashboard:*     → Dashboard 状态
    - decision:*      → 决策状态
    - risk:*          → 风控状态
    - position:*      → 持仓状态
    - timeline:*      → 事件时间线
    - metrics:*       → 运行指标
    """

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
        """Dashboard 总览状态"""
        return cls._key("dashboard", "state")

    @classmethod
    def dashboard_prices(cls) -> str:
        """Dashboard 价格列表"""
        return cls._key("dashboard", "prices")

    @classmethod
    def dashboard_factors(cls) -> str:
        """Dashboard 因子状态"""
        return cls._key("dashboard", "factors")

    @classmethod
    def dashboard_regime(cls, symbol: str = "BTC") -> str:
        """Dashboard 市场状态"""
        return cls._key("dashboard", "regime", symbol)

    @classmethod
    def decision_latest(cls, symbol: str = "") -> str:
        """最新决策"""
        if symbol:
            return cls._key("decision", "latest", symbol)
        return cls._key("decision", "latest")

    @classmethod
    def decision_history(cls, symbol: str = "") -> str:
        """决策历史（List）"""
        if symbol:
            return cls._key("decision", "history", symbol)
        return cls._key("decision", "history")

    @classmethod
    def decision_stats(cls) -> str:
        """决策统计"""
        return cls._key("decision", "stats")

    @classmethod
    def risk_state(cls) -> str:
        """风控状态"""
        return cls._key("risk", "state")

    @classmethod
    def risk_level(cls) -> str:
        """风险等级"""
        return cls._key("risk", "level")

    @classmethod
    def risk_checks(cls) -> str:
        """风控检查记录"""
        return cls._key("risk", "checks")

    @classmethod
    def risk_daily_metrics(cls) -> str:
        """每日风控指标"""
        return cls._key("risk", "daily_metrics")

    @classmethod
    def position_current(cls) -> str:
        """当前持仓"""
        return cls._key("position", "current")

    @classmethod
    def position_by_symbol(cls, symbol: str) -> str:
        """按品种持仓"""
        return cls._key("position", "symbol", symbol)

    @classmethod
    def position_history(cls) -> str:
        """持仓历史"""
        return cls._key("position", "history")

    @classmethod
    def position_pnl(cls) -> str:
        """持仓盈亏"""
        return cls._key("position", "pnl")

    @classmethod
    def timeline_events(cls) -> str:
        """事件时间线（List，最新在前）"""
        return cls._key("timeline", "events")

    @classmethod
    def timeline_by_symbol(cls, symbol: str) -> str:
        """按品种的事件时间线"""
        return cls._key("timeline", "symbol", symbol)

    @classmethod
    def timeline_by_type(cls, event_type: str) -> str:
        """按类型的事件时间线"""
        return cls._key("timeline", "type", event_type)

    @classmethod
    def metrics_worker(cls, worker_name: str) -> str:
        """Worker 运行指标"""
        return cls._key("metrics", "worker", worker_name)

    @classmethod
    def metrics_system(cls) -> str:
        """系统运行指标"""
        return cls._key("metrics", "system")

    @classmethod
    def metrics_kafka_lag(cls) -> str:
        """Kafka 消费延迟"""
        return cls._key("metrics", "kafka_lag")

    @classmethod
    def signal_latest(cls, symbol: str = "") -> str:
        """最新信号"""
        if symbol:
            return cls._key("signal", "latest", symbol)
        return cls._key("signal", "latest")

    @classmethod
    def signal_history(cls, symbol: str = "") -> str:
        """信号历史"""
        if symbol:
            return cls._key("signal", "history", symbol)
        return cls._key("signal", "history")

    @classmethod
    def order_active(cls) -> str:
        """活跃订单"""
        return cls._key("order", "active")

    @classmethod
    def order_history(cls) -> str:
        """订单历史"""
        return cls._key("order", "history")

    @classmethod
    def fill_today(cls) -> str:
        """今日成交"""
        return cls._key("fill", "today")


class ProjectionChannels:
    """
    WebSocket 推送频道
    
    前端订阅这些频道获取实时更新
    """

    NAMESPACE: Final[str] = "channel"

    @classmethod
    def _channel(cls, domain: str, sub: str = "") -> str:
        if sub:
            return f"{cls.NAMESPACE}:{domain}:{sub}"
        return f"{cls.NAMESPACE}:{domain}"

    @classmethod
    def prices(cls) -> str:
        """价格实时推送频道（高频）"""
        return cls._channel("prices")

    @classmethod
    def dashboard(cls) -> str:
        """Dashboard 更新频道"""
        return cls._channel("dashboard")

    @classmethod
    def decision(cls) -> str:
        """决策更新频道"""
        return cls._channel("decision")

    @classmethod
    def risk(cls) -> str:
        """风控更新频道"""
        return cls._channel("risk")

    @classmethod
    def position(cls) -> str:
        """持仓更新频道"""
        return cls._channel("position")

    @classmethod
    def timeline(cls) -> str:
        """事件时间线频道"""
        return cls._channel("timeline")

    @classmethod
    def signal(cls, symbol: str = "") -> str:
        """信号频道"""
        if symbol:
            return cls._channel("signal", symbol)
        return cls._channel("signal")

    @classmethod
    def order(cls) -> str:
        """订单频道"""
        return cls._channel("order")

    @classmethod
    def all(cls) -> list:
        """所有频道"""
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
