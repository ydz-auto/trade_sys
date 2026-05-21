#!/usr/bin/env python3
"""
OrderBook Feature Extraction - 实时采集脚本

从Binance WebSocket实时获取订单簿和成交数据，提取特征并存储到Parquet

使用方法:
    python scripts/extract_orderbook_features.py --symbols BTCUSDT ETHUSDT --duration 3600
"""

import asyncio
import json
import sys
import signal
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aggregation_service.models.orderbook_model import (
    OrderBookSnapshot,
    OrderBookLevel,
    OrderBookFeature,
    TradeEvent,
    TradeFlowState,
    SweepState,
)
from services.aggregation_service.aggregators.orderbook.orderbook_aggregator import (
    OrderBookAggregator,
    TradeFlowCalculator,
    SymbolState,
)
from services.aggregation_service.publishers.parquet_writer import (
    get_parquet_writer,
)
from infrastructure.data_lake import get_data_lake_subpath


class BinanceWebSocketCollector:
    """Binance WebSocket订单簿采集器"""
    
    def __init__(
        self,
        symbols: List[str],
        output_path: str = None,
        buffer_size: int = 1000
    ):
        self.symbols = [s.upper() for s in symbols]
        if output_path is None:
            output_path = str(get_data_lake_subpath("orderbook_features"))
        self.output_path = output_path
        self.buffer_size = buffer_size
        
        self.aggregators: Dict[str, OrderBookAggregator] = {}
        self.writer = None
        
        self.running = True
        self.stats = {
            'snapshots_processed': 0,
            'features_extracted': 0,
            'trades_processed': 0,
            'errors': 0,
            'start_time': None,
        }
        
        for symbol in self.symbols:
            self.aggregators[symbol] = OrderBookAggregator(snapshot_interval_ms=1000)
    
    async def initialize(self):
        """初始化"""
        try:
            self.writer = get_parquet_writer(base_path=self.output_path)
            print(f"Initialized parquet writer at: {self.output_path}")
        except Exception as e:
            print(f"Failed to initialize parquet writer: {e}")
            raise
    
    async def process_depth_message(self, symbol: str, data: dict):
        """处理订单簿深度消息"""
        try:
            aggregator = self.aggregators.get(symbol)
            if not aggregator:
                return
            
            bids = [
                OrderBookLevel(price=float(b[0]), quantity=float(b[1]))
                for b in data.get('bids', [])[:20]
            ]
            asks = [
                OrderBookLevel(price=float(a[0]), quantity=float(a[1]))
                for a in data.get('asks', [])[:20]
            ]
            
            snapshot = OrderBookSnapshot(
                exchange="binance",
                symbol=symbol,
                timestamp=int(datetime.now().timestamp() * 1000),
                bids=bids,
                asks=asks,
                last_update_id=int(data.get('lastUpdateId', 0)),
            )
            
            feature = aggregator.process_snapshot(snapshot)
            self.stats['snapshots_processed'] += 1
            
            if feature:
                self.writer.add_feature(feature)
                self.stats['features_extracted'] += 1
                
        except Exception as e:
            self.stats['errors'] += 1
            if self.stats['errors'] % 100 == 0:
                print(f"Error processing depth: {e}")
    
    async def process_trade_message(self, symbol: str, data: dict):
        """处理成交消息"""
        try:
            aggregator = self.aggregators.get(symbol)
            if not aggregator:
                return
            
            trade = TradeEvent(
                exchange="binance",
                symbol=symbol,
                timestamp=int(data.get('T', 0)),
                trade_id=str(data.get('t', '')),
                price=float(data.get('p', 0)),
                quantity=float(data.get('q', 0)),
                side="buy" if data.get('m', True) else "sell",
                is_buyer_maker=data.get('m', True),
            )
            
            aggregator.process_trade(trade)
            self.stats['trades_processed'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
    
    async def connect_websocket(self, uri: str, symbol: str, stream_type: str):
        """连接WebSocket并接收数据"""
        try:
            import websockets
            
            async with websockets.connect(uri) as ws:
                print(f"Connected to {stream_type} stream: {symbol}")
                
                async for message in ws:
                    if not self.running:
                        break
                    
                    try:
                        data = json.loads(message)
                        
                        if stream_type == 'depth':
                            await self.process_depth_message(symbol, data)
                        elif stream_type == 'trade':
                            await self.process_trade_message(symbol, data)
                            
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        self.stats['errors'] += 1
                        
        except Exception as e:
            print(f"WebSocket error for {symbol} {stream_type}: {e}")
            self.stats['errors'] += 1
    
    async def start_collection(self, duration_seconds: Optional[int] = None):
        """开始采集"""
        self.stats['start_time'] = datetime.now()
        
        print("=" * 80)
        print("OrderBook Feature Extraction - Real-time Collection")
        print("=" * 80)
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Output: {self.output_path}")
        print(f"Duration: {duration_seconds if duration_seconds else 'unlimited'} seconds")
        print()
        
        tasks = []
        
        for symbol in self.symbols:
            symbol_lower = symbol.lower()
            
            depth_uri = f"wss://stream.binance.com:9443/stream?streams={symbol_lower}@depth20@100ms/{symbol_lower}@depth20@100ms"
            trade_uri = f"wss://stream.binance.com:9443/stream?streams={symbol_lower}@trade/{symbol_lower}@trade"
            
            tasks.append(self.connect_websocket(depth_uri, symbol, 'depth'))
            tasks.append(self.connect_websocket(trade_uri, symbol, 'trade'))
        
        async def monitor_stats():
            """定期打印统计信息"""
            while self.running:
                await asyncio.sleep(10)
                elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Elapsed: {elapsed:.0f}s | "
                      f"Snapshots: {self.stats['snapshots_processed']} | "
                      f"Features: {self.stats['features_extracted']} | "
                      f"Trades: {self.stats['trades_processed']} | "
                      f"Errors: {self.stats['errors']}")
                
                self.writer.flush_all()
        
        tasks.append(monitor_stats())
        
        if duration_seconds:
            tasks.append(asyncio.sleep(duration_seconds))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """停止采集"""
        print("\nStopping collection...")
        self.running = False
        
        if self.writer:
            print("Flushing remaining features...")
            self.writer.flush_all()
            
            stats = self.writer.get_storage_stats()
            print("\nStorage Stats:")
            print(f"  Total Files: {stats['total_files']}")
            print(f"  Total Size: {stats['total_size_mb']:.2f} MB")
            for symbol, info in stats['symbols'].items():
                print(f"  {symbol}: {info['size_mb']:.2f} MB")
        
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        print(f"\nCollection Summary:")
        print(f"  Duration: {elapsed:.0f} seconds")
        print(f"  Snapshots Processed: {self.stats['snapshots_processed']}")
        print(f"  Features Extracted: {self.stats['features_extracted']}")
        print(f"  Trades Processed: {self.stats['trades_processed']}")
        print(f"  Errors: {self.stats['errors']}")


async def main():
    parser = argparse.ArgumentParser(
        description="Extract orderbook features from Binance WebSocket"
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['BTCUSDT', 'ETHUSDT'],
        help='Trading symbols to monitor (default: BTCUSDT ETHUSDT)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=None,
        help='Collection duration in seconds (default: run indefinitely)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path for parquet files'
    )
    parser.add_argument(
        '--buffer-size',
        type=int,
        default=1000,
        help='Buffer size before flushing to parquet'
    )
    
    args = parser.parse_args()
    
    collector = BinanceWebSocketCollector(
        symbols=args.symbols,
        output_path=args.output,
        buffer_size=args.buffer_size
    )
    
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal...")
        asyncio.create_task(collector.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await collector.initialize()
        await collector.start_collection(duration_seconds=args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(main())
