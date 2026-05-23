"""
Narrative Engine - AI 解释层

基于 Event + Factor + Signal 自动生成解释

功能：
- Event sequence summarization
- Decision explanation
- Runtime cognition
- Trading narrative generation
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from domain.logging import get_logger

logger = get_logger("narrative_engine")


class NarrativeType(str, Enum):
    """叙事类型"""
    SIGNAL = "signal"
    DECISION = "decision"
    REGIME = "regime"
    TRADE = "trade"
    SUMMARY = "summary"
    ALERT = "alert"


class Confidence(str, Enum):
    """置信度描述"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Narrative:
    """叙事"""
    narrative_id: str
    narrative_type: NarrativeType

    title: str
    content: str

    confidence: Confidence

    key_events: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.utcnow)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "narrative_id": self.narrative_id,
            "narrative_type": self.narrative_type.value,
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence.value,
            "key_events": self.key_events,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DecisionExplanation:
    """决策解释"""
    decision_id: str

    action: str
    symbol: str
    quantity: float

    triggering_events: List[Dict[str, Any]] = field(default_factory=list)
    supporting_factors: List[str] = field(default_factory=list)
    opposing_factors: List[str] = field(default_factory=list)

    confidence: float = 0.5

    reasoning: str = ""

    risk_assessment: str = ""

    alternative_actions: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "triggering_events": self.triggering_events,
            "supporting_factors": self.supporting_factors,
            "opposing_factors": self.opposing_factors,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk_assessment": self.risk_assessment,
            "alternative_actions": self.alternative_actions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SignalNarrative:
    """信号叙事"""
    signal_name: str
    symbol: str
    direction: str

    strength: float
    confidence: float

    contributing_events: List[Dict[str, Any]] = field(default_factory=list)

    timeframe_context: str = ""

    explanation: str = ""

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.strength,
            "confidence": self.confidence,
            "contributing_events": self.contributing_events,
            "timeframe_context": self.timeframe_context,
            "explanation": self.explanation,
            "timestamp": self.timestamp.isoformat(),
        }


