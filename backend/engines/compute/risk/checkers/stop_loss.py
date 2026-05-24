from typing import Optional
from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.stop_loss")


class StopLossTPCheckChecker(RiskChecker):

    def __init__(
        self,
        require_stop_loss: bool = True,
        require_take_profit: bool = False,
        max_stop_loss_pct: Optional[float] = None,
    ):
        self.require_stop_loss = require_stop_loss
        self.require_take_profit = require_take_profit
        self.max_stop_loss_pct = max_stop_loss_pct

    @property
    def name(self) -> str:
        return "StopLossTPCheckChecker"

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        warnings = []

        if intent.leverage > 3:
            warnings.append(
                f"High leverage ({intent.leverage}x), consider setting a stop loss!"
            )
            logger.warning(f"High leverage order without explicit SL/TP: {intent.symbol}")

        if self.max_stop_loss_pct and intent.quantity * (intent.price or 0) > 1000:
            warnings.append(
                f"Large order, recommend setting stop loss at {self.max_stop_loss_pct:.1%}"
            )

        return RiskCheckResult(passed=True, warnings=warnings)
