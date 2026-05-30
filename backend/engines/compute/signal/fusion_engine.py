from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field

from engines.compute.aggregation.aggregator import EventAggregator
from engines.compute.signal.scorer import ScoringEngine


@dataclass
class FusionEvent:
    id: str
    timestamp: datetime
    source: str
    event_type: str
    category: str
    asset: Optional[str]
    direction: str
    strength: float
    sources: list[str] = field(default_factory=list)
    raw_data_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class FusionSignal:
    id: str
    timestamp: datetime
    source: str
    signal: str
    direction: str
    confidence: float
    consensus: float
    event_types: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    strength: float = 0.5
    event_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and self.event_count >= 3

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.6 and self.event_count >= 2


class FusionEngine:
    def __init__(
        self,
        min_events: int = 1,
        min_confidence: float = 0.4,
    ):
        self.aggregator = EventAggregator(min_events=min_events)
        self.scorer = ScoringEngine()
        self.min_confidence = min_confidence

    def process(self, events: list, price_change: float = 0.0) -> list[FusionSignal]:
        if not events:
            return []

        groups = self.aggregator.aggregate(events)

        signals = []
        for group in groups:
            signal = self._generate_signal(group, price_change)
            if signal:
                signals.append(signal)

        return signals

    def _generate_signal(
        self,
        group: Any,
        price_change: float,
    ) -> Optional[FusionSignal]:
        score = self.scorer.score(group, price_change)

        if score.confidence < self.min_confidence:
            return None

        direction_str = group.direction.value if hasattr(group.direction, 'value') else group.direction
        asset_str = group.asset or "UNKNOWN"

        signal = FusionSignal(
            id=f"sig_{int(datetime.utcnow().timestamp())}",
            timestamp=datetime.utcnow(),
            source="fusion_engine",
            signal=f"{asset_str.upper()}_{direction_str.upper()}",
            direction=direction_str,
            confidence=score.confidence,
            consensus=score.consensus,
            event_types=[group.event_type],
            assets=[group.asset] if group.asset else [],
            strength=score.strength,
            event_count=group.event_count,
            metadata={
                "source_count": group.source_count,
                "avg_strength": group.avg_strength,
                "market_confirmation": score.market_confirmation,
                "event_weight": score.event_weight,
            },
        )

        return signal
