#!/usr/bin/env python3
"""
完整的 Order Book 特征生成器

基于 Trade + K 线数据生成以下特征：
- Spread / Mid Price / VWAP
- Buy/Sell Volume / Imbalance
- Cumulative Depth (Top N)
- Potential Order Wall Height
- Order Flow Volatility
- Price Impact Proxy
- Depth Slope / Shape
- Top N Price Levels
- Liquidity Ratio
- Bid/Ask Pressure
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aggregation_service.publishers.parquet_writer import get_parquet_writer


class OrderBookFeatureGenerator:
    """基于Trade+K线生成OrderBook特征"""
    
    def __init__(self, output_path: str = "data_lake/orderbook_features"):
        self.writer = get_parquet_writer(base_path=output_path)
    
    def load_trades(self, symbol: str, year: int, month: int) -> pd.DataFrame:
        """加载Trades数据"""
        trades_path = Path(__file__).parent.parent / "data_lake" / "crypto" / "binance" / "trades"
        path = trades_path / f"symbol={symbol}" / f"year={year}" / f"month={str(month).zfill(2)}" / "data.parquet"
        
        if not path.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(path)
        df['datetime'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('datetime').reset_index(drop=True)
        return df
    
    def load_klines(self, symbol: str, year: int, month: int) -> pd.DataFrame:
        """加载K线数据"""
        klines_path = Path(__file__).parent.parent / "data_lake" / "crypto" / "binance" / "klines"
        path = klines_path / f"symbol={symbol}" / f"year={year}" / f"month={str(month).zfill(2)}" / "data.parquet"
        
        if not path.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(path)
        df['datetime'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('datetime').reset_index(drop=True)
        return df
    
    def calculate_features(self, trades_df: pd.DataFrame, klines_df: pd.DataFrame = None, window_seconds: int = 60):
        """计算所有特征"""
        
        if len(trades_df) == 0:
            return pd.DataFrame()
        
        features = []
        cumulative_delta = 0
        
        # 设置时间窗口
        trades_df['window'] = trades_df['datetime'].dt.floor(f'{window_seconds}S')
        
        for window_start, group in trades_df.groupby('window'):
            # === 基础特征 ===
            buy_trades = group[~group['is_buyer_maker']]
            sell_trades = group[group['is_buyer_maker']]
            
            buy_volume = buy_trades['qty'].sum()
            sell_volume = sell_trades['qty'].sum()
            total_volume = buy_volume + sell_volume
            
            buy_value = buy_trades['quote_qty'].sum()
            sell_value = sell_trades['quote_qty'].sum()
            total_value = buy_value + sell_value
            
            trade_delta = buy_volume - sell_volume
            cumulative_delta += trade_delta
            
            # VWAP
            vwap = total_value / total_volume if total_volume > 0 else group['price'].mean()
            
            # === Spread 和 Mid Price (基于K线或Trade估算) ===
            if klines_df is not None and len(klines_df) > 0:
                klines_window = klines_df[
                    (klines_df['datetime'] >= window_start) & 
                    (klines_df['datetime'] < window_start + timedelta(seconds=window_seconds))
                ]
                if len(klines_window) > 0:
                    mid_price = (klines_window['high'].mean() + klines_window['low'].mean()) / 2
                    spread = klines_window['high'].max() - klines_window['low'].min()
                else:
                    mid_price = vwap
                    spread = vwap * 0.0001
            else:
                mid_price = vwap
                spread = vwap * 0.0001
            
            spread_pct = spread / mid_price if mid_price > 0 else 0
            
            # === Imbalance ===
            imbalance = trade_delta / total_volume if total_volume > 0 else 0
            
            # === Liquidity Ratio ===
            liquidity_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
            
            # === Bid/Ask Pressure ===
            bid_pressure = buy_volume / total_volume if total_volume > 0 else 0.5
            ask_pressure = 1 - bid_pressure
            
            # === Order Flow Volatility ===
            price_std = group['price'].std() if len(group) > 1 else 0
            volume_std = group['qty'].std() if len(group) > 1 else 0
            order_flow_volatility = price_std * volume_std if price_std > 0 and volume_std > 0 else 0
            
            # === Price Impact Proxy ===
            price_impact_proxy = price_std / mid_price if mid_price > 0 else 0
            
            # === Cumulative Depth (Top N 估算) ===
            # 根据价格分布估算top档量
            price_bins = pd.cut(group['price'], bins=20)
            price_dist = group.groupby(price_bins)['qty'].sum()
            top5_bid_volume = price_dist.head(5).sum()
            top5_ask_volume = price_dist.tail(5).sum()
            
            # === Depth Slope ===
            if len(price_dist) > 2:
                prices = price_dist.index.map(lambda x: x.mid)
                depth_slope = np.polyfit(prices, price_dist.values, 1)[0]
            else:
                depth_slope = 0
            
            # === Potential Order Wall Height ===
            max_bin_volume = price_dist.max() if len(price_dist) > 0 else 0
            avg_bin_volume = price_dist.mean() if len(price_dist) > 0 else 0
            order_wall_height = max_bin_volume if max_bin_volume > avg_bin_volume * 2 else 0
            
            # === Top N Price Levels ===
            top_bid_price = group['price'].min()
            top_ask_price = group['price'].max()
            
            # === 大单统计 ===
            large_trades = group[group['quote_qty'] >= 10000]
            large_trade_ratio = len(large_trades) / len(group) if len(group) > 0 else 0
            
            # === 交易强度 ===
            trade_intensity = len(group) / window_seconds
            
            feature = {
                # 基础元数据
                'timestamp': int(window_start.timestamp() * 1000),
                'exchange': 'binance',
                'symbol': trades_df['symbol'].iloc[0] if 'symbol' in trades_df.columns else 'BTCUSDT',
                'window_seconds': window_seconds,
                
                # Top-of-Book
                'spread': spread,
                'spread_pct': spread_pct,
                'mid_price': mid_price,
                'vwap': vwap,
                
                # Volume
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'total_volume': total_volume,
                'total_value': total_value,
                
                # Imbalance
                'imbalance': imbalance,
                'trade_delta': trade_delta,
                'cumulative_delta': cumulative_delta,
                
                # Liquidity
                'liquidity_ratio': liquidity_ratio,
                'bid_pressure': bid_pressure,
                'ask_pressure': ask_pressure,
                
                # Volatility
                'order_flow_volatility': order_flow_volatility,
                'price_std': price_std,
                'volume_std': volume_std,
                
                # Price Impact
                'price_impact_proxy': price_impact_proxy,
                
                # Depth (Top N)
                'top5_bid_volume': top5_bid_volume,
                'top5_ask_volume': top5_ask_volume,
                'depth_slope': depth_slope,
                
                # Order Wall
                'potential_order_wall_height': order_wall_height,
                'top_bid_price': top_bid_price,
                'top_ask_price': top_ask_price,
                
                # Trade Stats
                'num_trades': len(group),
                'avg_trade_size': total_volume / len(group) if len(group) > 0 else 0,
                'large_trade_ratio': large_trade_ratio,
                'trade_intensity': trade_intensity,
            }
            
            features.append(feature)
        
        return pd.DataFrame(features)
    
    def process_month(self, symbol: str, year: int, month: int, window_seconds: int = 60):
        """处理单个月份的数据"""
        print(f"\n处理: {symbol} {year}-{month:02d}")
        
        trades_df = self.load_trades(symbol, year, month)
        klines_df = self.load_klines(symbol, year, month)
        
        if len(trades_df) == 0:
            print(f"  ❌ 未找到Trades数据")
            return
        
        print(f"  ✅ 加载了 {len(trades_df):,} 条交易记录")
        
        features_df = self.calculate_features(trades_df, klines_df, window_seconds)
        
        if len(features_df) == 0:
            print(f"  ❌ 未生成特征")
            return
        
        print(f"  ✅ 生成了 {len(features_df):,} 条特征记录")
        
        # 保存特征
        for _, row in features_df.iterrows():
            self.writer.add_feature(row.to_dict())
        
        self.writer.flush_all()
        
        # 统计信息
        stats = self.writer.get_storage_stats()
        print(f"  📊 当前存储: {stats['total_size_mb']:.2f} MB")
    
    def run(self, symbols: list, years: list, window_seconds: int = 60):
        """运行完整的特征生成流程"""
        print("=" * 80)
        print("Order Book 特征生成器")
        print(f"交易对: {symbols}")
        print(f"年份: {years}")
        print(f"时间窗口: {window_seconds}秒")
        print("=" * 80)
        
        for symbol in symbols:
            for year in years:
                for month in range(1, 13):
                    self.process_month(symbol, year, month, window_seconds)
        
        print("\n" + "=" * 80)
        print("特征生成完成！")
        print("=" * 80)
        
        stats = self.writer.get_storage_stats()
        print("\n最终存储统计:")
        print(f"  总文件数: {stats['total_files']}")
        print(f"  总大小: {stats['total_size_mb']:.2f} MB")
        for symbol, info in stats['symbols'].items():
            print(f"  {symbol}: {info['size_mb']:.2f} MB, {info['file_count']} files")


def main():
    parser = argparse.ArgumentParser(description="基于Trade+K线生成OrderBook特征")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT", "ETHUSDT"],
        help="交易对列表"
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2024, 2025],
        help="年份列表"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=60,
        help="时间窗口（秒）"
    )
    
    args = parser.parse_args()
    
    generator = OrderBookFeatureGenerator()
    generator.run(args.symbols, args.years, args.window)


if __name__ == "__main__":
    main()
