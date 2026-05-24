from typing import Optional

from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.leverage_limit")


class LeverageLimitChecker(RiskChecker):

    def __init__(
        self,
        max_leverage: int = 10,
        warning_leverage: int = 5,
    ):
        self.max_leverage = max_leverage
        self.warning_leverage = warning_leverage

    @property
    def name(self) -> str:
        return "LeverageLimitChecker"

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        warnings = []

        if intent.max_leverage > self.max_leverage:
            return RiskCheckResult(
                passed=False,
                reason=f"Leverage {intent.max_leverage}x exceeds maximum {self.max_leverage}x",
            )

        if intent.max_leverage > self.warning_leverage:
            warnings.append(
                f"High leverage {intent.max_leverage}x (warning threshold: {self.warning_leverage}x)"
            )

        return RiskCheckResult(passed=True, warnings=warnings)
