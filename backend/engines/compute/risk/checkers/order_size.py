from typing import Optional

from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.order_size")


class OrderSizeLimitChecker(RiskChecker):

    def __init__(
        self,
        max_order_value: float = 1000.0,
        max_order_quantity: Optional[float] = None,
        min_order_value: float = 1.0,
    ):
        self.max_order_value = max_order_value
        self.max_order_quantity = max_order_quantity
        self.min_order_value = min_order_value

    @property
    def name(self) -> str:
        return "OrderSizeLimitChecker"

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        warnings = []
        order_value = intent.quantity * (intent.price or 0)

        if order_value < self.min_order_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Order value {order_value:.2f} below min {self.min_order_value:.2f}",
            )

        if order_value > self.max_order_value:
            logger.error(f"Order value limit exceeded: {order_value:.2f} > {self.max_order_value:.2f}")
            return RiskCheckResult(
                passed=False,
                reason=f"Order value {order_value:.2f} exceeds max {self.max_order_value:.2f}",
            )

        if self.max_order_quantity and intent.quantity > self.max_order_quantity:
            logger.error(f"Order quantity limit exceeded: {intent.quantity} > {self.max_order_quantity}")
            return RiskCheckResult(
                passed=False,
                reason=f"Order quantity {intent.quantity} exceeds max {self.max_order_quantity}",
            )

        if order_value > self.max_order_value * 0.8:
            warnings.append(
                f"Order value {order_value:.2f} is {order_value/self.max_order_value:.0%} of max limit"
            )

        logger.info(f"Order size check passed: {order_value:.2f}")
        return RiskCheckResult(passed=True, warnings=warnings)
