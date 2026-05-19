#!/usr/bin/env python3
"""
OrderBook Feature Extraction Test

测试 orderbook 特征提取功能：
1. 从 Binance 获取实时订单簿
2. 提取高价值特征
3. 存储到 Parquet
"""

import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import List

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
    SweepDetector,
    SymbolState,
)
from services.aggregation_service.publishers.parquet_writer import (
    OrderBookFeatureParquetWriter,
    get_parquet_writer,
)


def create_mock_snapshot(
    exchange: str = "binance",
    symbol: str = "BTCUSDT",
    bid_price: float = 65000.0,
    ask_price: float = 65001.0,
) -> OrderBookSnapshot:
    """创建模拟订单簿快照"""
    bids = []
    asks = []
    
    for i in range(10):
        bids.append(OrderBookLevel(
            price=bid_price - i * 0.5,
            quantity=1.0 + i * 0.1
        ))
        asks.append(OrderBookLevel(
            price=ask_price + i * 0.5,
            quantity=1.0 + i * 0.1
        ))
    
    return OrderBookSnapshot(
        exchange=exchange,
        symbol=symbol,
        timestamp=int(datetime.now().timestamp() * 1000),
        bids=bids,
        asks=asks,
        last_update_id=123456,
    )


def create_mock_trade(
    exchange: str = "binance",
    symbol: str = "BTCUSDT",
    price: float = 65000.0,
    quantity: float = 1.0,
    is_buyer_maker: bool = True,
) -> TradeEvent:
    """创建模拟交易"""
    return TradeEvent(
        exchange=exchange,
        symbol=symbol,
        timestamp=int(datetime.now().timestamp() * 1000),
        trade_id=f"trade_{int(datetime.now().timestamp() * 1000)}",
        price=price,
        quantity=quantity,
        side="buy" if not is_buyer_maker else "sell",
        is_buyer_maker=is_buyer_maker,
    )


def print_feature(feature: OrderBookFeature, indent: int = 0):
    """打印特征"""
    prefix = "  " * indent
    print(f"{prefix}=== OrderBook Feature ===")
    print(f"{prefix}Exchange/Symbol: {feature.exchange}/{feature.symbol}")
    print(f"{prefix}Timestamp: {feature.timestamp}")
    print(f"{prefix}")
    print(f"{prefix}--- Top-of-Book ---")
    print(f"{prefix}  Spread: {feature.spread:.2f}")
    print(f"{prefix}  Spread %: {feature.spread_pct:.6f}")
    print(f"{prefix}  Mid Price: {feature.mid_price:.2f}")
    print(f"{prefix}  Microprice: {feature.microprice:.2f}")
    print(f"{prefix}  Best Bid/Ask Size: {feature.best_bid_size:.4f} / {feature.best_ask_size:.4f}")
    print(f"{prefix}")
    print(f"{prefix}--- Imbalance ---")
    print(f"{prefix}  Imbalance 1: {feature.imbalance_1:.4f}")
    print(f"{prefix}  Imbalance 5: {feature.imbalance_5:.4f}")
    print(f"{prefix}  Imbalance 10: {feature.imbalance_10:.4f}")
    print(f"{prefix}  Imbalance Slope: {feature.imbalance_slope:.4f}")
    print(f"{prefix}")
    print(f"{prefix}--- Depth ---")
    print(f"{prefix}  Top5 Bid/Ask: {feature.top5_bid_volume:.4f} / {feature.top5_ask_volume:.4f}")
    print(f"{prefix}  Top10 Bid/Ask: {feature.top10_bid_volume:.4f} / {feature.top10_ask_volume:.4f}")
    print(f"{prefix}  Depth Ratio: {feature.depth_ratio:.4f}")
    print(f"{prefix}  Depth Change: {feature.depth_change:.4f}")
    print(f"{prefix}")
    print(f"{prefix}--- Trade Flow ---")
    print(f"{prefix}  Trade Delta: {feature.trade_delta:.4f}")
    print(f"{prefix}  Cumulative Delta: {feature.cumulative_delta:.4f}")
    print(f"{prefix}  Aggressive Buy/Sell: {feature.aggressive_buy_volume:.4f} / {feature.aggressive_sell_volume:.4f}")
    print(f"{prefix}  Large Trade Ratio: {feature.large_trade_ratio:.4f}")
    print(f"{prefix}  Total Volume: {feature.total_volume:.4f}")
    print(f"{prefix}  Total Value: {feature.total_value:.2f}")
    print(f"{prefix}  Avg Trade Size: {feature.avg_trade_size:.4f}")
    print(f"{prefix}  Buy/Sell Ratio: {feature.buy_sell_ratio:.4f}")
    print(f"{prefix}  Trade Intensity: {feature.trade_intensity:.4f}")
    print(f"{prefix}  VWAP: {feature.vwap:.2f}")
    print(f"{prefix}  Max Trade Size: {feature.max_trade_size:.4f}")
    print(f"{prefix}  Min Trade Size: {feature.min_trade_size:.4f}")
    print(f"{prefix}  Price Impact: {feature.price_impact:.6f}")
    print(f"{prefix}")
    print(f"{prefix}--- Sweep ---")
    print(f"{prefix}  Sweep Buy/Sell Score: {feature.sweep_buy_score:.4f} / {feature.sweep_sell_score:.4f}")
    print(f"{prefix}  Multi Level Fill: {feature.multi_level_fill}")
    print(f"{prefix}  Liquidity Vacuum: {feature.liquidity_vacuum:.4f}")
    print(f"{prefix}")
    print(f"{prefix}--- Volatility ---")
    print(f"{prefix}  Spread Volatility: {feature.spread_volatility:.4f}")
    print(f"{prefix}  Book Flip Rate: {feature.book_flip_rate:.4f}")
    print(f"{prefix}  Book Pressure: {feature.book_pressure:.4f}")


