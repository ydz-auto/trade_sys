"""
State 状态定义
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


class StateType(str, Enum):
    SYSTEM = "system"
    TRADING = "trading"
    POSITION = "position"
    ORDER = "order"
    MARKET = "market"
    RISK = "risk"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"


class SystemMode(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    BACKTEST = "BACKTEST"
    SUSPENDED = "SUSPENDED"


class SystemStatus(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class SystemState:
    mode: SystemMode = SystemMode.PAPER
    status: SystemStatus = SystemStatus.READY
    allow_trading: bool = True
    active_strategies: List[str] = field(default_factory=list)
    services: Dict[str, str] = field(default_factory=dict)
    started_at: Optional[int] = None
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value if isinstance(self.mode, Enum) else self.mode,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "allow_trading": self.allow_trading,
            "active_strategies": self.active_strategies,
            "services": self.services,
            "started_at": self.started_at,
            "last_update": self.last_update,
        }


@dataclass
class MarketState:
    symbol: str
    regime: str = "unknown"
    volatility: float = 0.0
    trend: str = "neutral"
    support: float = 0.0
    resistance: float = 0.0
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "volatility": self.volatility,
            "trend": self.trend,
            "support": self.support,
            "resistance": self.resistance,
            "last_update": self.last_update,
        }


@dataclass
class Position:
    symbol: str
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: int = 1
    margin: float = 0.0
    liquidation_price: float = 0.0
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "size": self.size,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "last_update": self.last_update,
        }


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    order_type: str
    price: float = 0.0
    quantity: float = 0.0
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: str = "pending"
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "type": self.order_type,
            "price": self.price,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class TradingState:
    balance: float = 0.0
    equity: float = 0.0
    available_balance: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_position_value: float = 0.0
    total_exposure: float = 0.0
    margin_ratio: float = 0.0
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "balance": self.balance,
            "equity": self.equity,
            "available_balance": self.available_balance,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_position_value": self.total_position_value,
            "total_exposure": self.total_exposure,
            "margin_ratio": self.margin_ratio,
            "last_update": self.last_update,
        }


@dataclass
class RiskState:
    risk_index: int = 0
    risk_level: str = "normal"
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    daily_loss: float = 0.0
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_index": self.risk_index,
            "risk_level": self.risk_level,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "daily_loss": self.daily_loss,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "last_update": self.last_update,
        }


@dataclass
class StrategyState:
    strategy_id: str
    name: str
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    last_signal: Optional[str] = None
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "enabled": self.enabled,
            "parameters": self.parameters,
            "performance": self.performance,
            "last_signal": self.last_signal,
            "last_update": self.last_update,
        }


@dataclass
class PortfolioState:
    total_value: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    positions: List[Position] = field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    last_update: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_value": self.total_value,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "positions": [p.to_dict() for p in self.positions],
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "last_update": self.last_update,
        }


STATE_DEFAULTS: Dict[StateType, Dict[str, Any]] = {
    StateType.SYSTEM: SystemState().to_dict(),
    StateType.TRADING: TradingState().to_dict(),
    StateType.RISK: RiskState().to_dict(),
    StateType.POSITION: {},
    StateType.ORDER: {},
    StateType.MARKET: {},
    StateType.STRATEGY: {},
    StateType.PORTFOLIO: PortfolioState().to_dict(),
}


STATE_HISTORY_SIZE = 100
STATE_SNAPSHOT_INTERVAL = 60
