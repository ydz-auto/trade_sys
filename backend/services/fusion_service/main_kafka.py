"""
Fusion Service - Kafka Consumer + Producer

消费 events，进行融合，发布 signals 到 Kafka

用法:
    python -m services.fusion_service.main_kafka
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import os
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("fusion_service.kafka")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import Event, Signal
from services.fusion_service import FusionEngine, FusionEvent


broker = None
engine = FusionEngine(window_seconds=300, min_events=1, min_confidence=0.3)


def resolve_conflict(signals: list) -> list[dict]:
    """冲突解决：多个信号 → 每个资产一个最终信号"""
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


async def handle_event(msg: dict):
    """处理事件，进行融合"""
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

        engine.add_event(fusion_event)
        print(f"[fusion_service] Buffer size: {engine.get_buffer_size()}")

        signals = engine.process(price_change=0.02)

        if signals:
            print(f"[fusion_service] Generated {len(signals)} signals")

            final_signals = resolve_conflict(signals)

            for fs in final_signals:
                print(f"[fusion_service] Final: {fs['signal']} confidence={fs['confidence']:.3f}")

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

                await broker.publish(
                    message=signal.model_dump(),
                    topic=Topics.SIGNALS,
                    key=fs["asset"],
                )
                print(f"[fusion_service] Published signal to {Topics.SIGNALS}")

    except Exception as e:
        print(f"[fusion_service] Error: {e}")


async def main():
    global broker

    print("=" * 60)
    print("Fusion Service - Kafka Consumer")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.EVENTS}")
    print(f"Publish: {Topics.SIGNALS}")
    print("=" * 60)

    broker = get_broker(bootstrap_servers)

    print("\n[fusion_service] Starting to consume events...\n")

    @broker.subscriber(Topics.EVENTS)
    async def on_event(msg: dict):
        await handle_event(msg)

    await broker.run()


if __name__ == "__main__":
    asyncio.run(main())
