"""
Strategy Service - 业务逻辑处理器

业务逻辑：策略信号转换、决策生成
"""

from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Optional

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.signal import Signal
from infrastructure.messaging.schema.decision import Decision
from services.strategy_service.strategies import (
    create_default_strategies,
    StrategySignal,
    ActionType,
)

logger = get_logger("strategy_service.handlers")


class StrategyHandler:
    """策略处理器 - 纯业务逻辑"""

    def __init__(self):
        self.strategy_orchestrator = create_default_strategies()

    def convert_strategy_signals(
        self,
        signals: List[StrategySignal],
        fusion_signal: Signal,
    ) -> Decision:
        """
        将策略信号转换为决策

        Args:
            signals: 策略信号列表
            fusion_signal: 原始融合信号

        Returns:
            Decision
        """
        if not signals:
            return Decision(
                decision_id=f"dec_{int(datetime.now().timestamp() * 1000)}",
                action="HOLD",
                symbol=fusion_signal.assets[0] if fusion_signal.assets else "BTCUSDT",
                quantity=0.0,
                price=None,
                confidence=0.0,
                reason="无策略信号",
                source="strategy_service",
                timestamp=int(datetime.now().timestamp() * 1000),
                metadata={},
            )

        direction_votes = defaultdict(float)
        total_confidence = 0.0

        for sig in signals:
            weight = sig.confidence
            direction_votes[sig.action] += weight
            total_confidence += weight

        if not direction_votes:
            action = "HOLD"
        else:
            sorted_directions = sorted(
                direction_votes.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            dominant_action = sorted_directions[0][0]
            confidence = sorted_directions[0][1] / max(total_confidence, 0.001)

            if dominant_action == ActionType.LONG:
                action = "LONG"
            elif dominant_action == ActionType.SHORT:
                action = "SHORT"
            else:
                action = "HOLD"

        first_sig = signals[0]

        return Decision(
            decision_id=f"dec_{int(datetime.now().timestamp() * 1000)}",
            action=action,
            symbol=first_sig.symbol,
            quantity=first_sig.quantity,
            price=first_sig.price,
            confidence=min(1.0, confidence),
            reason=f"策略一致: {', '.join([s.reason for s in signals])}",
            source="strategy_service",
            timestamp=int(datetime.now().timestamp() * 1000),
            metadata={
                "signal_count": len(signals),
                "strategies": [s.strategy_id for s in signals],
                "fusion_signal": {
                    "direction": fusion_signal.direction,
                    "confidence": fusion_signal.confidence,
                    "event_count": fusion_signal.event_count,
                },
            },
        )

    def generate_simple_decision(self, signal: Signal) -> Decision:
        """
        生成简单决策（基于融合信号）

        当策略引擎没有可用数据时使用
        """
        confidence = signal.confidence

        if confidence < 0.1:
            action = "HOLD"
            quantity = 0.0
            reason = "信号模糊"
        elif signal.direction == "bullish":
            action = "LONG"
            quantity = min(confidence * 0.08, 0.1)
            reason = f"信号看涨，置信度 {confidence:.3f}"
        elif signal.direction == "bearish":
            action = "SHORT"
            quantity = min(confidence * 0.08, 0.1)
            reason = f"信号看跌，置信度 {confidence:.3f}"
        else:
            action = "HOLD"
            quantity = 0.0
            reason = "中性信号"

        return Decision(
            decision_id=f"dec_{int(datetime.now().timestamp() * 1000)}",
            action=action,
            symbol=signal.assets[0] if signal.assets else "BTCUSDT",
            quantity=quantity,
            price=None,
            confidence=confidence,
            reason=reason,
            source="strategy_service",
            timestamp=int(datetime.now().timestamp() * 1000),
            metadata={"fusion_signal": signal.model_dump()},
        )

    def process_signal(self, msg: Dict[str, Any]) -> Optional[Decision]:
        """
        处理融合信号，生成决策

        Args:
            msg: 原始信号消息

        Returns:
            Decision 或 None
        """
        try:
            signal = Signal(**msg) if isinstance(msg, dict) else msg
            symbol = signal.assets[0] if signal.assets else "BTCUSDT"

            logger.info(f"Processing signal: {signal.signal} confidence={signal.confidence:.3f}")

            strategy_signals = []
            if self.strategy_orchestrator:
                strategy_signals = self.strategy_orchestrator.process()

            if strategy_signals:
                decision = self.convert_strategy_signals(strategy_signals, signal)
            else:
                decision = self.generate_simple_decision(signal)

            logger.info(f"Decision: {decision.action} {decision.symbol} confidence={decision.confidence:.3f}")

            return decision

        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            return None


def get_strategy_handler() -> StrategyHandler:
    """获取策略处理器实例"""
    return StrategyHandler()
