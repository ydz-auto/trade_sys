"""
Strategy Service - Kafka Consumer

消费 signals，输出最终交易决策

用法:
    python -m services.strategy_service.main_kafka
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import Signal


broker = None


def decide_action(signal: Signal) -> dict:
    """根据信号决定最终 action"""
    confidence = signal.confidence

    if confidence < 0.1:
        return {"action": "HOLD", "position": 0.0, "reason": "信号模糊"}

    direction = signal.direction

    if direction == "bullish":
        action = "LONG"
        position = min(confidence * 0.8, 0.9)
    elif direction == "bearish":
        action = "SHORT"
        position = min(confidence * 0.8, 0.9)
    else:
        return {"action": "HOLD", "position": 0.0, "reason": "中性信号"}

    return {
        "action": action,
        "position": round(position, 2),
        "reason": f"置信度 {confidence:.3f}"
    }


async def handle_signal(msg: dict):
    """处理信号，输出最终决策"""
    try:
        signal = Signal(**msg) if isinstance(msg, dict) else msg

        decision = decide_action(signal)

        print("\n" + "=" * 60)
        print("🎯 FINAL TRADING DECISION")
        print("=" * 60)
        print(f"  Symbol:     {signal.assets[0] if signal.assets else 'CRYPTO'}")
        print(f"  Signal:     {signal.signal}")
        print(f"  Confidence: {signal.confidence:.3f}")
        print("-" * 60)
        print(f"  ✅ ACTION:   {decision['action']}")
        print(f"  📊 POSITION: {decision['position']}")
        print(f"  💡 REASON:   {decision['reason']}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"[strategy_service] Error: {e}")


async def main():
    global broker

    print("=" * 60)
    print("Strategy Service - Kafka Consumer")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.SIGNALS}")
    print("=" * 60)

    broker = get_broker(bootstrap_servers)

    print("\n[strategy_service] Waiting for signals...\n")

    @broker.subscriber(Topics.SIGNALS)
    async def on_signal(msg: dict):
        await handle_signal(msg)

    await broker.run()


if __name__ == "__main__":
    asyncio.run(main())
