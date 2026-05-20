"""
Trading Mode Manager - 交易模式管理器

核心职责:
1. 管理三种交易模式: BACKTEST | PAPER | LIVE
2. 模式切换的状态机
3. Execution Adapter 的动态切换
4. Portfolio 隔离 (每种模式独立的 Portfolio)
5. 安全防护 (防止误操作)

架构:
    Market Runtime
           ↓
    Feature Runtime
           ↓
    Strategy Runtime
           ↓
    Trading Mode Manager  <-- 本模块
           ↓
    Execution Runtime
           ↓
    Portfolio Runtime (隔离)
"""
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import os

from pydantic import BaseModel, Field

from infrastructure.logging import get_logger

logger = get_logger("trading_mode.manager")


class TradingMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class ModeTransition(str, Enum):
    BACKTEST_TO_PAPER = "backtest->paper"
    BACKTEST_TO_LIVE = "backtest->live"
    PAPER_TO_BACKTEST = "paper->backtest"
    PAPER_TO_LIVE = "paper->live"
    LIVE_TO_BACKTEST = "live->backtest"
    LIVE_TO_PAPER = "live->paper"


@dataclass
class ModeConfig:
    market_data_source: str
    order_execution: str
    risk_engine: str
    portfolio_isolated: bool
    require_confirmation: bool
    color: str
    warning: Optional[str] = None


MODE_CONFIGS: Dict[TradingMode, ModeConfig] = {
    TradingMode.BACKTEST: ModeConfig(
        market_data_source="historical",
        order_execution="simulated",
        risk_engine="simulated",
        portfolio_isolated=True,
        require_confirmation=False,
        color="#3B82F6",
        warning=None,
    ),
    TradingMode.PAPER: ModeConfig(
        market_data_source="real",
        order_execution="simulated",
        risk_engine="real",
        portfolio_isolated=True,
        require_confirmation=False,
        color="#F59E0B",
        warning="Paper Trading: 真实行情 + 模拟下单",
    ),
    TradingMode.LIVE: ModeConfig(
        market_data_source="real",
        order_execution="real",
        risk_engine="real",
        portfolio_isolated=True,
        require_confirmation=True,
        color="#EF4444",
        warning="⚠️ LIVE MODE: 真实交易，请谨慎操作！",
    ),
}


class ModeState(str, Enum):
    IDLE = "idle"
    TRANSITIONING = "transitioning"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class ModeStatus:
    mode: TradingMode
    state: ModeState
    previous_mode: Optional[TradingMode] = None
    transition_time: Optional[datetime] = None
    error: Optional[str] = None
    confirmed: bool = False


class ModeTransitionRequest(BaseModel):
    target_mode: TradingMode
    reason: str = ""
    confirmed: bool = False
    force: bool = False


