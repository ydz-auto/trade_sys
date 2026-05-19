#!/usr/bin/env python3
"""
快速生成一个月的特征用于测试
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("📊 生成一个月的特征用于测试")
print("=" * 80)

# 加载Trades数据
trades_path = Path("data_lake/crypto/binance/trades/symbol=BTCUSDT/year=2024/month=01/data.parquet")
print(f"\n📂 加载Trades数据: {trades_path}")

if not trades_path.exists():
    print("❌ Trades文件不存在")
    exit(1)

trades_df = pd.read_parquet(trades_path)
print(f"✅ 加载完成，{len(trades_df):,}条记录")
print(f"   时间范围: {trades_df['datetime'].min()} ~ {trades_df['datetime'].max()}")

# 计算特征
print(f"\n🔧 开始计算特征...")

features = []
cumulative_delta = 0

window_seconds = 60  # 60秒窗口
trades_df['window'] = trades_df['datetime'].dt.floor(f'{window_seconds}S')

total_groups = trades_df['window'].nunique()
print(f"   总时间窗口数: {total_groups:,}")

for idx, (window_start, group) in enumerate(trades_df.groupby('window')):
    buy_trades = group[~group['is_buyer_maker']
    sell_trades = group[group['is_buyer_maker']]
    
    buy_volume = buy_trades['qty'].sum()
    sell_volume = sell_trades['qty'].sum()
    total_volume = buy_volume + sell_volume
    
    buy_value = buy_trades['quote_qty'].sum()
    sell_value = sell_trades['quote_qty'].sum()
    total_value = buy_value + sell_value
    
    trade_delta = buy_volume - sell_volume
    cumulative_delta += trade_delta
    
    vwap = total_value / total_volume if total_volume > 0 else group['price'].mean()
    
    mid_price = vwap
    spread = vwap * 0.0001
    spread_pct = spread / mid_price if mid_price > 0 else 0
    
    imbalance = trade_delta / total_volume if total_volume > 0 else 0
    
    liquidity_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
    
    bid_pressure = buy_volume / total_volume if total_volume > 0 else 0.5
    ask_pressure = 1 - bid_pressure
    
    price_std = group['price'].std() if len(group) > 1 else 0
    volume_std = group['qty'].std() if len(group) > 1 else 0
    order_flow_volatility = price_std * volume_std if price_std > 0 and volume_std > 0 else 0
    
    price_impact_proxy = price_std / mid_price if mid_price > 0 else 0
    
    large_trades = group[group['quote_qty'] >= 10000]
    large_trade_ratio = len(large_trades) / len(group) if len(group) > 0 else 0
    
    trade_intensity = len(group) / window_seconds
    
    feature = {
        'timestamp': int(window_start.timestamp() * 1000),
        'datetime': window_start,
        'exchange': 'binance',
        'symbol': 'BTCUSDT',
        'window_seconds': window_seconds,
        
        'spread': spread,
        'spread_pct': spread_pct,
        'mid_price': mid_price,
        'vwap': vwap,
        
        'buy_volume': buy_volume,
        'sell_volume': sell_volume,
        'total_volume': total_volume,
        'total_value': total_value,
        
        'imbalance': imbalance,
        'trade_delta': trade_delta,
        'cumulative_delta': cumulative_delta,
        
        'liquidity_ratio': liquidity_ratio,
        'bid_pressure': bid_pressure,
        'ask_pressure': ask_pressure,
        
        'order_flow_volatility': order_flow_volatility,
        'price_std': price_std,
        'volume_std': volume_std,
        
        'price_impact_proxy': price_impact_proxy,
        
        'num_trades': len(group),
        'avg_trade_size': total_volume / len(group) if len(group) > 0 else 0,
        'large_trade_ratio': large_trade_ratio,
        'trade_intensity': trade_intensity,
    }
    
    features.append(feature)
    
    if (idx + 1) % 5000 == 0:
        print(f"   进度: {idx + 1}/{total_groups} ({(idx+1)/total_groups*100:.1f}%")

features_df = pd.DataFrame(features)
print(f"✅ 特征计算完成，{len(features_df):,}条记录")

# 保存
output_path = Path("data_lake/orderbook_features/symbol=BTCUSDT/year=2024/month=01")
output_path.mkdir(parents=True, exist_ok=True)

output_file = output_path / "features.parquet"
features_df.to_parquet(output_file, compression="zstd", index=False)
print(f"✅ 保存到: {output_file}")

# 统计
print("\n" + "=" * 80)
print("📊 特征生成结果")
print("=" * 80)
print(f"\n📋 生成的特征:")
for i, col in enumerate(features_df.columns.tolist(), 1):
    print(f"  {i:2d}. {col}")

print(f"\n📈 统计数据:")
print(f"  时间范围: {features_df['datetime'].min()} ~ {features_df['datetime'].max()}")
print(f"  特征记录数: {len(features_df):,}")
print(f"  特征列数: {len(features_df.columns)}")
print(f"  平均点差: {features_df['spread'].mean():.4f}")
print(f"  平均Imbalance: {features_df['imbalance'].mean():.4f}")
print(f"  平均VWAP: {features_df['vwap'].mean():.2f}")
print(f"  总成交量: {features_df['total_volume'].sum():,.2f} BTC")
print(f"  总成交金额: ${features_df['total_value'].sum():,.2f}")

# 文件大小
file_size_mb = output_file.stat().st_size / 1024 / 1024
print(f"\n💾 文件大小: {file_size_mb:.2f} MB")

print("\n" + "=" * 80)
print("70G空间估算")
print("=" * 80)

one_month_size_gb = file_size_mb / 1024
months_per_70g = 70 / one_month_size_gb
years_per_70g = months_per_70g / 12

print(f"\n一个月特征大小: {one_month_size_gb:.4f} GB")
print(f"70GB可存: {months_per_70g:.1f}个月 = {years_per_70g:.1f}年")
print(f"  BTC单币种: {years_per_70g:.1f}年")
print(f"  BTC+ETH: {years_per_70g/2:.1f}年")

print("\n" + "=" * 80)
print("✅ 特征生成完成")
print("=" * 80)
