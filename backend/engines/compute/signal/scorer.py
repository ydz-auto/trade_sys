from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.event.event_category import EventCategory
from domain.event.event_type import EventType
from domain.event.direction import Direction
from engines.compute.aggregation.aggregator import AggregatedGroup


EVENT_WEIGHTS: dict[str, float] = {
    "etf_inflow": 1.0,
    "etf_outflow": 1.0,
    "exchange_net_inflow": 0.9,
    "exchange_net_outflow": 0.9,
    "stablecoin_inflow": 0.85,
    "stablecoin_outflow": 0.85,
    "whale_transfer": 0.8,
    "liquidation": 0.9,
    "funding_rate_spike": 0.7,
    "open_interest_spike": 0.7,
    "rate_cut": 0.9,
    "rate_hike": 0.9,
    "regulation_positive": 0.9,
    "regulation_negative": 0.9,
    "etf_approval": 1.0,
    "etf_rejection": 1.0,
    "hack": 0.95,
    "exchange_collapse": 1.0,
    "stablecoin_depeg": 1.0,
    "mainnet_launch": 0.8,
    "token_unlock": 0.75,
    "airdrop": 0.7,
    "partnership": 0.8,
    "upgrade": 0.7,
    "kol_bullish": 0.5,
    "kol_bearish": 0.5,
    "social_spike": 0.4,
    "narrative_trend": 0.4,
    "fear_index_extreme": 0.5,
}

SOURCE_QUALITY: dict[str, float] = {
    "onchain": 0.9,
    "exchange_api": 0.85,
    "etf_tracker": 0.9,
    "news": 0.7,
    "twitter": 0.5,
    "social": 0.4,
}


@dataclass
class ScoreResult:
    confidence: float
    consensus: float
    strength: float
    quality: float
    market_confirmation: float
    event_weight: float


class ScoringEngine:
    def __init__(
        self,
        weight_source_diversity: float = 0.35,
        weight_strength: float = 0.25,
        weight_quality: float = 0.20,
        weight_market: float = 0.20,
    ):
        self.weight_source_diversity = weight_source_diversity
        self.weight_strength = weight_strength
        self.weight_quality = weight_quality
        self.weight_market = weight_market

    def score(
        self,
        group: AggregatedGroup,
        price_change: float = 0.0,
    ) -> ScoreResult:
        source_diversity = self._calc_source_diversity(group)
        strength = self._calc_strength(group)
        quality = self._calc_quality(group)
        market_confirmation = self._calc_market_confirmation(price_change)
        event_weight = self._calc_event_weight(group.event_type)

        confidence = (
            self.weight_source_diversity * source_diversity
            + self.weight_strength * strength
            + self.weight_quality * quality
            + self.weight_market * market_confirmation
        )

        consensus = self._calc_consensus(group, source_diversity)

        return ScoreResult(
            confidence=min(confidence * event_weight, 1.0),
            consensus=consensus,
            strength=strength,
            quality=quality,
            market_confirmation=market_confirmation,
            event_weight=event_weight,
        )

    def _calc_source_diversity(self, group: AggregatedGroup) -> float:
        return group.source_diversity

    def _calc_strength(self, group: AggregatedGroup) -> float:
        return group.avg_strength

    def _calc_quality(self, group: AggregatedGroup) -> float:
        all_quality = []
        for event in group.events:
            for source in event.sources:
                quality = SOURCE_QUALITY.get(source.lower(), 0.5)
                all_quality.append(quality)

        if not all_quality:
            return 0.5

        return sum(all_quality) / len(all_quality)

    def _calc_market_confirmation(self, price_change: float) -> float:
        abs_change = abs(price_change)

        if abs_change > 0.05:
            return 1.0
        elif abs_change > 0.02:
            return 0.7
        elif abs_change > 0.01:
            return 0.5
        elif abs_change > 0.005:
            return 0.3
        return 0.2

    def _calc_consensus(self, group: AggregatedGroup, source_diversity: float) -> float:
        event_count_factor = min(group.event_count / 5, 1.0)
        return (source_diversity * 0.6 + event_count_factor * 0.4)

    def _calc_event_weight(self, event_type: str) -> float:
        normalized = event_type.lower().replace("_", " ").replace("-", " ")
        for key, weight in EVENT_WEIGHTS.items():
            key_normalized = key.lower().replace("_", " ").replace("-", " ")
            if key_normalized in normalized or normalized in key_normalized:
                return weight
        return 0.5
