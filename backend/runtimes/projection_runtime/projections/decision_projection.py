import json
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict

from .base import BaseProjection
from ..state_keys import ProjectionKeys, ProjectionChannels
from infrastructure.messaging.topics import Topics


class DecisionProjection(BaseProjection):
    def __init__(self):
        super().__init__("decision")

        self._latest_decisions: Dict[str, Dict[str, Any]] = {}
        self._decision_history: List[Dict[str, Any]] = []
        self._decision_stats = {
            "total": 0,
            "long": 0,
            "short": 0,
            "hold": 0,
            "approved": 0,
            "rejected": 0,
            "avg_confidence": 0.0,
        }
        self._confidence_sum = 0.0

    @property
    def topics(self) -> List[str]:
        return [
            Topics.DECISIONS,
            Topics.decisions_risk_checked(),
        ]

    async def initialize(self) -> None:
        await super().initialize()

        latest = await self.get_redis(ProjectionKeys.decision_latest())
        if latest:
            self._latest_decisions = latest

        self.logger.info("Decision projection initialized")

    async def process_event(self, event: Dict[str, Any]) -> None:
        self.record_event()

        event_type = event.get("event_type", "")

        try:
            if event_type == "decision":
                await self._process_decision(event)
            elif event_type == "risk_checked":
                await self._process_risk_checked(event)

        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self._stats.errors += 1

    async def _process_decision(self, event: Dict[str, Any]) -> None:
        symbol = event.get("symbol", "BTC")
        decision_id = event.get("decision_id", event.get("event_id", ""))
        action = event.get("action", "HOLD").upper()
        confidence = event.get("confidence", 0.0)

        decision = {
            "decision_id": decision_id,
            "trace_id": event.get("trace_id", ""),
            "symbol": symbol,
            "action": action,
            "quantity": event.get("quantity", 0.0),
            "price": event.get("price"),
            "confidence": confidence,
            "reason": event.get("reason", ""),
            "strategy_id": event.get("strategy_id", ""),
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
            "status": "pending",
            "approved": None,
        }

        self._latest_decisions[symbol] = decision

        self._decision_history.insert(0, decision)
        self._decision_history = self._decision_history[:100]

        self._decision_stats["total"] += 1
        self._confidence_sum += confidence

        if self._decision_stats["total"] > 0:
            self._decision_stats["avg_confidence"] = self._confidence_sum / self._decision_stats["total"]

        if action == "LONG":
            self._decision_stats["long"] += 1
        elif action == "SHORT":
            self._decision_stats["short"] += 1
        else:
            self._decision_stats["hold"] += 1

        await self._update_state()

        await self.append_redis_list(
            ProjectionKeys.decision_history(symbol),
            decision,
            max_len=50
        )

        await self.push_websocket(ProjectionChannels.decision(), {
            "type": "new_decision",
            "decision": decision,
        })

        self.logger.info(
            f"Decision: {action} {symbol} @ {confidence:.2f} - {decision.get('reason', '')}"
        )

    async def _process_risk_checked(self, event: Dict[str, Any]) -> None:
        original_decision_id = event.get("original_decision_id", "")
        approved = event.get("approved", False)
        risk_level = event.get("risk_level", "low")
        rejection_reason = event.get("rejection_reason")

        for symbol, decision in self._latest_decisions.items():
            if decision.get("decision_id") == original_decision_id:
                decision["status"] = "approved" if approved else "rejected"
                decision["approved"] = approved
                decision["risk_level"] = risk_level
                if rejection_reason:
                    decision["rejection_reason"] = rejection_reason

                if approved:
                    self._stats["approved"] += 1
                else:
                    self._stats["rejected"] += 1

                break

        for i, decision in enumerate(self._decision_history):
            if decision.get("decision_id") == original_decision_id:
                self._decision_history[i] = self._latest_decisions.get(
                    decision.get("symbol", "BTC"),
                    decision
                )
                break

        await self._update_state()

        await self.push_websocket(ProjectionChannels.decision(), {
            "type": "risk_checked",
            "decision_id": original_decision_id,
            "approved": approved,
            "risk_level": risk_level,
            "rejection_reason": rejection_reason,
        })

    async def _update_state(self) -> None:
        await self.update_redis(ProjectionKeys.decision_latest(), self._latest_decisions)
        await self.update_redis(ProjectionKeys.decision_stats(), self._stats)

    def get_latest_decision(self, symbol: str = None) -> Dict[str, Any]:
        if symbol:
            return self._latest_decisions.get(symbol, {})
        return self._latest_decisions

    def get_history(self, symbol: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        if symbol:
            return [d for d in self._decision_history if d.get("symbol") == symbol][:limit]
        return self._decision_history[:limit]

    def get_stats(self) -> Dict[str, Any]:
        return self._stats
