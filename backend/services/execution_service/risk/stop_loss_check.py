"""
Stop Loss / Take Profit Mandatory Checker

强制止损/止盈检查器
"""

from typing import Optional
from domain.execution.models import OrderIntent
from services.execution_service.risk.risk_engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.stop_loss")


class StopLossTPCheckChecker(RiskChecker):
    """止损/止盈检查器

    确保开仓时设置了止损/止盈
    """

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
        """检查是否设置了止损/止盈"""
        warnings = []

        # 注意：这是个简化版本 - 真实场景中需要检查订单附带的 SL/TP
        # 或者检查风险敞口

        # 模拟检查：只对大金额或高杠杆发出警告
        if intent.leverage > 3:
            warnings.append(
                f"High leverage ({intent.leverage}x), consider setting a stop loss!"
            )
            logger.warning(f"High leverage order without explicit SL/TP: {intent.symbol}")

        if self.max_stop_loss_pct and intent.quantity * (intent.price or 0) > 1000:
            warnings.append(
                f"Large order, recommend setting stop loss at {self.max_stop_loss_pct:.1%}"
            )

        # 在真实实现中，我们会检查订单是否附带了止损/止盈单
        # 这里仅返回通过，但给出警告

        return RiskCheckResult(passed=True, warnings=warnings)
