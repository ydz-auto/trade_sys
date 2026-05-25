#!/usr/bin/env python3
"""
完整真实回测！
配置：
- 初始资金：$10,000
- 杠杆：50倍
- 止损：10%
- 复利：否
- 持仓：48小时
- 仓位：100%
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from infrastructure.logging import get_logger
logger = get_logger("backtest_real")

# 导入真实系统引擎！
from runtimes.replay_runtime.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar
)


def load_data_from_datalake(symbol, start, end, freq_min=60):
    data_lake = Path("/Volumes/00_crypto/00_code/backend/data_lake")
    all_bars = []
    
    for month in range(start.month, end.month+1):
        data_path = data_lake / "crypto/binance/klines" / f"symbol={symbol}/year={start.year}/month={month:02d}/data.parquet"
        if data_path.exists():
            df = pd.read_parquet(data_path)
            all_bars.append(df)
    
    if not all_bars:
        return []
        
    df_total = pd.concat(all_bars, ignore_index=True)
    df_total['timestamp'] = pd.to_datetime(df_total['timestamp'])
    df_total = df_total[(df_total['timestamp'] >= start] & [(df_total['timestamp'] <= end)
    df_total = df_total.set_index('timestamp').sort_index()
    
    agg = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    df_resampled = df_total.resample(f"{freq_min}T").agg(agg).dropna().reset_index()
    return df_resampled


def main():
    print("=" * 120)
    print("完整真实回测！")
    print("=" * 120)
    
    initial_capital = 10000.0
    leverage = 50.0
    stop_loss = 0.10
    
    start = datetime(2022,1,1)
    end = datetime(2022,1,31)
    
    print(f"配置：")
    print(f"  - 初始资金：${initial_capital:,.2f}")
    print(f"  - 杠杆：{leverage:.0f}x")
    print(f"  - 止损：{stop_loss*100:.0f}%")
    print(f"  - 非复利，100%仓位")
    
    # 加载数据
    df = load_data_from_datalake("BTCUSDT", start, end)
    print(f"✅ 加载 {len(df)}条 K线")
    
    # 转换格式！
    bars = []
    for _, row in df.iterrows():
        bars.append(Bar(
            timestamp=row['timestamp'],
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))
    
    # 配置真实引擎！
    config = BacktestConfig(
        initial_capital=initial_capital,
        leverage=leverage,
        position_size=1.0,
        stop_loss=stop_loss,
        take_profit=0.30,
        commission=0.0004,
        slippage=0.0005,
        use_realistic_fees=True,
        maintenance_margin_rate=0.005
    )
    
    # 真实策略！
    class RealStrategy:
        def __init__(self):
            self._closes = []
            
        def __call__(self, bar, pos):
            self._closes.append(bar.close)
            
            if len(self._closes) < 2:
                return SignalType.HOLD
                
            current_price = bar.close
            prev_price = self._closes[-2]
            
            # 简单趋势策略！
            if not pos:
                if current_price > prev_price * 1.005:
                    return SignalType.BUY
                elif current_price < prev_price * 0.995:
                    return SignalType.SELL
            else:
                if pos['side'] == SignalType.BUY and current_price < prev_price:
                    return SignalType.SELL
                elif pos['side'] == SignalType.SELL and current_price > prev_price:
                    return SignalType.BUY
                    
            return SignalType.HOLD
    
    # 运行真实回测！
    print("\n🚀 开始真实回测...")
    engine = BacktestEngine(config=config)
    engine.load_data(bars)
    result = engine.run(RealStrategy())
    
    print("\n" + "=" * 120)
    print("📊 完整真实系统回测结果！")
    print("=" * 120)
    print(f"初始资金：${initial_capital:,.2f}")
    print(f"最终