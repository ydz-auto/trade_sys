from datetime import datetime, date
from typing import Dict, Any, List
from collections import defaultdict

from .base import BaseProjection
from ..state_keys import ProjectionKeys, ProjectionChannels
from infrastructure.messaging.topics import Topics


class RiskProjection(BaseProjection):
    def __init__(self):
        super().__init__("risk")

        self._risk_state = {
            "level": "low",
            "score": 0,
            "components": {
                "volatility": 0.0,
                "flow": 0.0,
                "sentiment": 0.0,
                "macro": 0.0,
            },
            "warnings": [],
            "last_check": None,
        }

        self._daily_metrics = {
            "date": str(date.today()),
            "trades": 0,
            "approved": 0,
            "rejected": 0,
            "total_volume": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
        }

        self._check_history: List[Dict[str, Any]] = []

        self._risk_counts = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "extreme": 0,
        }

    @property
    def topics(self) -> List[str]:
        return [
            Topics.DECISIONS,
            Topics.decisions_risk_checked(),
            Topics.ORDERS,
            Topics.EVENTS,
        ]

    async def initialize(self) -> None:
        await super().initialize()

        state = await self.get_redis(ProjectionKeys.risk_state())
        if state:
            self._risk_state = state

        metrics = await self.get_redis(ProjectionKeys.risk_daily_metrics())
        if metrics and metrics.get("date") == str(date.today()):
            self._daily_metrics = metrics

        self.logger.info("Risk projection initialized")

    async def process_event(self, event: Dict[str, Any]) -> None:
        self.record_event()

        event_type = event.get("event_type", "")

        try:
            if event_type == "risk_checked":
                await self._process_risk_checked(event)
            elif event_type == "order":
                await self._process_order(event)
            elif event_type == "fill":
                await self._process_fill(event)
            elif event_type == "event":
                await self._process_analysis_event(event)

        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self._stats.errors += 1

    async def _process_risk_checked(self, event: Dict[str, Any]) -> None:
        approved = event.get("approved", False)
        risk_level = event.get("risk_level", "low")
        warnings = event.get("warnings", [])
        check_results = event.get("check_results", {})

        self._daily_metrics["trades"] += 1
        if approved:
            self._daily_metrics["approved"] += 1
        else:
            self._daily_metrics["rejected"] += 1

        self._risk_counts[risk_level] = self._risk_counts.get(risk_level, 0) + 1

        self._risk_state["level"] = self._calculate_overall_risk_level()
        self._risk_state["last_check"] = datetime.utcnow().isoformat()

        if warnings:
            self._risk_state["warnings"] = warnings[-5:]

        check_record = {
            "decision_id": event.get("original_decision_id", ""),
            "symbol": event.get("symbol", ""),
            "approved": approved,
            "risk_level": risk_level,
            "warnings": warnings,
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
        }

        self._check_history.insert(0, check_record)
        self._check_history = self._check_history[:100]

        await self._update_state()

        await self.push_websocket(ProjectionChannels.risk(), {
            "type": "risk_check",
            "approved": approved,
            "risk_level": risk_level,
            "warnings": warnings,
        })

    async def _process_order(self, event: Dict[str, Any]) -> None:
        status = event.get("status", "")
        quantity = event.get("quantity", 0)
        price = event.get("price", 0) or event.get("avg_price", 0)

        if status in ("filled", "partial"):
            volume = quantity * price
            self._daily_metrics["total_volume"] += volume

    async def _process_fill(self, event: Dict[str, Any]) -> None:
        realized_pnl = event.get("realized_pnl", 0) or 0
        self._daily_metrics["total_pnl"] += realized_pnl

        await self._update_state()

    async def _process_analysis_event(self, event: Dict[str, Any]) -> None:
        event_category = event.get("event_category", "")
        direction = event.get("direction", "neutral")
        strength = event.get("strength", 0.5)

        if "risk" in event_category.lower() or "volatility" in event_category.lower():
            if direction == "bearish":
                self._risk_state["components"]["volatility"] = min(
                    1.0, self._risk_state["components"]["volatility"] + strength * 0.1
                )
        elif "flow" in event_category.lower():
            if direction == "bearish":
                self._risk_state["components"]["flow"] = min(
                    1.0, self._risk_state["components"]["flow"] + strength * 0.1
                )
        elif "sentiment" in event_category.lower():
            if direction == "bearish":
                self._risk_state["components"]["sentiment"] = min(
                    1.0, self._risk_state["components"]["sentiment"] + strength * 0.1
                )

        self._risk_state["score"] = self._calculate_risk_score()
        self._risk_state["level"] = self._calculate_overall_risk_level()

    def _calculate_risk_score(self) -> int:
        components = self._risk_state["components"]
        score = (
            components.get("volatility", 0) * 30 +
            components.get("flow", 0) * 25 +
            components.get("sentiment", 0) * 25 +
            components.get("macro", 0) * 20
        )
        return int(score * 100)

    def _calculate_overall_risk_level(self) -> str:
        score = self._risk_state.get("score", 0)

        if score >= 80:
            return "extreme"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"

    async def _update_state(self) -> None:
        await self.update_redis(ProjectionKeys.risk_state(), self._risk_state)
        await self.update_redis(ProjectionKeys.risk_daily_metrics(), self._daily_metrics)
        await self.update_redis(ProjectionKeys.risk_checks(), self._check_history[:20])

    def get_state(self) -> Dict[str, Any]:
        return self._risk_state

    def get_daily_metrics(self) -> Dict[str, Any]:
        return self._daily_metrics

    def get_check_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._check_history[:limit]