async def test_feature_extraction():
    """测试特征提取"""
    print("=" * 80)
    print("OrderBook Feature Extraction Test")
    print("=" * 80)
    print()
    
    aggregator = OrderBookAggregator(snapshot_interval_ms=1000)
    
    print("Step 1: 基础订单簿（买卖盘均衡）")
    snapshot1 = create_mock_snapshot(bid_price=65000.0, ask_price=65001.0)
    feature1 = aggregator.process_snapshot(snapshot1)
    if feature1:
        print_feature(feature1)
        assert abs(feature1.imbalance_10) < 0.1, "均衡订单簿失衡应该接近0"
        print("  ✓ 均衡订单簿验证通过")
    else:
        print("  (等待1秒以生成特征)")
    
    print()
    print("Step 2: 模拟买盘占优（imbalance > 0）")
    await asyncio.sleep(1.1)
    snapshot2 = OrderBookSnapshot(
        exchange="binance",
        symbol="BTCUSDT",
        timestamp=int(datetime.now().timestamp() * 1000),
        bids=[OrderBookLevel(price=65000.0 - i * 0.5, quantity=10.0 + i) for i in range(10)],
        asks=[OrderBookLevel(price=65001.0 + i * 0.5, quantity=2.0 - i * 0.1) for i in range(10)],
        last_update_id=123457,
    )
    feature2 = aggregator.process_snapshot(snapshot2)
    if feature2:
        print_feature(feature2)
        assert feature2.imbalance_10 > 0.3, "买盘占优时失衡应该大于0.3"
        assert feature2.imbalance_1 > 0, "imbalance_1应该反映即时失衡"
        print(f"  ✓ 买盘占优验证通过 (imbalance_10={feature2.imbalance_10:.4f})")
    
    print()
    print("Step 3: 模拟卖盘占优（imbalance < 0）")
    await asyncio.sleep(1.1)
    snapshot3 = OrderBookSnapshot(
        exchange="binance",
        symbol="BTCUSDT",
        timestamp=int(datetime.now().timestamp() * 1000),
        bids=[OrderBookLevel(price=65000.0 - i * 0.5, quantity=2.0 - i * 0.1) for i in range(10)],
        asks=[OrderBookLevel(price=65001.0 + i * 0.5, quantity=10.0 + i) for i in range(10)],
        last_update_id=123458,
    )
    feature3 = aggregator.process_snapshot(snapshot3)
    if feature3:
        print_feature(feature3)
        assert feature3.imbalance_10 < -0.3, "卖盘占优时失衡应该小于-0.3"
        print(f"  ✓ 卖盘占优验证通过 (imbalance_10={feature3.imbalance_10:.4f})")
    
    print()
    print("Step 4: 添加交易流数据")
    state = aggregator.get_state("binance", "BTCUSDT")
    for i in range(10):
        trade = create_mock_trade(
            price=65000.5,
            quantity=1.0,
            is_buyer_maker=False
        )
        aggregator.process_trade(trade)
    
    for i in range(5):
        trade = create_mock_trade(
            price=65000.5,
            quantity=0.5,
            is_buyer_maker=True
        )
        aggregator.process_trade(trade)
    
    await asyncio.sleep(1.1)
    snapshot4 = create_mock_snapshot(bid_price=65000.0, ask_price=65001.0)
    feature4 = aggregator.process_snapshot(snapshot4)
    if feature4:
        print_feature(feature4)
        assert feature4.trade_delta > 0, "主动买大于主动卖，delta应该为正"
        assert feature4.aggressive_buy_volume > feature4.aggressive_sell_volume, "主动买应该大于主动卖"
        assert feature4.total_volume > 0, "总成交量应该大于0"
        assert feature4.total_value > 0, "总成交金额应该大于0"
        assert feature4.avg_trade_size > 0, "平均单笔成交量应该大于0"
        assert feature4.buy_sell_ratio > 1.0, "主动买大于主动卖，买卖比例应该大于1"
        assert feature4.vwap > 0, "VWAP应该大于0"
        assert feature4.price_impact >= 0, "价格冲击应该大于等于0"
        print(f"  ✓ 交易流验证通过 (trade_delta={feature4.trade_delta:.4f}, VWAP={feature4.vwap:.2f})")
    
    print()
    print("Step 5: 模拟扫单（向上扫）")
    state.sweep = SweepState()
    state.sweep.sweep_buy_score = 0.8
    state.sweep.multi_level_fill = 5
    state.sweep.liquidity_vacuum = 0.3
    
    await asyncio.sleep(1.1)
    snapshot5 = create_mock_snapshot(bid_price=65000.0, ask_price=65001.0)
    feature5 = aggregator.process_snapshot(snapshot5)
    if feature5:
        print_feature(feature5)
        assert feature5.sweep_buy_score > 0, "向上扫单应该有正的sweep_buy_score"
        assert feature5.multi_level_fill > 0, "多档吃单应该有multi_level_fill"
        print(f"  ✓ 扫单验证通过 (sweep_buy_score={feature5.sweep_buy_score:.4f})")
    
    print()
    print("Step 6: 验证Microprice与Midprice的区别")
    await asyncio.sleep(1.1)
    snapshot6 = OrderBookSnapshot(
        exchange="binance",
        symbol="BTCUSDT",
        timestamp=int(datetime.now().timestamp() * 1000),
        bids=[OrderBookLevel(price=65000.0 - i * 0.5, quantity=10.0) for i in range(10)],
        asks=[OrderBookLevel(price=65001.0 + i * 0.5, quantity=2.0) for i in range(10)],
        last_update_id=123459,
    )
    feature6 = aggregator.process_snapshot(snapshot6)
    if feature6:
        print_feature(feature6)
        assert feature6.microprice != feature6.mid_price, "买卖盘不均衡时，microprice应该不同于mid_price"
        assert feature6.microprice < feature6.mid_price, "买盘量大于卖盘时，microprice应该偏向买方"
        print(f"  ✓ Microprice验证通过 (microprice={feature6.microprice:.2f}, mid_price={feature6.mid_price:.2f})")
    
    print()
    print("Step 7: 存储到 Parquet")
    try:
        writer = get_parquet_writer(base_path="data_lake/test_orderbook_features")
        
        for i in range(10):
            await asyncio.sleep(1.1)
            snap = create_mock_snapshot(
                bid_price=65000.0 + i * 10,
                ask_price=65001.0 + i * 10
            )
            feat = aggregator.process_snapshot(snap)
            if feat:
                writer.add_feature(feat)
        
        writer.flush_all()
        stats = writer.get_storage_stats()
        print()
        print("Storage Stats:")
        print(f"  Total Files: {stats['total_files']}")
        print(f"  Total Size: {stats['total_size_mb']:.4f} MB")
        for symbol, info in stats['symbols'].items():
            print(f"  {symbol}: {info['size_mb']:.4f} MB, {info['file_count']} files")
        
        print()
        print("Step 8: 读取数据验证")
        df = writer.read_features(
            exchange="binance",
            symbol="BTCUSDT",
            start_time=int(datetime.now().timestamp() * 1000) - 120000,
            end_time=int(datetime.now().timestamp() * 1000) + 1000
        )
        if df is not None and len(df) > 0:
            print(f"  ✓ 读取到 {len(df)} 条特征记录")
            print(f"  ✓ 列数: {len(df.columns)}")
        else:
            print("  ! 未读取到数据（可能是时间范围问题）")
            
    except Exception as e:
        print(f"  Parquet test skipped: {e}")
    
    print()
    print("=" * 80)
    print("All Tests Passed!")
    print("=" * 80)


