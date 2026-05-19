#!/usr/bin/env python3
"""
简化版 Order Book 特征生成器
直接保存到Parquet文件
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
import argparse


def load_trades(symbol: str, year: int, month: int) -> pd.DataFrame:
    trades_path = Path(__file__).parent.parent / "data_lake" / "crypto" / "binance" / "trades"
    path = trades_path / f"symbol={symbol}" / f"year={year}" / f"month={str(month).zfill(2)}" / "data.parquet"
    
    if not path.exists():
        return pd.DataFrame()
    
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('datetime').reset_index(drop=True)
    return df


def calculate_features(trades_df: pd.DataFrame, window_seconds: int = 60):
    if len(trades_df) == 0:
        return pd.DataFrame()
    
    features = []
    cumulative_delta = 0
    
    trades_df['window'] = trades_df['datetime'].dt.floor(f'{window_seconds}S')
    
    for window_start, group in trades_df.groupby('window'):
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
            'symbol': trades_df['symbol'].iloc[0] if 'symbol' in trades_df.columns else 'BTCUSDT',
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
    
    return pd.DataFrame(features)


def main():
    parser = argparse.ArgumentParser(description="基于Trade+K线生成OrderBook特征")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT"], help="交易对列表")
    parser.add_argument("--years", nargs="+", type=int, default=[2024], help="年份列表")
    parser.add_argument("--window", type=int, default=60, help="时间窗口（秒）")
    
    args = parser.parse_args()
    
    output_root = Path(__file__).parent.parent / "data_lake" / "orderbook_features"
    output_root.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("Order Book 特征生成器")
    print(f"交易对: {args.symbols}")
    print(f"年份: {args.years}")
    print(f"时间窗口: {args.window}秒")
    print("=" * 80)
    
    total_features = 0
    
    for symbol in args.symbols:
        for year in args.years:
            for month in range(1, 13):
                print(f"\n处理: {symbol} {year}-{month:02d}")
                
                trades_df = load_trades(symbol, year, month)
                
                if len(trades_df) == 0:
                    print(f"  ❌ 未找到Trades数据")
                    continue
                
                print(f"  ✅ 加载了 {len(trades_df):,} 条交易记录")
                
                features_df = calculate_features(trades_df, args.window)
                
                if len(features_df) == 0:
                    print(f"  ❌ 未生成特征")
                    continue
                
                print(f"  ✅ 生成了 {len(features_df):,} 条特征记录")
                total_features += len(features_df)
                
                output_path = output_root / f"symbol={symbol}" / f"year={year}" / f"month={str(month).zfill(2)}"
                output_path.mkdir(parents=True, exist_ok=True)
                
                features_df.to_parquet(
                    output_path / "features.parquet",
                    compression="zstd",
                    index=False
                )
                
                print(f"  ✅ 保存到: {output_path / 'features.parquet'}")
    
    print("\n" + "=" * 80)
    print("特征生成完成！")
    print(f"总特征数: {total_features:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
