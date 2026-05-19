#!/usr/bin/env python3
"""
Batch OrderBook Feature Extraction - 历史数据处理

从Binance API获取历史成交数据，重构简化的订单簿状态，提取特征

注意：Binance不提供历史订单簿数据，此脚本通过历史成交数据来：
1. 计算成交流特征（Trade Flow）
2. 模拟订单簿失衡（基于成交方向）
3. 提取相关特征

使用方法:
    python scripts/batch_extract_orderbook_features.py --symbol BTCUSDT --start-date 2024-01-01
"""

import asyncio
import aiohttp
import json
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aggregation_service.publishers.parquet_writer import (
    get_parquet_writer,
)


class BinanceHistoricalCollector:
    """Binance历史数据采集器"""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(
        self,
        symbol: str,
        output_path: str = "data_lake/orderbook_features"
    ):
        self.symbol = symbol.upper()
        self.output_path = output_path
        self.writer = None
    
    async def initialize(self):
        """初始化"""
        try:
            self.writer = get_parquet_writer(base_path=self.output_path)
            print(f"Initialized parquet writer at: {self.output_path}")
        except Exception as e:
            print(f"Failed to initialize parquet writer: {e}")
            raise
    
    async def fetch_historical_trades(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """获取历史成交数据"""
        print(f"\nFetching historical trades from {start_date.date()} to {end_date.date()}")
        
        all_trades = []
        start_time = int(start_date.timestamp() * 1000)
        end_time = int(end_date.timestamp() * 1000)
        
        session = aiohttp.ClientSession()
        
        try:
            while start_time < end_time:
                url = f"{self.BASE_URL}/api/v3/myTrades"
                params = {
                    'symbol': self.symbol,
                    'startTime': start_time,
                    'endTime': end_time,
                    'limit': 1000
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data:
                            break
                        
                        for trade in data:
                            all_trades.append({
                                'timestamp': trade['time'],
                                'trade_id': trade['tradeId'],
                                'price': float(trade['price']),
                                'qty': float(trade['qty']),
                                'quote_qty': float(trade['quoteQty']),
                                'is_buyer_maker': trade['isBuyerMaker'],
                                'is_buy': not trade['isBuyerMaker'],
                            })
                        
                        start_time = data[-1]['time'] + 1
                        
                        print(f"  Fetched {len(all_trades)} trades so far...")
                        
                    elif response.status == 429:
                        print("  Rate limited, waiting...")
                        await asyncio.sleep(60)
                    else:
                        print(f"  Error: {response.status}")
                        break
        
        finally:
            await session.close()
        
        df = pd.DataFrame(all_trades)
        if len(df) > 0:
            df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"  Total trades fetched: {len(df)}")
        return df
    
    def calculate_trade_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """从成交数据计算交易特征"""
        print("\nCalculating trade features...")
        
        if len(df) == 0:
            return pd.DataFrame()
        
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['second'] = df['datetime'].dt.floor('s')
        
        features = []
        
        for second, group in df.groupby('second'):
            buy_volume = group[group['is_buy']]['qty'].sum()
            sell_volume = group[~group['is_buy']]['qty'].sum()
            
            total_volume = buy_volume + sell_volume
            trade_delta = buy_volume - sell_volume
            
            buy_value = group[group['is_buy']]['quote_qty'].sum()
            sell_value = group[~group['is_buy']]['quote_qty'].sum()
            
            total_value = buy_value + sell_value
            vwap = total_value / total_volume if total_volume > 0 else 0
            
            num_trades = len(group)
            avg_trade_size = total_volume / num_trades if num_trades > 0 else 0
            
            max_trade_size = group['qty'].max()
            min_trade_size = group['qty'].min()
            
            large_trades = group[group['quote_qty'] >= 10000]
            large_trade_ratio = len(large_trades) / num_trades if num_trades > 0 else 0
            
            buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
            
            price_std = group['price'].std() if len(group) > 1 else 0
            price_impact = price_std / group['price'].mean() if len(group) > 0 and group['price'].mean() > 0 else 0
            
            features.append({
                'timestamp': int(second.timestamp() * 1000),
                'datetime': second,
                'exchange': 'binance',
                'symbol': self.symbol,
                
                'total_volume': total_volume,
                'total_value': total_value,
                'vwap': vwap,
                'avg_trade_size': avg_trade_size,
                'num_trades': num_trades,
                
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'trade_delta': trade_delta,
                'buy_sell_ratio': buy_sell_ratio,
                
                'max_trade_size': max_trade_size,
                'min_trade_size': min_trade_size,
                'large_trade_ratio': large_trade_ratio,
                'price_impact': price_impact,
                
                'bid_volume': buy_volume,
                'ask_volume': sell_volume,
                'imbalance_1': trade_delta / total_volume if total_volume > 0 else 0,
                
                'trade_velocity': num_trades,
            })
        
        features_df = pd.DataFrame(features)
        print(f"  Features calculated: {len(features_df)}")
        
        return features_df
    
    async def process_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ):
        """处理日期范围"""
        print("=" * 80)
        print("Batch OrderBook Feature Extraction")
        print("=" * 80)
        print(f"Symbol: {self.symbol}")
        print(f"Date Range: {start_date.date()} to {end_date.date()}")
        
        df = await self.fetch_historical_trades(start_date, end_date)
        
        if len(df) == 0:
            print("No trades found for the specified date range.")
            return
        
        features_df = self.calculate_trade_features(df)
        
        if len(features_df) > 0:
            print(f"\nSaving features to parquet...")
            
            for _, row in features_df.iterrows():
                feature_dict = {
                    'timestamp': row['timestamp'],
                    'datetime': row['datetime'],
                    'exchange': row['exchange'],
                    'symbol': row['symbol'],
                    
                    'best_bid': row['vwap'] if row['trade_delta'] >= 0 else row['vwap'] * 0.9999,
                    'best_ask': row['vwap'] if row['trade_delta'] <= 0 else row['vwap'] * 1.0001,
                    'spread': row['vwap'] * 0.0001 if abs(row['trade_delta']) > 0 else 0,
                    'spread_pct': 0.0001,
                    'mid_price': row['vwap'],
                    'microprice': row['vwap'],
                    
                    'imbalance_1': row['imbalance_1'],
                    'imbalance_5': row['imbalance_1'],
                    'imbalance_10': row['imbalance_1'],
                    'imbalance_slope': 0.0,
                    
                    'top5_bid_volume': row['bid_volume'],
                    'top5_ask_volume': row['ask_volume'],
                    'top10_bid_volume': row['bid_volume'],
                    'top10_ask_volume': row['ask_volume'],
                    'depth_ratio': row['buy_sell_ratio'] if row['sell_volume'] > 0 else 1.0,
                    'depth_change': 0.0,
                    
                    'trade_delta': row['trade_delta'],
                    'cumulative_delta': 0.0,
                    'aggressive_buy_volume': row['buy_volume'],
                    'aggressive_sell_volume': row['sell_volume'],
                    'large_trade_ratio': row['large_trade_ratio'],
                    'trade_velocity': row['trade_velocity'],
                    'total_volume': row['total_volume'],
                    'total_value': row['total_value'],
                    'avg_trade_size': row['avg_trade_size'],
                    'buy_sell_ratio': row['buy_sell_ratio'],
                    'trade_intensity': 0.0,
                    'vwap': row['vwap'],
                    'max_trade_size': row['max_trade_size'],
                    'min_trade_size': row['min_trade_size'],
                    'price_impact': row['price_impact'],
                    
                    'sweep_buy_score': 0.0,
                    'sweep_sell_score': 0.0,
                    'multi_level_fill': 0,
                    'liquidity_vacuum': 0.0,
                    
                    'spread_volatility': 0.0,
                    'quote_update_rate': 0.0,
                    'cancel_rate': 0.0,
                    'book_flip_rate': 0.0,
                    'book_pressure': row['imbalance_1'] * row['total_volume'],
                }
                
                self.writer.add_feature(feature_dict)
            
            self.writer.flush_all()
            
            stats = self.writer.get_storage_stats()
            print(f"\nStorage Stats:")
            print(f"  Total Files: {stats['total_files']}")
            print(f"  Total Size: {stats['total_size_mb']:.2f} MB")
            for symbol, info in stats['symbols'].items():
                print(f"  {symbol}: {info['size_mb']:.2f} MB, {info['file_count']} files")
        
        print("\nProcessing complete!")


async def main():
    parser = argparse.ArgumentParser(
        description="Extract orderbook features from historical Binance trades"
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTCUSDT',
        help='Trading symbol (default: BTCUSDT)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data_lake/orderbook_features',
        help='Output path for parquet files'
    )
    
    args = parser.parse_args()
    
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    collector = BinanceHistoricalCollector(
        symbol=args.symbol,
        output_path=args.output
    )
    
    await collector.initialize()
    await collector.process_date_range(start_date, end_date)


if __name__ == "__main__":
    asyncio.run(main())
