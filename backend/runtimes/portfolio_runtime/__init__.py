"""
Portfolio Runtime - 组合运行时（实盘核心）

单一状态 owner：
- positions -> self.portfolio
- pnl_timeline -> self.portfolio
- exposure -> self.exposure_manager
- capital_allocation -> self.capital_allocator

不变量：
- 所有 position 状态变更必须通过此 runtime
- 外部只能通过 RuntimeBus 发送 command 来修改 position
- PortfolioService 不再持有独立 Portfolio 实例
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from runtime.kernel.base import BaseRuntime, RuntimeConfig
from runtime.kernel.shared import RuntimeLifecycle, RuntimeMetrics, RuntimeHealthCheck
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

from domain.portfolio import Portfolio, Position
from domain.portfolio.exposure import ExposureManager, ExposureConfig
from domain.portfolio.leverage import CapitalAllocator, CapitalAllocatorConfig, AllocationResult
from domain.signal import Signal, SignalRegistry


logger = get_logger("portfolio_runtime")


def _utcnow() -> datetime:
    return datetime.utcfromtimestamp(now_ms() / 1000)


@dataclass
class PortfolioRuntimeConfig(RuntimeConfig):
    name: str = "portfolio_runtime"
    initial_capital: float = 10000.0
    max_total_exposure: float = 1.0
    max_single_symbol_exposure: float = 0.3
    max_leverage: float = 5.0
    update_interval_seconds: float = 1.0
    risk_check_interval_seconds: float = 5.0


class PortfolioRuntime(BaseRuntime):
    """
    Portfolio Runtime - 组合运行时

    单一状态 owner：
    - positions -> self.portfolio
    - pnl_timeline -> self.portfolio
    - exposure -> self.exposure_manager
    - capital_allocation -> self.capital_allocator
    """

    def __init__(self, config: Optional[PortfolioRuntimeConfig] = None):
        config = config or PortfolioRuntimeConfig()
        super().__init__(config)
        self.config: PortfolioRuntimeConfig = config

        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None

        self.portfolio: Optional[Portfolio] = None
        self.exposure_manager: Optional[ExposureManager] = None
        self.capital_allocator: Optional[CapitalAllocator] = None
        self.signal_registry: Optional[SignalRegistry] = None

        self._price_cache: Dict[str, float] = {}
        self.risk_alerts: List[Dict[str, Any]] = []
        self.last_updated: Optional[datetime] = None
        self._state: Dict[str, Any] = {"positions": [], "accounts": {}}

    async def initialize(self) -> None:
        logger.info("Initializing Portfolio Runtime...")

        self.lifecycle = RuntimeLifecycle("portfolio")
        self.metrics = RuntimeMetrics("portfolio")
        self.health_check = RuntimeHealthCheck("portfolio")

        self.signal_registry = SignalRegistry()

        self.portfolio = Portfolio(
            initial_capital=self.config.initial_capital,
            current_capital=self.config.initial_capital,
            available_capital=self.config.initial_capital,
        )
        self.exposure_manager = ExposureManager(ExposureConfig())
        self.capital_allocator = CapitalAllocator(CapitalAllocatorConfig())

        logger.info("Portfolio Runtime initialized successfully")

    async def update_price(self, symbol: str, price: float, exchange: str = "binance") -> None:
        key = f"{exchange}:{symbol}"
        self._price_cache[key] = price
        if self.portfolio:
            self.portfolio.update_position_price(symbol, price, exchange)

    async def can_open_position(
        self,
        symbol: str,
        exchange: str,
        quantity: float,
        price: float,
        leverage: int = 1,
    ) -> tuple[bool, str]:
        from domain.portfolio.pnl import PortfolioState

        if not self.portfolio:
            return False, "Portfolio not loaded"

        if self.portfolio.state != PortfolioState.ACTIVE:
            return False, "Portfolio not active"

        if not self.portfolio.can_open_position(symbol, quantity, price, leverage):
            return False, "Position limit exceeded"

        additional_value = abs(quantity) * price
        passed, reason = self.exposure_manager.check_exposure_limit(
            symbol=symbol,
            exchange=exchange,
            additional_value=additional_value,
            capital=self.portfolio.current_capital,
            is_long=quantity > 0,
        )

        if not passed:
            return False, reason

        return True, "OK"

    async def open_position(
        self,
        symbol: str,
        exchange: str,
        quantity: float,
        price: float,
        leverage: int = 1,
        strategy_id: str = "",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> tuple[Optional[Position], str]:
        can_open, reason = await self.can_open_position(symbol, exchange, quantity, price, leverage)

        if not can_open:
            return None, reason

        position = self.portfolio.open_position(
            symbol=symbol,
            exchange=exchange,
            quantity=quantity,
            price=price,
            leverage=leverage,
            strategy_id=strategy_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.exposure_manager.update_exposure(
            symbol=symbol,
            exchange=exchange,
            long_quantity=quantity if quantity > 0 else 0,
            short_quantity=abs(quantity) if quantity < 0 else 0,
            price=price,
        )

        self._price_cache[f"{exchange}:{symbol}"] = price
        self.last_updated = _utcnow()
        self.metrics.increment("position_opens")

        return position, "OK"

    async def close_position(
        self,
        symbol: str,
        exchange: str = "binance",
        quantity: Optional[float] = None,
        price: float = 0.0,
    ) -> tuple[float, str]:
        if not self.portfolio:
            return 0.0, "Portfolio not loaded"

        position = self.portfolio.get_position(symbol, exchange)
        if not position:
            return 0.0, "No position found"

        if price <= 0:
            key = f"{exchange}:{symbol}"
            price = self._price_cache.get(key, 0.0)

        realized_pnl = self.portfolio.close_position(symbol, exchange, quantity, price)

        remaining = self.portfolio.get_position(symbol, exchange)
        if remaining:
            self.exposure_manager.update_exposure(
                symbol=symbol,
                exchange=exchange,
                long_quantity=remaining.quantity if remaining.quantity > 0 else 0,
                short_quantity=abs(remaining.quantity) if remaining.quantity < 0 else 0,
                price=price,
            )
        else:
            key = f"{exchange}:{symbol}"
            if key in self.exposure_manager.exposures:
                del self.exposure_manager.exposures[key]

        self.last_updated = _utcnow()
        self.metrics.increment("position_closes")

        return realized_pnl, "OK"

    async def allocate_for_trade(
        self,
        symbol: str,
        exchange: str,
        price: float,
        stop_loss_price: Optional[float] = None,
        confidence: float = 0.5,
        volatility: float = 0.02,
    ) -> AllocationResult:
        if not self.capital_allocator or not self.portfolio:
            raise RuntimeError("Portfolio or allocator not initialized")

        return self.capital_allocator.allocate_for_trade(
            symbol=symbol,
            exchange=exchange,
            capital=self.portfolio.current_capital,
            price=price,
            stop_loss_price=stop_loss_price,
            confidence=confidence,
            volatility=volatility,
            used_margin=self.portfolio.total_margin,
        )

    async def calculate_exposure(self) -> Dict[str, float]:
        if not self.portfolio:
            return {}

        total_exposure = 0.0
        by_symbol: Dict[str, float] = {}
        net_exposure = 0.0

        for position in self.portfolio.positions.values():
            exposure = position.notional_value
            total_exposure += abs(exposure)
            by_symbol[position.symbol] = exposure

            if position.side == "long":
                net_exposure += exposure
            else:
                net_exposure -= exposure

        return {
            "total": total_exposure,
            "net": net_exposure,
            "by_symbol": by_symbol,
            "leverage": total_exposure / self.portfolio.equity if self.portfolio.equity > 0 else 0.0,
        }

    async def check_risk(self) -> Dict[str, Any]:
        if not self.portfolio:
            return {"status": "no_portfolio"}

        exposure = await self.calculate_exposure()
        alerts = []

        if exposure["leverage"] > self.config.max_leverage:
            alert = {
                "type": "leverage_limit",
                "severity": "critical",
                "message": f"Leverage {exposure['leverage']:.2f} exceeds limit {self.config.max_leverage}",
                "timestamp": _utcnow().isoformat(),
            }
            alerts.append(alert)
            self.risk_alerts.append(alert)
            logger.critical(alert["message"])

        if exposure["total"] > self.config.max_total_exposure * self.portfolio.equity:
            alert = {
                "type": "total_exposure",
                "severity": "high",
                "message": f"Total exposure {exposure['total']:.2f} exceeds limit",
                "timestamp": _utcnow().isoformat(),
            }
            alerts.append(alert)
            self.risk_alerts.append(alert)
            logger.warning(alert["message"])

        for symbol, exp in exposure["by_symbol"].items():
            if exp > self.config.max_single_symbol_exposure * self.portfolio.equity:
                alert = {
                    "type": "single_exposure",
                    "severity": "high",
                    "symbol": symbol,
                    "message": f"Single symbol {symbol} exposure {exp:.2f} exceeds limit",
                    "timestamp": _utcnow().isoformat(),
                }
                alerts.append(alert)
                self.risk_alerts.append(alert)
                logger.warning(alert["message"])

        status = "ok" if not alerts else "alerts"

        return {
            "status": status,
            "exposure": exposure,
            "alerts": alerts,
            "portfolio_value": self.portfolio.equity,
            "timestamp": _utcnow().isoformat(),
        }

    async def allocate_capital(self, signals: List[Signal]) -> Dict[str, float]:
        if not self.portfolio:
            return {}

        allocations: Dict[str, float] = {}
        active_signals = [s for s in signals if s.is_active()]

        if not active_signals:
            return allocations

        total_weight = sum(s.confidence.value * s.strength.magnitude for s in active_signals)

        if total_weight <= 0:
            return allocations

        available_capital = self.portfolio.equity * self.config.max_total_exposure

        for signal in active_signals:
            weight = (signal.confidence.value * signal.strength.magnitude) / total_weight
            allocation = available_capital * weight
            allocations[signal.symbol] = allocations.get(signal.symbol, 0.0) + allocation

        for symbol in allocations:
            max_alloc = self.portfolio.equity * self.config.max_single_symbol_exposure
            allocations[symbol] = min(allocations[symbol], max_alloc)

        self.metrics.increment("capital_allocations")
        return allocations

    async def detect_conflicts(self, signals: List[Signal]) -> List[Dict[str, Any]]:
        conflicts = []
        by_symbol: Dict[str, List[Signal]] = {}
        for signal in signals:
            if signal.symbol not in by_symbol:
                by_symbol[signal.symbol] = []
            by_symbol[signal.symbol].append(signal)

        for symbol, symbol_signals in by_symbol.items():
            longs = [s for s in symbol_signals if s.direction.value == "long" and s.is_active()]
            shorts = [s for s in symbol_signals if s.direction.value == "short" and s.is_active()]

            if longs and shorts:
                conflicts.append({
                    "type": "direction_conflict",
                    "symbol": symbol,
                    "long_signals": [str(s.signal_id) for s in longs],
                    "short_signals": [str(s.signal_id) for s in shorts],
                    "timestamp": _utcnow().isoformat(),
                })

        return conflicts

    def get_state(self) -> Dict[str, Any]:
        if self.portfolio:
            positions = []
            for pos in self.portfolio.positions.values():
                if hasattr(pos, 'to_dict'):
                    positions.append(pos.to_dict())
                elif isinstance(pos, dict):
                    positions.append(pos)
            accounts = {}
            if hasattr(self.portfolio, 'portfolio_id'):
                accounts[self.portfolio.portfolio_id] = {
                    "balance": getattr(self.portfolio, 'equity', 0),
                    "unrealized_pnl": getattr(self.portfolio, 'total_unrealized_pnl', 0),
                    "available_balance": getattr(self.portfolio, 'available_capital', 0),
                    "margin_balance": getattr(self.portfolio, 'total_margin', 0),
                    "positions_count": len(self.portfolio.positions),
                }
            exposure = {}
            if self.exposure_manager:
                exposure = self.exposure_manager.to_dict()
            self._state = {
                "positions": positions,
                "accounts": accounts,
                "exposure": exposure,
                "total_pnl": getattr(self.portfolio, 'total_pnl', 0),
                "total_value": getattr(self.portfolio, 'total_value', 0),
                "equity": getattr(self.portfolio, 'equity', 0),
            }
        return self._state

    async def snapshot(self) -> Dict[str, Any]:
        ts = now_ms()
        return {
            "name": self.config.name,
            "state": self.state.value,
            "timestamp": ts,
            "business_state": self.get_state(),
        }

    async def recover(self, checkpoint: Any = None) -> None:
        await super().recover(checkpoint)
        if not isinstance(checkpoint, dict):
            return
        business_state = checkpoint.get("business_state")
        if business_state and self.portfolio:
            equity = business_state.get("equity")
            if equity is not None:
                self.portfolio.current_capital = equity
                self.portfolio.available_capital = equity
            total_pnl = business_state.get("total_pnl")
            if total_pnl is not None:
                self.portfolio.total_pnl = total_pnl
            self._state = business_state

    async def get_portfolio_metrics(self):
        if self.portfolio:
            return self.portfolio.get_metrics()
        return None

    async def get_exposure_summary(self) -> Dict[str, Any]:
        if self.exposure_manager:
            return self.exposure_manager.to_dict()
        return {}

    async def get_exposure_warnings(self) -> List[Dict[str, Any]]:
        if self.exposure_manager and self.portfolio:
            return self.exposure_manager.get_exposure_warnings(self.portfolio.current_capital)
        return []

    async def get_risk_budget(self, daily_pnl: float = 0.0) -> Dict[str, float]:
        if self.capital_allocator and self.portfolio:
            return self.capital_allocator.calculate_risk_budget(
                capital=self.portfolio.current_capital,
                daily_pnl=daily_pnl,
            )
        return {}

    async def pause(self) -> None:
        from domain.portfolio.pnl import PortfolioState
        if self.portfolio:
            self.portfolio.state = PortfolioState.PAUSED

    async def resume(self) -> None:
        from domain.portfolio.pnl import PortfolioState
        if self.portfolio:
            self.portfolio.state = PortfolioState.ACTIVE

    async def run(self) -> None:
        logger.info("Starting Portfolio Runtime main loop...")

        await self.lifecycle.transition_to_running()

        last_risk_check = _utcnow()

        while not self.context.is_shutdown_requested():
            try:
                now = _utcnow()

                if (now - last_risk_check).total_seconds() >= self.config.risk_check_interval_seconds:
                    await self.check_risk()
                    last_risk_check = now

                if self.signal_registry:
                    self.signal_registry.cleanup_expired()

                await asyncio.sleep(self.config.update_interval_seconds)

            except Exception as e:
                logger.error(f"Error in portfolio runtime loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)

    async def shutdown(self) -> None:
        logger.info("Shutting down Portfolio Runtime...")
        logger.info(f"Portfolio Runtime stopped. Stats: {self.metrics.to_dict()}")

    async def health_check(self) -> Dict[str, Any]:
        base_health = await super().health_check()

        exposure = await self.calculate_exposure() if self.portfolio else {}

        base_health.update({
            "portfolio_loaded": self.portfolio is not None,
            "exposure": exposure,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "risk_alerts_count": len(self.risk_alerts),
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
        })

        return base_health


_portfolio_runtime: Optional[PortfolioRuntime] = None


def get_portfolio_runtime() -> PortfolioRuntime:
    global _portfolio_runtime
    if _portfolio_runtime is None:
        _portfolio_runtime = PortfolioRuntime()
    return _portfolio_runtime


async def main():
    print("=" * 60)
    print("Portfolio Runtime - Real-time Portfolio Management")
    print("=" * 60)

    runtime = get_portfolio_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