class TradingModeManager:
    _instance: Optional['TradingModeManager'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        initial_mode: Optional[TradingMode] = None,
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        if initial_mode is None:
            mode_str = os.getenv("TRADING_MODE", "paper").lower()
            try:
                initial_mode = TradingMode(mode_str)
            except ValueError:
                initial_mode = TradingMode.PAPER
                logger.warning(f"Invalid TRADING_MODE '{mode_str}', defaulting to PAPER")
        
        self._mode = initial_mode
        self._state = ModeState.ACTIVE
        self._previous_mode: Optional[TradingMode] = None
        self._transition_history: list[Dict[str, Any]] = []
        
        self._portfolios: Dict[TradingMode, Dict[str, Any]] = {
            TradingMode.BACKTEST: {"balance": {"USDT": 100000.0}, "positions": {}},
            TradingMode.PAPER: {"balance": {"USDT": 100000.0}, "positions": {}},
            TradingMode.LIVE: {"balance": {}, "positions": {}},
        }
        
        self._adapter: Optional[Any] = None
        self._exchange: str = "binance"
        
        self._mode_change_callbacks: list[Callable[[TradingMode, TradingMode], Awaitable[None]]] = []
        
        self._safety_checks: list[Callable[[], bool]] = []
        
        self._stats = {
            "total_transitions": 0,
            "failed_transitions": 0,
            "uptime_seconds": 0,
        }
        self._start_time = datetime.now()
        
        logger.info(f"TradingModeManager initialized with mode: {self._mode.value}")

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def state(self) -> ModeState:
        return self._state

    @property
    def config(self) -> ModeConfig:
        return MODE_CONFIGS[self._mode]

    def get_status(self) -> ModeStatus:
        return ModeStatus(
            mode=self._mode,
            state=self._state,
            previous_mode=self._previous_mode,
            transition_time=self._transition_history[-1].get("time") if self._transition_history else None,
        )

    def get_all_modes_info(self) -> list[Dict[str, Any]]:
        result = []
        for mode in TradingMode:
            config = MODE_CONFIGS[mode]
            result.append({
                "mode": mode.value,
                "config": {
                    "market_data_source": config.market_data_source,
                    "order_execution": config.order_execution,
                    "risk_engine": config.risk_engine,
                    "portfolio_isolated": config.portfolio_isolated,
                    "require_confirmation": config.require_confirmation,
                    "color": config.color,
                    "warning": config.warning,
                },
                "is_current": mode == self._mode,
                "portfolio": self._portfolios[mode],
            })
        return result

    def get_portfolio(self, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        target_mode = mode or self._mode
        return self._portfolios[target_mode].copy()

    def update_portfolio(self, balance: Dict[str, float], positions: Dict[str, Any]) -> None:
        self._portfolios[self._mode]["balance"] = balance.copy()
        self._portfolios[self._mode]["positions"] = positions.copy()

    def register_safety_check(self, check: Callable[[], bool]) -> None:
        self._safety_checks.append(check)

    def register_mode_change_callback(
        self,
        callback: Callable[[TradingMode, TradingMode], Awaitable[None]]
    ) -> None:
        self._mode_change_callbacks.append(callback)

    async def can_transition_to(self, target_mode: TradingMode) -> tuple[bool, str]:
        if self._state == ModeState.TRANSITIONING:
            return False, "Already transitioning"
        
        if target_mode == self._mode:
            return False, f"Already in {target_mode.value} mode"
        
        target_config = MODE_CONFIGS[target_mode]
        
        if target_config.require_confirmation:
            return True, f"Transition to {target_mode.value} requires confirmation"
        
        for check in self._safety_checks:
            if not check():
                return False, "Safety check failed"
        
        return True, "OK"

    async def transition_to(
        self,
        target_mode: TradingMode,
        reason: str = "",
        confirmed: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        if self._state == ModeState.TRANSITIONING:
            return {
                "success": False,
                "error": "Already transitioning",
                "current_mode": self._mode.value,
            }
        
        if target_mode == self._mode:
            return {
                "success": True,
                "message": f"Already in {target_mode.value} mode",
                "current_mode": self._mode.value,
            }
        
        target_config = MODE_CONFIGS[target_mode]
        
        if target_config.require_confirmation and not confirmed and not force:
            return {
                "success": False,
                "requires_confirmation": True,
                "warning": target_config.warning,
                "current_mode": self._mode.value,
                "target_mode": target_mode.value,
            }
        
        self._state = ModeState.TRANSITIONING
        old_mode = self._mode
        
        try:
            logger.info(f"Transitioning from {old_mode.value} to {target_mode.value}: {reason}")
            
            if self._adapter:
                await self._disconnect_adapter()
            
            self._mode = target_mode
            self._previous_mode = old_mode
            self._state = ModeState.ACTIVE
            
            await self._connect_adapter()
            
            transition_record = {
                "from": old_mode.value,
                "to": target_mode.value,
                "reason": reason,
                "time": datetime.now().isoformat(),
                "confirmed": confirmed,
            }
            self._transition_history.append(transition_record)
            self._stats["total_transitions"] += 1
            
            for callback in self._mode_change_callbacks:
                try:
                    await callback(old_mode, target_mode)
                except Exception as e:
                    logger.error(f"Mode change callback error: {e}")
            
            logger.info(f"Successfully transitioned to {target_mode.value}")
            
            return {
                "success": True,
                "previous_mode": old_mode.value,
                "current_mode": target_mode.value,
                "config": {
                    "market_data_source": target_config.market_data_source,
                    "order_execution": target_config.order_execution,
                    "risk_engine": target_config.risk_engine,
                },
                "warning": target_config.warning,
            }
            
        except Exception as e:
            self._state = ModeState.ERROR
            self._stats["failed_transitions"] += 1
            logger.error(f"Failed to transition to {target_mode.value}: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "current_mode": old_mode.value,
            }

    async def _disconnect_adapter(self) -> None:
        if self._adapter:
            try:
                await self._adapter.disconnect()
                logger.info(f"Disconnected adapter for {self._previous_mode.value if self._previous_mode else 'unknown'}")
            except Exception as e:
                logger.error(f"Error disconnecting adapter: {e}")
            self._adapter = None

    async def _connect_adapter(self) -> None:
        from services.execution_service.adapters.paper_trading_adapter import PaperTradingAdapter
        from services.execution_service.adapters.mock_adapter import MockAdapter
        from domain.execution.models import Exchange
        
        exchange = Exchange.BINANCE if self._exchange == "binance" else Exchange.OKX
        
        if self._mode == TradingMode.BACKTEST:
            self._adapter = MockAdapter(exchange)
        elif self._mode == TradingMode.PAPER:
            self._adapter = PaperTradingAdapter(
                exchange=exchange,
                initial_balance=self._portfolios[TradingMode.PAPER]["balance"],
            )
        elif self._mode == TradingMode.LIVE:
            if self._exchange == "binance":
                from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter
                self._adapter = BinanceFuturesAdapter()
            else:
                from services.execution_service.adapters.okx_adapter import OKXAdapter
                self._adapter = OKXAdapter()
        
        if self._adapter:
            await self._adapter.connect()
            logger.info(f"Connected adapter for {self._mode.value}")

    def get_adapter(self) -> Optional[Any]:
        return self._adapter

    def set_exchange(self, exchange: str) -> None:
        if exchange not in ["binance", "okx"]:
            raise ValueError(f"Invalid exchange: {exchange}")
        self._exchange = exchange
        logger.info(f"Exchange set to: {exchange}")

    def get_stats(self) -> Dict[str, Any]:
        uptime = (datetime.now() - self._start_time).total_seconds()
        return {
            "mode": self._mode.value,
            "state": self._state.value,
            "exchange": self._exchange,
            "uptime_seconds": uptime,
            "total_transitions": self._stats["total_transitions"],
            "failed_transitions": self._stats["failed_transitions"],
            "transition_history": self._transition_history[-10:],
        }

    def is_safe_to_trade(self) -> tuple[bool, str]:
        if self._state != ModeState.ACTIVE:
            return False, f"Mode state is {self._state.value}"
        
        if self._mode == TradingMode.LIVE:
            return True, "LIVE mode - real trading enabled"
        elif self._mode == TradingMode.PAPER:
            return True, "PAPER mode - simulated trading"
        else:
            return True, "BACKTEST mode - historical replay"


def get_trading_mode_manager() -> TradingModeManager:
    return TradingModeManager()
