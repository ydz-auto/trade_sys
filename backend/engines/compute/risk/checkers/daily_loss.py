from datetime import datetime, timedelta
from typing import Optional
from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.daily_loss")


class DailyLossLimitChecker(RiskChecker):

    def __init__(self, max_daily_loss_pct: float = 0.1, initial_capital: float = 10000.0):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.initial_capital = initial_capital
        self._daily_pnl: float = 0.0
        self._last_reset_date: str = datetime.now().strftime("%Y-%m-%d")

    @property
    def name(self) -> str:
        return "DailyLossLimitChecker"

    def _reset_daily_counter(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._daily_pnl = 0.0
            self._last_reset_date = today
            logger.info("Daily PnL counter reset")

    def record_pnl(self, pnl: float):
        self._daily_pnl += pnl
        logger.info(f"Daily PnL updated: {self._daily_pnl:.2f}")

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        self._reset_daily_counter()

        max_loss = self.initial_capital * self.max_daily_loss_pct
        current_loss = -self._daily_pnl

        if current_loss >= max_loss:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily loss limit reached: {current_loss:.2f} > {max_loss:.2f}",
            )

        warnings = []
        if current_loss >= max_loss * 0.8:
            warnings.append(
                f"Warning: Daily loss at {current_loss/max_loss*100:.1f}% of limit"
            )

        return RiskCheckResult(passed=True, warnings=warnings)
