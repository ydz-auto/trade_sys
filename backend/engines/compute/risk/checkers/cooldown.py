from datetime import datetime, timedelta
from typing import Optional, Dict
from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.cooldown")


class CooldownChecker(RiskChecker):

    def __init__(
        self,
        default_cooldown_seconds: int = 300,
        cooldown_configs: Optional[Dict[str, int]] = None,
    ):
        self.default_cooldown = default_cooldown_seconds
        self.cooldown_configs = cooldown_configs or {}
        self._last_trades: Dict[str, datetime] = {}

    @property
    def name(self) -> str:
        return "CooldownChecker"

    def record_trade(self, symbol: str):
        self._last_trades[symbol] = datetime.now()
        logger.info(f"Recorded trade for {symbol}")

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        symbol = intent.symbol

        if symbol not in self._last_trades:
            return RiskCheckResult(passed=True)

        cooldown = self.cooldown_configs.get(symbol, self.default_cooldown)
        last_trade = self._last_trades[symbol]
        elapsed = (datetime.now() - last_trade).total_seconds()

        if elapsed < cooldown:
            remaining = cooldown - elapsed
            return RiskCheckResult(
                passed=False,
                reason=f"{symbol} in cooldown period, {remaining:.1f}s remaining",
            )

        return RiskCheckResult(passed=True)
