#!/usr/bin/env python3
"""
从已下载的 Binance Trades 数据提取特征
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
from tqdm import tqdm
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aggregation_service.publishers.parquet_writer import get_parquet_writer


class TradeFeatureExtractor:
    """从Trades数据提取特征"""
    
    def __init__(self, trades_root: Path = None, output_root: Path = None):
        if trades_root is None:
            trades_root = Path(__file__).parent.parent / "data_lake" / "crypto" / "binance" / "trades"
        
        if output_root is None:
            output_root = Path(__file__).parent.parent / "data_lake" / "orderbook_features"
        
        self.trades_root = trades_root
        self.writer = get_parquet_writer(base_path=str(output_root))
    
    def load_trades_for_symbol(self, symbol: str, year: int, month: int) -> pd.DataFrame:
        """加载指定交易对的Trades数据"""
        month_str = f"{month:02d}"
        data_path = self.trades_root / f"symbol={symbol}" / f"year={year}" / f"month={month_str}" / "data.parquet"
        
        if not data_path.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(data_path)
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df
    
    def extract_features_from_trades(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """从Trades数据提取特征（1秒频率）"""
        
        if len(df) == 0:
            return pd.DataFrame()
        
        df['datetime'] = pd.to_datetime(df['timestamp'])
        df['second'] = df['datetime'].dt.floor('s')
        
        features_list = []
        
        # 累积量
        cumulative_delta = 0
        cumulative_buy_volume = 0
        cumulative_sell_volume = 0
        
        grouped = df.groupby('second')
        
        for second, group in tqdm(grouped, desc=f"处理 {symbol}", leave=False):
            # 基础统计
            buy_trades = group[~group['is_buyer_maker']]
            sell_trades = group[group['is_buyer_maker']]
            
            buy_volume = buy_trades['qty'].sum()
            sell_volume = sell_trades['qty'].sum()
            
            buy_value = buy_trades['quote_qty'].sum()
            sell_value = sell_trades['quote_qty'].sum()
            
            total_volume = buy_volume + sell_volume
            total_value = buy_value + sell_value
            trade_delta = buy_volume - sell_volume
            
            cumulative_delta += trade_delta
            cumulative_buy_volume += buy_volume
            cumulative_sell_volume += sell_volume
            
            # VWAP
            vwap = total_value / total_volume if total_volume > 0 else group['price'].mean()
            
            # 单统计
            num_trades = len(group)
            avg_trade_size = total_volume / num_trades if num_trades > 0 else 0
            
            max_trade_size = group['qty'].max()
            min_trade_size = group['qty'].min()
            
            # 大单统计 (>10,000 USD)
            large_trades = group[group['quote_qty'] >= 10000]
            large_trade_ratio = len(large_trades) / num_trades if num_trades > 0 else 0
            
            # 买卖比例
            buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
            
            # 价格波动
            price_std = group['price'].std() if len(group) > 1 else 0
            price_mean = group['price'].mean()
            price_impact = price_std / price_mean if price_mean > 0 else 0
            
            # 价格估算（基于VWAP）
            best_bid = vwap * (0.9999 if trade_delta <= 0 else 1.0)
            best_ask = vwap * (1.0001 if trade_delta >= 0 else 1.0)
            spread = best_ask - best_bid
            spread_pct = spread / vwap if vwap > 0 else 0
            
            # 估算订单簿失衡（基于成交流向）
            imbalance_1 = trade_delta / total_volume if total_volume > 0 else 0
            imbalance_5 = imbalance_1
            imbalance_10 = imbalance_1
            
            # 估算深度
            depth_ratio = buy_sell_ratio if sell_volume > 0 else 1.0
            book_pressure = imbalance_1 * total_volume
            
            # 交易强度
            time_span = (group['timestamp'].max() - group['timestamp'].min()).total_seconds()
            if time_span > 0:
                trade_velocity = num_trades / time_span
                trade_intensity = total_volume / time_span
            else:
                trade_velocity = num_trades
                trade_intensity = 0
            
            features = {
                # 基础元数据
                'timestamp': int(second.timestamp() * 1000),
                'exchange': 'binance',
                'symbol': symbol,
                
                # Top-of-Book（估算）
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_pct': spread_pct,
                'mid_price': vwap,
                'microprice': vwap,
                'best_bid_size': buy_volume,
                'best_ask_size': sell_volume,
                
                # Imbalance（基于成交流向）
                'imbalance_1': imbalance_1,
                'imbalance_5': imbalance_5,
                'imbalance_10': imbalance_10,
                'imbalance_slope': 0.0,
                
                # Depth（估算）
                'top5_bid_volume': buy_volume,
                'top5_ask_volume': sell_volume,
                'top10_bid_volume': buy_volume,
                'top10_ask_volume': sell_volume,
                'depth_ratio': depth_ratio,
                'depth_change': 0.0,
                
                # Trade Flow
                'trade_delta': trade_delta,
                'cumulative_delta': cumulative_delta,
                'aggressive_buy_volume': buy_volume,
                'aggressive_sell_volume': sell_volume,
                'large_trade_ratio': large_trade_ratio,
                'trade_velocity': trade_velocity,
                'total_volume': total_volume,
                'total_value': total_value,
                'avg_trade_size': avg_trade_size,
                'buy_sell_ratio': buy_sell_ratio,
                'trade_intensity': trade_intensity,
                'vwap': vwap,
                'max_trade_size': max_trade_size,
                'min_trade_size': min_trade_size,
                'price_impact': price_impact,
                
                # Sweep（暂不计算）
                'sweep_buy_score': 0.0,
                'sweep_sell_score': 0.0,
                'multi_level_fill': 0,
                'liquidity_vacuum': 0.0,
                
                # Volatility（基于成交价格）
                'spread_volatility': 0.0,
                'quote_update_rate': 0.0,
                'cancel_rate': 0.0,
                'book_flip_rate': 0.0,
                'book_pressure': book_pressure,
            }
            
            features_list.append(features)
        
        return pd.DataFrame(features_list)
    
    def process_symbol(self, symbol: str, years: list):
        """处理单个交易对"""
        print(f"\n{'=' * 80}")
        print(f"处理交易对: {symbol}")
        print(f"{'=' * 80}")
        
        for year in years:
            for month in range(1, 13):
                print(f"\n处理: {symbol} {year}-{month:02d}")
                
                df = self.load_trades_for_symbol(symbol, year, month)
                
                if len(df) == 0:
                    print(f"  未找到数据，跳过")
                    continue
                
                print(f"  加载了 {len(df):,} 条交易记录")
                
                features_df = self.extract_features_from_trades(df, symbol)
                
                if len(features_df) > 0:
                    print(f"  提取了 {len(features_df):,} 条特征")
                    
                    for _, row in features_df.iterrows():
                        self.writer.add_feature(row.to_dict())
                    
                    self.writer.flush_all()
                    
                    stats = self.writer.get_storage_stats()
                    print(f"  当前存储统计:")
                    print(f"    总文件数: {stats['total_files']}")
                    print(f"    总大小: {stats['total_size_mb']:.2f} MB")
                    for sym, info in stats['symbols'].items():
                        print(f"    {sym}: {info['size_mb']:.2f} MB, {info['file_count']} files")
    
    def get_storage_stats(self):
        """获取存储统计"""
        return self.writer.get_storage_stats()


def main():
    parser = argparse.ArgumentParser(description="从Binance Trades数据提取特征")
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
        default=[2024, 2025, 2026],
        help="年份列表"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Binance Trades 特征提取")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print("=" * 80)
    
    extractor = TradeFeatureExtractor()
    
    for symbol in args.symbols:
        extractor.process_symbol(symbol, args.years)
    
    print("\n" + "=" * 80)
    print("提取完成！")
    print("=" * 80)
    
    stats = extractor.get_storage_stats()
    print("\n最终存储统计:")
    print(f"  总文件数: {stats['total_files']}")
    print(f"  总大小: {stats['total_size_mb']:.2f} MB")
    for symbol, info in stats['symbols'].items():
        print(f"  {symbol}: {info['size_mb']:.2f} MB, {info['file_count']} files")


if __name__ == "__main__":
    main()
