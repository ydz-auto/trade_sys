"""
Risk Service - 业务逻辑处理器

业务逻辑：风控检查、风险评估
"""

from datetime import datetime
from typing import Dict, Any, Optional

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.decision import Decision, RiskCheckedDecision
from services.risk_service.risk_engine import (
    RiskService,
    RiskCheckResult,
    RiskConfig,
    TradeRisk,
)

logger = get_logger("risk_service.handlers")


class RiskHandler:
    """风控处理器 - 纯业务逻辑"""

    def __init__(self, config: Optional[RiskConfig] = None):
        config = config or RiskConfig(
            max_position_size=0.2,
            max_single_loss=0.02,
            max_daily_loss=0.05,
            max_drawdown=0.15,
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
        )
        self.risk_service = RiskService(config)

    def perform_risk_check(self, decision: Decision) -> RiskCheckedDecision:
        """
        执行风控检查

        Args:
            decision: 原始决策

        Returns:
            风控检查后的决策
        """
        if not self.risk_service:
            return RiskCheckedDecision(
                decision_id=decision.decision_id,
                approved=True,
                reason="Risk service not initialized",
                risk_level="medium",
                original_decision=decision,
                check_results={"status": "bypassed"},
            )

        estimated_value = decision.quantity * (decision.price or 1.0)
        trade_risk = TradeRisk(
            symbol=decision.symbol,
            side="buy" if decision.is_buy else "sell" if decision.is_sell else "hold",
            quantity=decision.quantity,
            price=decision.price or 0.0,
            estimated_value=estimated_value,
            estimated_loss=estimated_value * 0.02,
            risk_level="low",
            stop_loss=decision.price * 0.98 if decision.price else 0,
            take_profit=decision.price * 1.02 if decision.price else 0,
        )

        result = self.risk_service.check_trade(trade_risk)

        approved = result.check_result == RiskCheckResult.PASSED

        return RiskCheckedDecision(
            decision_id=decision.decision_id,
            approved=approved,
            reason=result.rejected_reason,
            risk_level=result.risk_level,
            original_decision=decision,
            check_results={
                "check_result": result.check_result.value,
                "risk_level": result.risk_level,
                "warnings": result.warnings,
                "metrics": result.metrics,
            },
            metadata={
                "position_risks": [
                    {
                        "symbol": pr.symbol,
                        "unrealized_pnl": pr.unrealized_pnl,
                    }
                    for pr in result.position_risks
                ],
            },
        )

    def process_decision(self, msg: Dict[str, Any]) -> Optional[RiskCheckedDecision]:
        """
        处理策略决策，执行风控检查

        Args:
            msg: 原始决策消息

        Returns:
            RiskCheckedDecision 或 None
        """
        try:
            decision = Decision(**msg) if isinstance(msg, dict) else msg
            logger.info(f"Processing decision: {decision.action} on {decision.symbol}")

            checked_decision = self.perform_risk_check(decision)
            logger.info(f"Risk check result: approved={checked_decision.approved}")

            return checked_decision

        except Exception as e:
            logger.error(f"Error processing decision: {e}")
            return None


def get_risk_handler(config: Optional[RiskConfig] = None) -> RiskHandler:
    """获取风控处理器实例"""
    return RiskHandler(config=config)
