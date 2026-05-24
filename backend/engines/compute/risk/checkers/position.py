from typing import Optional

from domain.execution.models import OrderIntent, Exchange
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from domain.execution.position_reader import PositionReader
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.position_limit")


class PositionLimitChecker(RiskChecker):

    def __init__(
        self,
        position_repository: PositionReader = None,
        max_position_value: float = 10000.0,
        max_position_count: int = 10,
        max_single_position_pct: float = 0.3,
    ):
        self._position_repository = position_repository
        self.max_position_value = max_position_value
        self.max_position_count = max_position_count
        self.max_single_position_pct = max_single_position_pct

    @property
    def name(self) -> str:
        return "PositionLimitChecker"

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        warnings = []

        if self._position_repository:
            positions = await self._position_repository.get_all()
            total_value = await self._position_repository.get_total_position_value()
            position_count = await self._position_repository.get_position_count()

            if total_value > self.max_position_value:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Total position value {total_value:.2f} exceeds limit {self.max_position_value}",
                )

            if position_count >= self.max_position_count:
                has_position = await self._position_repository.has_position(
                    intent.symbol,
                    intent.exchange,
                    intent.market_type,
                )
                if not has_position:
                    return RiskCheckResult(
                        passed=False,
                        reason=f"Position count {position_count} exceeds limit {self.max_position_count}",
                    )

            if intent.max_position_value > 0:
                single_position_pct = intent.quantity * intent.max_position_value / self.max_position_value
                if single_position_pct > self.max_single_position_pct:
                    warnings.append(
                        f"Single position {single_position_pct:.1%} exceeds recommended {self.max_single_position_pct:.1%}"
                    )

        if intent.max_position_value > self.max_position_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Order position value {intent.max_position_value} exceeds limit {self.max_position_value}",
            )

        return RiskCheckResult(passed=True, warnings=warnings)
