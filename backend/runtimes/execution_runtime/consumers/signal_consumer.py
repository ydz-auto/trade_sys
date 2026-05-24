from typing import Dict, Any, Optional
import uuid

from domain.execution.models import (
    OrderIntent,
    OrderSide,
    Exchange,
    MarketType,
)
from runtimes.execution_runtime.engine.execution_engine import ExecutionEngine, get_execution_engine
from engines.compute.risk.engine import RiskEngine
from infrastructure.logging import get_logger

logger = get_logger("execution_service.consumers.signal")


class SignalConsumer:

    def __init__(
        self,
        execution_engine: ExecutionEngine = None,
        risk_engine: RiskEngine = None,
        default_exchange: Exchange = Exchange.BINANCE,
        default_market_type: MarketType = MarketType.SPOT,
    ):
        self._engine = execution_engine or get_execution_engine()
        self._risk_engine = risk_engine
        self._default_exchange = default_exchange
        self._default_market_type = default_market_type

    def _parse_action(self, action: str) -> Optional[OrderSide]:
        action = action.upper()
        if action in ["LONG", "BUY"]:
            return OrderSide.BUY
        elif action in ["SHORT", "SELL"]:
            return OrderSide.SELL
        elif action in ["HOLD", "CLOSE"]:
            return None
        return None

    def _create_intent(self, signal: Dict[str, Any]) -> Optional[OrderIntent]:
        action = signal.get("action", signal.get("signal", "HOLD"))
        side = self._parse_action(action)

        if side is None:
            logger.info(f"Signal action {action} does not require order")
            return None

        assets = signal.get("assets", [])
        symbol = assets[0] if assets else signal.get("symbol", "BTC/USDT")
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"

        quantity = signal.get("quantity", signal.get("size", 0.001))
        confidence = signal.get("confidence", 0.5)

        exchange_str = signal.get("exchange", "binance").lower()
        exchange = Exchange.BINANCE if exchange_str == "binance" else Exchange(exchange_str)

        market_type_str = signal.get("market_type", "spot").lower()
        market_type = MarketType(market_type_str) if market_type_str in [m.value for m in MarketType] else MarketType.SPOT

        intent = OrderIntent(
            intent_id=f"intent_{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            exchange=exchange,
            market_type=market_type,
            signal_id=signal.get("signal_id"),
            strategy_id=signal.get("strategy_id"),
            confidence=confidence,
            max_leverage=signal.get("leverage", 1),
            stop_loss_pct=signal.get("stop_loss_pct"),
            take_profit_pct=signal.get("take_profit_pct"),
        )

        return intent

    async def process_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Processing signal: {signal.get('action')} {signal.get('symbol', signal.get('assets', ['?'])[0])}")

        intent = self._create_intent(signal)
        if intent is None:
            return {
                "status": "skipped",
                "reason": "No order required for this signal",
            }

        if self._risk_engine:
            risk_result = await self._risk_engine.validate(intent)
            if not risk_result.passed:
                logger.warning(f"Risk check failed: {risk_result.reason}")
                return {
                    "status": "rejected",
                    "reason": risk_result.reason,
                    "warnings": risk_result.warnings,
                }
            if risk_result.warnings:
                logger.info(f"Risk warnings: {risk_result.warnings}")

        result = await self._engine.execute_intent(intent)

        if result.success:
            return {
                "status": "success",
                "order_id": result.order.order_id,
                "symbol": result.order.symbol,
                "side": result.order.side.value,
                "quantity": result.order.quantity,
                "status": result.order.status.value,
            }
        else:
            return {
                "status": "error",
                "reason": result.error,
            }