class NarrativeEngine:
    """
    Narrative Engine

    职责：
    1. 生成决策解释
    2. 生成信号叙事
    3. 生成市场摘要
    4. 生成交易叙事
    """

    def __init__(self):
        self._narratives: List[Narrative] = []
        self._explanations: Dict[str, DecisionExplanation] = {}

        self._event_cache: Dict[str, List[Dict[str, Any]]] = {}

        self._stats = {
            "narratives_generated": 0,
            "explanations_generated": 0,
        }

    def add_event(self, event: Dict[str, Any]) -> None:
        """添加事件到缓存"""
        symbol = event.get("symbol", "BTC")

        if symbol not in self._event_cache:
            self._event_cache[symbol] = []

        self._event_cache[symbol].append(event)

        if len(self._event_cache[symbol]) > 100:
            self._event_cache[symbol] = self._event_cache[symbol][-100:]

    def generate_signal_narrative(
        self,
        signal_event: Dict[str, Any],
    ) -> SignalNarrative:
        """
        生成信号叙事

        Args:
            signal_event: 信号事件

        Returns:
            SignalNarrative: 信号叙事
        """
        symbol = signal_event.get("symbol", "BTC")
        direction = signal_event.get("direction", "neutral")

        recent_events = self._event_cache.get(symbol, [])

        contributing = self._find_contributing_events(recent_events, signal_event)

        direction_icon = "📈" if direction == "bullish" else "📉" if direction == "bearish" else "➡️"

        explanation_parts = [
            f"{direction_icon} {symbol} shows {direction} signal",
            f"Confidence: {signal_event.get('confidence', 0):.0%}",
        ]

        if signal_event.get("event_count", 0) > 0:
            explanation_parts.append(
                f"Aggregated from {signal_event['event_count']} events"
            )

        if contributing:
            event_types = list(set(e.get("event_category", e.get("raw_event_type", "unknown")) for e in contributing))
            explanation_parts.append(f"Key factors: {', '.join(event_types[:3])}")

        narrative = SignalNarrative(
            signal_name=signal_event.get("signal_name", "Unknown"),
            symbol=symbol,
            direction=direction,
            strength=signal_event.get("strength", 0.5),
            confidence=signal_event.get("confidence", 0.5),
            contributing_events=contributing,
            explanation=". ".join(explanation_parts),
            timestamp=datetime.utcnow(),
        )

        self._stats["narratives_generated"] += 1

        return narrative

    def _find_contributing_events(
        self,
        recent_events: List[Dict[str, Any]],
        signal_event: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """找到贡献事件"""
        if not recent_events:
            return []

        signal_time = self._parse_timestamp(signal_event.get("timestamp"))

        cutoff = signal_time - timedelta(hours=4)

        contributing = [
            e for e in recent_events
            if self._parse_timestamp(e.get("timestamp")) >= cutoff
            and e.get("event_type") in ("event", "raw_data")
        ]

        return contributing[-10:]

    def generate_decision_explanation(
        self,
        decision_event: Dict[str, Any],
        signal_event: Optional[Dict[str, Any]] = None,
    ) -> DecisionExplanation:
        """
        生成决策解释

        Args:
            decision_event: 决策事件
            signal_event: 关联的信号事件

        Returns:
            DecisionExplanation: 决策解释
        """
        symbol = decision_event.get("symbol", "BTC")
        action = decision_event.get("action", "HOLD")
        confidence = decision_event.get("confidence", 0.5)

        recent_events = self._event_cache.get(symbol, [])

        triggering = self._find_triggering_events(recent_events, decision_event)

        supporting = self._extract_supporting_factors(triggering)
        opposing = self._extract_opposing_factors(triggering)

        reasoning_parts = [
            f"{action} {symbol}",
            f"Confidence: {confidence:.0%}",
        ]

        if supporting:
            reasoning_parts.append(f"Supported by: {', '.join(supporting[:2])}")

        if opposing:
            reasoning_parts.append(f"Concerns: {', '.join(opposing[:2])}")

        reasoning_parts.append(decision_event.get("reason", ""))

        risk_parts = []

        if confidence < 0.6:
            risk_parts.append("Low confidence - smaller position recommended")

        if opposing:
            risk_parts.append(f"{len(opposing)} conflicting factors present")

        recent_volatility = self._estimate_volatility(recent_events)
        if recent_volatility > 0.5:
            risk_parts.append("High volatility - wider stop loss needed")

        risk_assessment = ". ".join(risk_parts) if risk_parts else "Risk within acceptable range"

        alternatives = []
        if action in ("LONG", "BUY"):
            alternatives = ["HOLD (wait for confirmation)", "SHORT (if bearish reversal)"]
        elif action in ("SHORT", "SELL"):
            alternatives = ["HOLD", "LONG (if bullish reversal)"]

        explanation = DecisionExplanation(
            decision_id=decision_event.get("decision_id", f"dec_{id(decision_event)}"),
            action=action,
            symbol=symbol,
            quantity=decision_event.get("quantity", 0.01),
            triggering_events=triggering,
            supporting_factors=supporting,
            opposing_factors=opposing,
            confidence=confidence,
            reasoning=". ".join(reasoning_parts),
            risk_assessment=risk_assessment,
            alternative_actions=alternatives,
            timestamp=datetime.utcnow(),
        )

        self._explanations[explanation.decision_id] = explanation
        self._stats["explanations_generated"] += 1

        logger.info(f"Generated explanation for {action} {symbol}")

        return explanation

    def _find_triggering_events(
        self,
        recent_events: List[Dict[str, Any]],
        decision_event: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """找到触发事件"""
        if not recent_events:
            return []

        decision_time = self._parse_timestamp(decision_event.get("timestamp"))

        cutoff = decision_time - timedelta(hours=24)

        triggering = [
            e for e in recent_events
            if self._parse_timestamp(e.get("timestamp")) >= cutoff
        ]

        return triggering[-20:]

    def _extract_supporting_factors(
        self,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        """提取支持因素"""
        factors = []

        for event in events:
            event_type = event.get("event_type", "")

            if event_type == "event":
                direction = event.get("direction", "")
                category = event.get("event_category", "")

                if direction == "bullish":
                    factors.append(f"Positive {category}")
                elif direction == "bearish":
                    factors.append(f"Negative {category}")

            elif event_type == "signal":
                signal_name = event.get("signal_name", "")
                direction = event.get("direction", "")

                if direction == "bullish":
                    factors.append(f"Bullish signal: {signal_name}")
                elif direction == "bearish":
                    factors.append(f"Bearish signal: {signal_name}")

        return list(dict.fromkeys(factors))[:5]

    def _extract_opposing_factors(
        self,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        """提取反对因素"""
        factors = []

        bullish_count = sum(
            1 for e in events
            if e.get("direction") == "bullish"
        )
        bearish_count = sum(
            1 for e in events
            if e.get("direction") == "bearish"
        )

        if bullish_count > 0 and bearish_count > 0:
            factors.append("Conflicting directional signals")

        recent_events = events[-5:]
        conflicting = sum(
            1 for i in range(len(recent_events) - 1)
            if recent_events[i].get("direction") != recent_events[i+1].get("direction")
            and recent_events[i].get("direction") and recent_events[i+1].get("direction")
        )

        if conflicting > 2:
            factors.append("Rapid signal reversal")

        return factors

    def _estimate_volatility(
        self,
        events: List[Dict[str, Any]],
    ) -> float:
        """估计波动率"""
        market_events = [
            e for e in events
            if e.get("event_type") == "market" or "volatility" in str(e.get("event_category", "")).lower()
        ]

        if len(market_events) < 2:
            return 0.3

        strengths = [e.get("strength", 0.5) for e in market_events]

        return sum(strengths) / len(strengths)

    def generate_market_summary(
        self,
        symbol: str,
        hours: int = 4,
    ) -> Narrative:
        """
        生成市场摘要

        Args:
            symbol: 品种
            hours: 回溯小时数

        Returns:
            Narrative: 市场摘要叙事
        """
        recent_events = self._event_cache.get(symbol, [])

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        relevant_events = [
            e for e in recent_events
            if self._parse_timestamp(e.get("timestamp")) >= cutoff
        ]

        event_summary = self._summarize_events(relevant_events)

        title = f"{symbol} Market Summary"

        content_parts = [
            f"Over the past {hours} hours:",
        ]

        if event_summary["bullish_count"] > event_summary["bearish_count"]:
            content_parts.append(f"Bullish bias with {event_summary['bullish_count']} positive events")
        elif event_summary["bearish_count"] > event_summary["bullish_count"]:
            content_parts.append(f"Bearish bias with {event_summary['bearish_count']} negative events")
        else:
            content_parts.append("Neutral with balanced positive and negative events")

        if event_summary["signals_generated"] > 0:
            content_parts.append(f"{event_summary['signals_generated']} signals generated")

        if event_summary["decisions_made"] > 0:
            content_parts.append(f"{event_summary['decisions_made']} decisions made")

        if event_summary["orders_filled"] > 0:
            content_parts.append(f"{event_summary['orders_filled']} orders filled")

        content = ". ".join(content_parts)

        narrative = Narrative(
            narrative_id=f"summary_{symbol}_{datetime.utcnow().timestamp()}",
            narrative_type=NarrativeType.SUMMARY,
            title=title,
            content=content,
            confidence=Confidence.MEDIUM if event_summary["total_events"] > 10 else Confidence.LOW,
            key_events=event_summary["top_events"],
            timestamp=datetime.utcnow(),
        )

        self._narratives.append(narrative)
        self._stats["narratives_generated"] += 1

        return narrative

    def _summarize_events(
        self,
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """总结事件"""
        summary = {
            "total_events": len(events),
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "signals_generated": 0,
            "decisions_made": 0,
            "orders_filled": 0,
            "top_events": [],
        }

        for event in events:
            event_type = event.get("event_type", "")

            if event_type == "event":
                direction = event.get("direction", "neutral")
                if direction == "bullish":
                    summary["bullish_count"] += 1
                elif direction == "bearish":
                    summary["bearish_count"] += 1
                else:
                    summary["neutral_count"] += 1

            elif event_type == "signal":
                summary["signals_generated"] += 1

            elif event_type == "decision":
                summary["decisions_made"] += 1

            elif event_type == "fill":
                summary["orders_filled"] += 1

        summary["top_events"] = [
            e.get("event_category", e.get("signal_name", e.get("action", "event")))
            for e in events[-5:]
        ]

        return summary

    def generate_trade_narrative(
        self,
        trade_result: Dict[str, Any],
    ) -> Narrative:
        """
        生成交易叙事

        Args:
            trade_result: 交易结果

        Returns:
            Narrative: 交易叙事
        """
        symbol = trade_result.get("symbol", "BTC")
        pnl = trade_result.get("pnl", 0)
        side = trade_result.get("side", "unknown")

        pnl_emoji = "💰" if pnl > 0 else "💸" if pnl < 0 else "➖"

        title = f"{symbol} Trade {pnl_emoji}"

        content_parts = [
            f"{side.upper()} position closed",
            f"PnL: ${pnl:.2f}",
        ]

        if trade_result.get("holding_period"):
            content_parts.append(
                f"Held for {trade_result['holding_period']}"
            )

        if trade_result.get("exit_reason"):
            content_parts.append(
                f"Exit reason: {trade_result['exit_reason']}"
            )

        narrative = Narrative(
            narrative_id=f"trade_{symbol}_{datetime.utcnow().timestamp()}",
            narrative_type=NarrativeType.TRADE,
            title=title,
            content=". ".join(content_parts),
            confidence=Confidence.HIGH,
            timestamp=datetime.utcnow(),
            metadata={"pnl": pnl, "side": side},
        )

        self._narratives.append(narrative)
        self._stats["narratives_generated"] += 1

        return narrative

    def get_explanation(self, decision_id: str) -> Optional[DecisionExplanation]:
        """获取决策解释"""
        return self._explanations.get(decision_id)

    def get_recent_narratives(
        self,
        narrative_type: Optional[NarrativeType] = None,
        limit: int = 10,
    ) -> List[Narrative]:
        """获取最近的叙事"""
        narratives = self._narratives

        if narrative_type:
            narratives = [n for n in narratives if n.narrative_type == narrative_type]

        return narratives[-limit:]

    def _parse_timestamp(self, ts) -> datetime:
        """解析时间戳"""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return datetime.utcnow()
        return datetime.utcnow()

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "narratives_stored": len(self._narratives),
            "explanations_stored": len(self._explanations),
        }


_narrative_engine: Optional[NarrativeEngine] = None


def get_narrative_engine() -> NarrativeEngine:
    """获取 NarrativeEngine 单例"""
    global _narrative_engine
    if _narrative_engine is None:
        _narrative_engine = NarrativeEngine()
    return _narrative_engine
