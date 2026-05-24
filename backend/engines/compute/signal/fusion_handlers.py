from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Optional

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.event import Event
from infrastructure.messaging.schema.signal import Signal
from engines.compute.signal.fusion_engine import FusionEngine, FusionEvent

logger = get_logger("fusion_service.handlers")


class FusionHandler:

    def __init__(
        self,
        window_seconds: int = 300,
        min_events: int = 1,
        min_confidence: float = 0.3,
    ):
        self.engine = FusionEngine(
            window_seconds=window_seconds,
            min_events=min_events,
            min_confidence=min_confidence,
        )

    def resolve_conflict(self, signals: list) -> List[Dict[str, Any]]:
        if not signals:
            return []

        asset_map = defaultdict(lambda: {"bullish": 0.0, "bearish": 0.0, "events": 0})

        for s in signals:
            asset = s.assets[0] if s.assets else "CRYPTO"
            direction = s.direction

            if direction == "bullish":
                asset_map[asset]["bullish"] += s.confidence
            elif direction == "bearish":
                asset_map[asset]["bearish"] += s.confidence

            asset_map[asset]["events"] += 1

        final_signals = []

        for asset, v in asset_map.items():
            net = v["bullish"] - v["bearish"]

            if abs(net) < 0.05:
                continue

            direction = "bullish" if net > 0 else "bearish"
            confidence = abs(net)

            final_signals.append({
                "asset": asset,
                "signal": f"{asset}_{direction.upper()}",
                "direction": direction,
                "confidence": confidence,
                "net_bias": net,
                "event_count": v["events"],
            })

        return final_signals

    def process_event(self, msg: Dict[str, Any]) -> Optional[FusionEvent]:
        try:
            event = Event(**msg) if isinstance(msg, dict) else msg

            fusion_event = FusionEvent(
                id=event.id,
                timestamp=event.timestamp if isinstance(event.timestamp, datetime) else datetime.now(),
                source=event.sources[0] if event.sources else "event_service",
                event_type=event.event_type,
                category=event.category,
                asset=event.asset,
                direction=event.direction,
                strength=event.strength,
                sources=event.sources,
            )
            return fusion_event
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return None

    def add_event(self, fusion_event: FusionEvent) -> int:
        self.engine.add_event(fusion_event)
        return self.engine.get_buffer_size()

    def generate_signals(self, price_change: float = 0.02) -> List[Signal]:
        signals = self.engine.process(price_change=price_change)
        if not signals:
            return []

        final_signals = self.resolve_conflict(signals)

        result = []
        for fs in final_signals:
            signal = Signal(
                signal=fs["signal"],
                direction=fs["direction"],
                confidence=fs["confidence"],
                consensus=fs["net_bias"],
                event_types=[s.event_type for s in signals],
                assets=[fs["asset"]],
                strength=fs["confidence"],
                event_count=fs["event_count"],
                source="fusion_service",
            )
            result.append(signal)

        return result


def get_fusion_handler(
    window_seconds: int = 300,
    min_events: int = 1,
    min_confidence: float = 0.3,
) -> FusionHandler:
    return FusionHandler(
        window_seconds=window_seconds,
        min_events=min_events,
        min_confidence=min_confidence,
    )
