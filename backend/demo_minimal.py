#!/usr/bin/env python3
"""
极简版Alpha回测 - 只运行BacktestEngine + 因子策略
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from services.backtest_service import BacktestEngine, BacktestConfig, SignalType


def generate_historical_data(symbol: str = "BTC/USDT", hours: int = 1000):
    """生成历史数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=hours)
    timestamps = pd.date_range(start=start_date, end=end_date, freq="1h")
    
    np.random.seed(42)
    n = len(timestamps)
    
    price = 50000.0
    prices = [price]
    
    for i in range(1, n):
        volatility = 0.02 + 0.01 * np.sin(i / 100)
        drift = 0.0005
        shock = np.random.normal(0, volatility)
        price = price * (1 + drift + shock)
        prices.append(price)
    
    price_array = np.array(prices)
    high = price_array * (1 + np.random.uniform(0, 0.015, n))
    low = price_array * (1 - np.random.uniform(0, 0.015, n))
    open_ = low + np.random.uniform(0, 1, n) * (high - low)
    close = price_array
    volume = np.random.lognormal(10, 0.8, n)
    
    data = pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    })
    return data


def compute_rsi(close_prices, period=14):
    """计算RSI"""
    delta = close_prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(close_prices, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
    ema_slow = close_prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def rsi_macd_strategy(bar, position):
    """基于RSI和MACD的组合策略"""
    if 'rsi' not in bar or 'macd_hist' not in bar:
        return SignalType.HOLD
    
    rsi = bar['rsi']
    macd_hist = bar['macd_hist']
    
    if pd.isna(rsi) or pd.isna(macd_hist):
        return SignalType.HOLD
    
    if rsi < 35 and macd_hist > 0:
        return SignalType.BUY
    elif rsi > 65 and macd_hist < 0:
        return SignalType.SELL
    
    return SignalType.HOLD


def momentum_strategy(bar, position):
    """动量策略"""
    if 'ma_short' not in bar or 'ma_long' not in bar:
        return SignalType.HOLD
    
    ma_short = bar['ma_short']
    ma_long = bar['ma_long']
    
    if pd.isna(ma_short) or pd.isna(ma_long):
        return SignalType.HOLD
    
    if ma_short > ma_long * 1.005:
        return SignalType.BUY
    elif ma_short < ma_long * 0.995:
        return SignalType.SELL
    
    return SignalType.HOLD


def mean_reversion_strategy(bar, position):
    """均值回归策略"""
    if 'bb_upper' not in bar or 'bb_lower' not in bar:
        return SignalType.HOLD
    
    close = bar['close']
    bb_upper = bar['bb_upper']
    bb_lower = bar['bb_lower']
    
    if pd.isna(close) or pd.isna(bb_upper) or pd.isna(bb_lower):
        return SignalType.HOLD
    
    if close < bb_lower * 0.995:
        return SignalType.BUY
    elif close > bb_upper * 1.005:
        return SignalType.SELL
    
    return SignalType.HOLD


def add_features(data_df):
    """给数据添加因子"""
    df = data_df.copy()
    df['rsi'] = compute_rsi(df['close'])
    _, _, df['macd_hist'] = compute_macd(df['close'])
    
    df['ma_short'] = df['close'].rolling(window=7).mean()
    df['ma_long'] = df['close'].rolling(window=21).mean()
    
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + bb_std * 2
    df['bb_lower'] = df['bb_middle'] - bb_std * 2
    
    return df


def main():
    print("\n" + "="*80)
    print("  🚀 Alpha 回测 - 因子策略")
    print("="*80)
    
    # 1. 生成数据
    print("\n[1/5] 生成历史数据...")
    data = generate_historical_data(hours=1200)
    print(f"      数据点: {len(data)}")
    print(f"      时间: {data['timestamp'].iloc[0]} → {data['timestamp'].iloc[-1]}")
    
    # 2. 计算因子
    print("\n[2/5] 计算技术因子...")
    data = add_features(data)
    print("      因子: RSI, MACD, MA, BBands")
    
    # 3. 转换数据格式
    print("\n[3/5] 准备回测数据...")
    bars = []
    for idx, row in data.iterrows():
        bars.append({
            'timestamp': row['timestamp'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume'],
            'rsi': row['rsi'],
            'macd_hist': row['macd_hist'],
            'ma_short': row['ma_short'],
            'ma_long': row['ma_long'],
            'bb_upper': row['bb_upper'],
            'bb_lower': row['bb_lower'],
        })
    
    # 4. 配置回测
    print("\n[4/5] 配置回测引擎...")
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.001,
        slippage=0.001
    )
    engine = BacktestEngine(config)
    
    # 5. 运行策略
    print("\n[5/5] 运行因子策略对比...")
    strategies = [
        ("RSI+MACD", rsi_macd_strategy),
        ("动量", momentum_strategy),
        ("均值回归", mean_reversion_strategy),
    ]
    
    results = []
    for name, strat in strategies:
        print(f"\n  策略: {name}")
        result = engine.run(bars, strat)
        results.append((name, result))
        engine.print_result(result)
    
    # 总结
    print("\n" + "="*80)
    print("  📊 策略对比")
    print("="*80)
    print(f"{'策略':<15} {'总收益':>12} {'夏普':>8} {'最大回撤':>12} {'交易次数':>10}")
    print("-"*80)
    for name, result in results:
        print(f"{name:<15} {result['total_return']:>12.2%} {result['sharpe_ratio']:>8.2f} {result['max_drawdown']:>12.2%} {result['total_trades']:>10}")
    
    print("\n" + "="*80)
    print("  ✅ 回测完成！")
    print("="*80)


if __name__ == "__main__":
    main()