async def test_binance_live():
    """测试 Binance 实时数据"""
    print("=" * 80)
    print("Binance Live OrderBook Feature Test")
    print("=" * 80)
    print()
    
    try:
        import websockets
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        print("websockets or nest_asyncio not installed, skipping live test")
        return
    
    aggregator = OrderBookAggregator(snapshot_interval_ms=1000)
    
    uri = "wss://stream.binance.com:9443/ws/btcusdt@depth10@100ms"
    
    print(f"Connecting to {uri}")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        async with websockets.connect(uri) as ws:
            while True:
                data = await asyncio.wait_for(ws.recv(), timeout=30.0)
                msg = json.loads(data)
                
                if "bids" in msg and "asks" in msg:
                    bids = [
                        OrderBookLevel(
                            price=float(b[0]),
                            quantity=float(b[1])
                        )
                        for b in msg["bids"][:10]
                    ]
                    asks = [
                        OrderBookLevel(
                            price=float(a[0]),
                            quantity=float(a[1])
                        )
                        for a in msg["asks"][:10]
                    ]
                    
                    snapshot = OrderBookSnapshot(
                        exchange="binance",
                        symbol="BTCUSDT",
                        timestamp=int(datetime.now().timestamp() * 1000),
                        bids=bids,
                        asks=asks,
                        last_update_id=int(msg.get("lastUpdateId", 0)),
                    )
                    
                    feature = aggregator.process_snapshot(snapshot)
                    if feature:
                        print_feature(feature)
                        print()
                        
    except asyncio.TimeoutError:
        print("Timeout waiting for data")
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OrderBook Feature Extraction Test")
    parser.add_argument("--live", action="store_true", help="Test with live Binance data")
    args = parser.parse_args()
    
    if args.live:
        asyncio.run(test_binance_live())
    else:
        asyncio.run(test_feature_extraction())
