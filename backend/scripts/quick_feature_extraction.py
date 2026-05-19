#!/usr/bin/env python3
"""
快速测试：从Trades数据提取特征并生成OrderBook特征
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aggregation_service.publishers.parquet_writer import get_parquet_writer


def main():
    print("=" * 80)
    print("Trade特征提取 + OrderBook特征生成")
    print("=" * 80)
    
    # 加载Trades数据
    trades_path = Path(__file__).parent.parent / "data_lake" / "crypto" / "binance" / "trades" / "symbol=BTCUSDT" / "year=2024" / "month=01" / "data.parquet"
    
    if not trades_path.exists():
        print(f"错误：未找到Trades数据: {trades_path}")
        return
    
    print(f"\n加载数据: {trades_path}")
    df = pd.read_parquet(trades_path)
    print(f"原始数据记录数: {len(df):,}")
    print(f"数据列: {df.columns.tolist()}")
    
    # 预处理
    df['datetime'] = pd.to_datetime(df['timestamp'])
    df['second'] = df['datetime'].dt.floor('s')
    
    # 计算每秒特征
    print("\n计算每秒特征...")
    
    features_list = []
    cumulative_delta = 0
    
    grouped = df.groupby('second')
    
    for idx, (second, group) in enumerate(grouped):
        # 主动买卖量
        buy_trades = group[~group['is_buyer_maker']]
        sell_trades = group[group['is_buyer_maker']]
        
        buy_volume = buy_trades['qty'].sum()
        sell_volume = sell_trades['qty'].sum()
        trade_delta = buy_volume - sell_volume
        cumulative_delta += trade_delta
        
        # 金额
        buy_value = buy_trades['quote_qty'].sum()
        sell_value = sell_trades['quote_qty'].sum()
        total_volume = buy_volume + sell_volume
        total_value = buy_value + sell_value
        
        # VWAP
        vwap = total_value / total_volume if total_volume > 0 else group['price'].mean()
        
        # 统计
        num_trades = len(group)
        avg_trade_size = total_volume / num_trades if num_trades > 0 else 0
        
        # 大单
        large_trades = group[group['quote_qty'] >= 10000]
        large_trade_ratio = len(large_trades) / num_trades if num_trades > 0 else 0
        
        # 买卖比例
        buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
        
        # 估算OrderBook特征
        best_bid = vwap * 0.9999 if trade_delta <= 0 else vwap
        best_ask = vwap * 1.0001 if trade_delta >= 0 else vwap
        spread = best_ask - best_bid
        spread_pct = spread / vwap if vwap > 0 else 0
        
        imbalance_1 = trade_delta / total_volume if total_volume > 0 else 0
        depth_ratio = buy_sell_ratio
        
        features = {
            'timestamp': int(second.timestamp() * 1000),
            'exchange': 'binance',
            'symbol': 'BTCUSDT',
            
            # Top-of-Book（估算）
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': spread,
            'spread_pct': spread_pct,
            'mid_price': vwap,
            'microprice': vwap,
            'best_bid_size': buy_volume,
            'best_ask_size': sell_volume,
            
            # Imbalance
            'imbalance_1': imbalance_1,
            'imbalance_5': imbalance_1,
            'imbalance_10': imbalance_1,
            
            # Depth
            'top5_bid_volume': buy_volume,
            'top5_ask_volume': sell_volume,
            'depth_ratio': depth_ratio,
            
            # Trade Flow
            'trade_delta': trade_delta,
            'cumulative_delta': cumulative_delta,
            'aggressive_buy_volume': buy_volume,
            'aggressive_sell_volume': sell_volume,
            'vwap': vwap,
            'large_trade_ratio': large_trade_ratio,
            'buy_sell_ratio': buy_sell_ratio,
            'total_volume': total_volume,
            'total_value': total_value,
            'avg_trade_size': avg_trade_size,
            'num_trades': num_trades,
        }
        
        features_list.append(features)
        
        if idx % 10000 == 0 and idx > 0:
            print(f"  已处理 {idx:,} 秒...")
    
    features_df = pd.DataFrame(features_list)
    print(f"\n特征提取完成！")
    print(f"  特征记录数: {len(features_df):,}")
    print(f"  特征列数: {len(features_df.columns)}")
    
    # 保存到Parquet
    output_path = Path(__file__).parent.parent / "data_lake" / "orderbook_features"
    writer = get_parquet_writer(base_path=str(output_path))
    
    for _, row in features_df.iterrows():
        writer.add_feature(row.to_dict())
    
    writer.flush_all()
    
    stats = writer.get_storage_stats()
    print(f"\n存储完成！")
    print(f"  总文件数: {stats['total_files']}")
    print(f"  总大小: {stats['total_size_mb']:.2f} MB")
    
    # 输出样本数据
    print("\n样本特征数据:")
    sample = features_df.head(5)[[
        'timestamp', 'mid_price', 'spread', 'spread_pct',
        'imbalance_1', 'trade_delta', 'vwap', 'buy_sell_ratio'
    ]]
    print(sample.to_string(index=False))
    
    # 输出统计信息
    print("\n特征统计摘要:")
    print(f"  时间范围: {features_df['timestamp'].min()} ~ {features_df['timestamp'].max()}")
    print(f"  平均点差: {features_df['spread'].mean():.2f}")
    print(f"  平均Imbalance: {features_df['imbalance_1'].mean():.4f}")
    print(f"  平均VWAP: {features_df['vwap'].mean():.2f}")
    print(f"  总成交: {features_df['total_volume'].sum():,.2f} BTC")
    print(f"  总金额: ${features_df['total_value'].sum():,.2f}")


if __name__ == "__main__":
    main()
