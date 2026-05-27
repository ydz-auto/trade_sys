"""
Runtime Context - Runtime 共享上下文

核心职责:
1. 所有 runtime 共享的上下文
2. 当前模式、namespace、session
3. 市场、风险状态 (RuntimeContext 是 market/risk 状态的唯一 Owner)
4. 配置传递

状态归属:
    market_state → RuntimeContext (this)
    risk_state   → RuntimeContext (this)
    其他状态     → 各自 Runtime
"""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import asyncio

from domain.trading_mode import TradingMode
from runtime.trading_mode_manager import get_trading_mode_manager
from runtime.kernel.namespace import get_runtime_isolation
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

logger = get_logger("runtime.context")


@dataclass
class MarketContext:
    symbols: list[str] = field(default_factory=list)
    primary_symbol: Optional[str] = None
    regime: str = "unknown"
    volatility: float = 0.0
    trend: str = "neutral"
    last_update: Optional[datetime] = None


@dataclass
class RiskContext:
    level: str = "safe"
    leverage_limit: float = 10.0
    position_limit: float = 1.0
    drawdown_limit: float = 0.1
    circuit_breaker_active: bool = False
    last_check: Optional[datetime] = None


@dataclass
class SessionContext:
    session_id: str
    mode: TradingMode
    namespace: str
    started_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class RuntimeContext:
    _instance: Optional['RuntimeContext'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True

        self._mode_manager = get_trading_mode_manager()
        self._isolation = get_runtime_isolation()

        self._session: Optional[SessionContext] = None
        self._market = MarketContext()
        self._risk = RiskContext()

        self._config: Dict[str, Any] = {}

        self._lock = asyncio.Lock()

        logger.info("RuntimeContext initialized (market/risk state owner)")

    @property
    def mode(self) -> TradingMode:
        return self._mode_manager.mode

    @property
    def namespace(self) -> str:
        return self._isolation.get_namespace()

    @property
    def session(self) -> Optional[SessionContext]:
        return self._session

    @property
    def market(self) -> MarketContext:
        return self._market

    @property
    def risk(self) -> RiskContext:
        return self._risk

    def create_session(self, session_id: Optional[str] = None) -> SessionContext:
        import uuid
        session_id = session_id or str(uuid.uuid4())[:8]

        self._session = SessionContext(
            session_id=session_id,
            mode=self.mode,
            namespace=self.namespace,
            started_at=datetime.fromtimestamp(now_ms() / 1000),
        )

        logger.info(f"Created session: {session_id} (mode={self.mode.value})")

        return self._session

    def end_session(self) -> None:
        if self._session:
            logger.info(f"Ended session: {self._session.session_id}")
            self._session = None

    def update_market(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self._market, key):
                setattr(self._market, key, value)
        self._market.last_update = datetime.fromtimestamp(now_ms() / 1000)

    def update_risk(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self._risk, key):
                setattr(self._risk, key, value)
        self._risk.last_check = datetime.fromtimestamp(now_ms() / 1000)

    def set_config(self, key: str, value: Any) -> None:
        self._config[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def is_paper_mode(self) -> bool:
        return self.mode == TradingMode.PAPER

    def is_live_mode(self) -> bool:
        return self.mode == TradingMode.LIVE

    def is_backtest_mode(self) -> bool:
        return self.mode == TradingMode.BACKTEST

    def is_safe_to_trade(self) -> bool:
        if self._risk.circuit_breaker_active:
            return False
        if self._risk.level in ["critical", "emergency"]:
            return False
        return True

    def get_event_topic(self, event_type: str) -> str:
        return f"{self.namespace}.{event_type}"

    def get_state(self) -> Dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "namespace": self.namespace,
            "session": {
                "session_id": self._session.session_id,
                "mode": self._session.mode.value,
                "started_at": self._session.started_at.isoformat(),
            } if self._session else None,
            "market": {
                "symbols": self._market.symbols,
                "primary_symbol": self._market.primary_symbol,
                "regime": self._market.regime,
                "volatility": self._market.volatility,
                "trend": self._market.trend,
            },
            "risk": {
                "level": self._risk.level,
                "leverage_limit": self._risk.leverage_limit,
                "position_limit": self._risk.position_limit,
                "circuit_breaker_active": self._risk.circuit_breaker_active,
            },
        }


def get_runtime_context() -> RuntimeContext:
    return RuntimeContext()
