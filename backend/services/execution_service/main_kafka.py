"""
Execution Service - Kafka Consumer

消费 signals，生成订单
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
from infrastructure.messaging import get_broker, Topics

logger = get_logger("execution_service.kafka")


class OrderExecutor:
    """订单执行器"""

    def __init__(self):
        from services.execution_service.execution_engine import (
            get_execution_service,
            OrderRequest,
            OrderSide,
            OrderType,
            Exchange
        )
        self.executor = get_execution_service()
        self.OrderRequest = OrderRequest
        self.OrderSide = OrderSide
        self.OrderType = OrderType
        self.Exchange = Exchange

    async def execute_signal(self, signal: dict) -> dict:
        """执行信号"""
        action = signal.get("action", "")
        symbol = signal.get("symbol", "BTC/USDT")
        quantity = signal.get("quantity", 0.001)

        if action == "HOLD":
            return {"status": "skipped", "reason": "No action"}

        try:
            if action in ["LONG", "BUY"]:
                side = self.OrderSide.BUY
            elif action in ["SHORT", "SELL"]:
                side = self.OrderSide.SELL
            else:
                return {"status": "error", "reason": f"Unknown action: {action}"}

            request = self.OrderRequest(
                symbol=symbol,
                exchange=self.Exchange.BINANCE,
                side=side,
                order_type=self.OrderType.MARKET,
                quantity=quantity
            )

            result = await self.executor.execute_order(request)

            if result.success:
                return {
                    "status": "success",
                    "order_id": result.order.order_id,
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity
                }
            else:
                return {"status": "error", "reason": result.error}

        except Exception as e:
            logger.error(f"Execute signal error: {e}")
            return {"status": "error", "reason": str(e)}


broker = None
executor = OrderExecutor()


async def handle_signal(msg: dict):
    """处理信号，生成订单"""
    try:
        signal = msg
        symbol = signal.get("assets", ["BTC"])[0] if signal.get("assets") else "BTC/USDT"

        action = signal.get("action", signal.get("signal", "HOLD"))
        confidence = signal.get("confidence", 0.5)

        print("\n" + "=" * 60)
        print("📊 RECEIVED SIGNAL")
        print("=" * 60)
        print(f"  Symbol:     {symbol}")
        print(f"  Action:     {action}")
        print(f"  Confidence: {confidence:.3f}")
        print("-" * 60)

        # 执行订单
        result = await executor.execute_signal({
            "action": action,
            "symbol": symbol,
            "quantity": 0.001  # 最小下单量
        })

        print(f"\n{'✅' if result['status'] == 'success' else '⚠️' if result['status'] == 'skipped' else '❌'} Result: {result['status']}")
        if result.get("order_id"):
            print(f"   Order ID: {result['order_id']}")
        if result.get("reason"):
            print(f"   Reason:   {result['reason']}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"[execution_service] Error: {e}")


async def main():
    global broker

    print("=" * 60)
    print("Execution Service - Kafka Consumer")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.SIGNALS}")
    print("=" * 60)

    try:
        broker = get_broker(bootstrap_servers)

        print("\n[execution_service] Waiting for signals...\n")

        @broker.subscriber(Topics.SIGNALS)
        async def on_signal(msg: dict):
            await handle_signal(msg)

        await broker.run()

    except Exception as e:
        print(f"\n[execution_service] Kafka not available: {e}")
        print("[execution_service] Running in standalone mode...")

        # 模拟模式
        while True:
            await asyncio.sleep(5)
            await handle_signal({
                "action": "LONG",
                "symbol": "BTC/USDT",
                "confidence": 0.8
            })


if __name__ == "__main__":
    asyncio.run(main())
