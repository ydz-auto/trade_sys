#!/usr/bin/env python3
"""
简单测试脚本：验证WebSocket连接和特征提取
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aggregation_service.models.orderbook_model import (
    OrderBookSnapshot,
    OrderBookLevel,
    OrderBookFeature,
    TradeEvent,
)
from services.aggregation_service.aggregators.orderbook.orderbook_aggregator import (
    OrderBookAggregator,
)


async def test_websocket():
    """测试WebSocket连接"""
    try:
        import websockets
        
        print("=" * 80)
        print("Testing Binance WebSocket Connection")
        print("=" * 80)
        
        aggregator = OrderBookAggregator(snapshot_interval_ms=1000)
        
        uri = "wss://stream.binance.com:9443/stream?streams=btcusdt@depth20@100ms/btcusdt@trade"
        
        print(f"\nConnecting to: {uri}")
        print("Press Ctrl+C to stop\n")
        
        count = 0
        async with websockets.connect(uri) as ws:
            print("✓ Connected successfully!\n")
            
            async for message in ws:
                try:
                    data = json.loads(message)
                    
                    if 'data' in data:
                        msg_data = data['data']
                        
                        if 'bids' in msg_data:
                            bids = [
                                OrderBookLevel(price=float(b[0]), quantity=float(b[1]))
                                for b in msg_data.get('bids', [])[:20]
                            ]
                            asks = [
                                OrderBookLevel(price=float(a[0]), quantity=float(a[1]))
                                for a in msg_data.get('asks', [])[:20]
                            ]
                            
                            snapshot = OrderBookSnapshot(
                                exchange="binance",
                                symbol="BTCUSDT",
                                timestamp=int(datetime.now().timestamp() * 1000),
                                bids=bids,
                                asks=asks,
                                last_update_id=int(msg_data.get('lastUpdateId', 0)),
                            )
                            
                            feature = aggregator.process_snapshot(snapshot)
                            
                            if feature and count % 5 == 0:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                                      f"Spread: {feature.spread:.2f} | "
                                      f"Imbalance: {feature.imbalance_10:.4f} | "
                                      f"Mid: {feature.mid_price:.2f} | "
                                      f"Micro: {feature.microprice:.2f}")
                            
                            count += 1
                            
                        elif 'T' in msg_data:
                            trade = TradeEvent(
                                exchange="binance",
                                symbol="BTCUSDT",
                                timestamp=int(msg_data.get('T', 0)),
                                trade_id=str(msg_data.get('t', '')),
                                price=float(msg_data.get('p', 0)),
                                quantity=float(msg_data.get('q', 0)),
                                side="buy" if msg_data.get('m', True) else "sell",
                                is_buyer_maker=msg_data.get('m', True),
                            )
                            
                            aggregator.process_trade(trade)
                    
                    if count >= 50:
                        break
                        
                except Exception as e:
                    print(f"Error: {e}")
        
        print("\n" + "=" * 80)
        print("Test Complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nFailed to connect: {e}")
        print("\nThis is expected if Binance WebSocket is not accessible.")
        print("You can still use the batch processing script for historical data.")


if __name__ == "__main__":
    asyncio.run(test_websocket())
