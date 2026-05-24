from typing import Optional
from datetime import datetime

from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.drawdown")


class DrawdownLimitChecker(RiskChecker):

    def __init__(
        self,
        max_drawdown_pct: float = 0.2,
        warning_drawdown_pct: float = 0.15,
        initial_capital: float = 10000.0,
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.warning_drawdown_pct = warning_drawdown_pct
        self.initial_capital = initial_capital
        self.peak_value = initial_capital
        self.last_check = datetime.now()

    @property
    def name(self) -> str:
        return "DrawdownLimitChecker"

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        warnings = []

        order_value = intent.quantity * (intent.price or 0)
        estimated_value = self.initial_capital + (self.initial_capital * (self.max_drawdown_pct / 2))

        if estimated_value > self.peak_value:
            self.peak_value = estimated_value
            logger.info(f"New portfolio peak: {self.peak_value:.2f}")

        drawdown = (self.peak_value - estimated_value) / self.peak_value if self.peak_value > 0 else 0

        if drawdown >= self.max_drawdown_pct:
            logger.error(f"Drawdown limit reached: {drawdown:.1%} (max: {self.max_drawdown_pct:.1%})")
            return RiskCheckResult(
                passed=False,
                reason=f"Max drawdown {drawdown:.1%} exceeds limit {self.max_drawdown_pct:.1%}",
            )

        if drawdown >= self.warning_drawdown_pct:
            warnings.append(
                f"Drawdown warning: {drawdown:.1%} (warning: {self.warning_drawdown_pct:.1%})"
            )
            logger.warning(f"Drawdown warning: {drawdown:.1%}")

        return RiskCheckResult(passed=True, warnings=warnings)

    async def reset(self, current_value: float):
        self.peak_value = current_value
        self.initial_capital = current_value
