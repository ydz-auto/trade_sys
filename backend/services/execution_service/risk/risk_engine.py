"""
Risk Engine

风控引擎
"""

from typing import List, Optional, Callable
from dataclasses import dataclass

from domain.execution.models import OrderIntent, OrderRequest
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.engine")


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    passed: bool
    reason: str = ""
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class RiskChecker:
    """风控检查器基类"""

    @property
    def name(self) -> str:
        """检查器名称"""
        return self.__class__.__name__

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        """执行检查"""
        raise NotImplementedError


class RiskEngine:
    """风控引擎

    执行订单前的风控检查
    """

    def __init__(self):
        self._checkers: List[RiskChecker] = []
        self._warnings: List[str] = []

    @property
    def checkers(self) -> List[RiskChecker]:
        """获取所有已注册的检查器"""
        return self._checkers.copy()

    def register_checker(self, checker: RiskChecker) -> None:
        """注册检查器"""
        self._checkers.append(checker)
        logger.info(f"Registered risk checker: {checker.name}")

    def remove_checker(self, checker_name: str) -> None:
        """移除检查器"""
        self._checkers = [c for c in self._checkers if c.name != checker_name]

    async def validate(self, intent: OrderIntent) -> RiskCheckResult:
        """验证订单意图

        执行所有注册的检查器
        """
        all_warnings = []
        errors = []

        for checker in self._checkers:
            try:
                result = await checker.check(intent)
                if not result.passed:
                    errors.append(f"[{checker.name}] {result.reason}")
                all_warnings.extend(result.warnings)
            except Exception as e:
                logger.error(f"Risk checker {checker.name} failed: {e}")
                errors.append(f"[{checker.name}] Check failed: {str(e)}")

        if errors:
            return RiskCheckResult(
                passed=False,
                reason="; ".join(errors),
                warnings=all_warnings,
            )

        return RiskCheckResult(
            passed=True,
            warnings=all_warnings,
        )

    async def check_order_request(self, request: OrderRequest) -> RiskCheckResult:
        """检查订单请求"""
        intent = OrderIntent(
            intent_id=f"check_{request.symbol}",
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            exchange=request.exchange,
            market_type=request.market_type,
            max_leverage=request.leverage,
        )
        return await self.validate(intent)

    def get_warnings(self) -> List[str]:
        """获取警告列表"""
        return self._warnings.copy()

    def clear_warnings(self) -> None:
        """清除警告"""
        self._warnings.clear()
