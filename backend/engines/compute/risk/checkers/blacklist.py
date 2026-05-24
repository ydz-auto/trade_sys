from typing import List, Set, Optional
from domain.execution.models import OrderIntent
from engines.compute.risk.engine import RiskChecker, RiskCheckResult
from infrastructure.logging import get_logger

logger = get_logger("execution_service.risk.blacklist")


class SymbolBlacklistChecker(RiskChecker):

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
        self.blacklist.add(symbol.upper())
        logger.info(f"Added to blacklist: {symbol}")

    def remove_from_blacklist(self, symbol: str):
        self.blacklist.discard(symbol.upper())
        logger.info(f"Removed from blacklist: {symbol}")

    def add_to_whitelist(self, symbol: str):
        self.whitelist.add(symbol.upper())
        logger.info(f"Added to whitelist: {symbol}")

    async def check(self, intent: OrderIntent) -> RiskCheckResult:
        symbol = intent.symbol.upper()

        if self.whitelist:
            if symbol not in self.whitelist:
                logger.warning(f"Symbol {symbol} not in whitelist")
                return RiskCheckResult(
                    passed=False,
                    reason=f"Symbol {symbol} not in whitelist",
                )

        if symbol in self.blacklist:
            logger.warning(f"Symbol {symbol} is blacklisted")
            return RiskCheckResult(
                passed=False,
                reason=f"Symbol {symbol} is blacklisted",
            )

        return RiskCheckResult(passed=True)
