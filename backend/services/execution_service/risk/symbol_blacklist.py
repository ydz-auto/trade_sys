"""
Symbol Blacklist Checker

交易对黑名单检查器
"""

from typing import List, Set, Optional
from domain.execution.models import OrderIntent
from services.execution_service.risk.risk_engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.blacklist")


class SymbolBlacklistChecker(RiskChecker):
    """交易对黑名单检查器

    禁止交易特定的交易对
    """

    def __init__(
        self,
        blacklist: Optional[List[str]] = None,
        whitelist: Optional[List[str]] = None,
    ):
        self.blacklist: Set[str] = set(blacklist or [])
        self.whitelist: Set[str] = set(whitelist or [])

    @property
    def name(self) -> str:
        return "SymbolBlacklistChecker"

    def add_to_blacklist(self, symbol: str):
        """添加到黑名单"""
        self.blacklist.add(symbol.upper())
        logger.info(f"Added to blacklist: {symbol}")

    def remove_from_blacklist(self, symbol: str):
        """从黑名单移除"""
        self.blacklist.discard(symbol.upper())
        logger.info(f"Removed from blacklist: {symbol}")

    def add_to_whitelist(self, symbol: str):
        """添加到白名单"""
        self.whitelist.add(symbol.upper())
        logger.info(f"Added to whitelist: {symbol}")

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        """检查交易对是否允许"""
        symbol = intent.symbol.upper()

        # 检查白名单优先
        if self.whitelist:
            if symbol not in self.whitelist:
                logger.warning(f"Symbol {symbol} not in whitelist")
                return RiskCheckResult(
                    passed=False,
                    reason=f"Symbol {symbol} not in whitelist",
                )

        # 检查黑名单
        if symbol in self.blacklist:
            logger.warning(f"Symbol {symbol} is blacklisted")
            return RiskCheckResult(
                passed=False,
                reason=f"Symbol {symbol} is blacklisted",
            )

        return RiskCheckResult(passed=True)
