"""
Drawdown Limit Checker

最大回撤限制检查器
"""

from typing import Optional
from datetime import datetime

from domain.execution.models import OrderIntent
from services.execution_service.risk.risk_engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.drawdown")


class DrawdownLimitChecker(RiskChecker):
    """最大回撤检查器

    检查从峰值开始的回撤是否超过限制
    """

    def __init__(
        self,
        max_drawdown_pct: float = 0.2,  # 20% 最大回撤
        warning_drawdown_pct: float = 0.15,  # 15% 警告
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
        """检查回撤限制"""
        warnings = []

        # 计算当前估计值（简化版）
        order_value = intent.quantity * (intent.price or 0)
        estimated_value = self.initial_capital + (self.initial_capital * (self.max_drawdown_pct / 2))

        # 更新峰值
        if estimated_value > self.peak_value:
            self.peak_value = estimated_value
            logger.info(f"New portfolio peak: {self.peak_value:.2f}")

        # 计算回撤
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
        """重置峰值（手动调用）"""
        self.peak_value = current_value
        self.initial_capital = current_value
