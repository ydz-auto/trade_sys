#!/usr/bin/env python3
"""调试回测逻辑"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

# 加载少量数据来调试
DATA_LAKE_ROOT = Path("/Volumes/00_crypto/00_code/backend/data_lake")

def load_sample():
    # 只加载2022-01的数据
    df = pd.read_parquet(DATA_LAKE_ROOT / "crypto/binance/klines/symbol=BTCUSDT/year=2022/month=01/data.parquet")
    df = df.set_index('timestamp').sort_index().resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna().reset_index()
    return df

def compute_simple_features(df):
    close = df['close']
    df['return_1h'] = close.pct_change(12)
    df['future_ret_1h'] = close.shift(-12) / close - 1
    return df

def debug_manual_backtest(df):
    """手动简易回测，每次满仓50倍，50倍1小时"""
    
    capital = 10000
    leverage = 50
    
    for i in range(48, min(1000, len(df)-12)):
        current_price = df.iloc[i]
        entry_price = current_price['close']
        
        # 随便模拟买入
        ret = df['future_ret_1h'].iloc[i]
        profit_pct = ret * leverage
        
        capital = capital * (1 + profit_pct)
        
        if i % 50 == 0:
            print(f"Step {i}: capital={capital:.2f}, ret={ret*100:.4f}%, profit_pct={profit_pct*100:.4f}%")
    
    print(f"Final capital: {capital:.2f}")

if __name__ == "__main__":
    df = load_sample()
    df = compute_simple_features(df)
    debug_manual_backtest(df)
