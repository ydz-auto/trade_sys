"""
批量策略优化 - 使用系统 ParallelBacktestEngine
支持：
- GPU 加速特征计算
- 多进程并行优化
- 最大持仓时间限制
- 止损/止盈
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import json
import asyncio
from itertools import product

sys.path.insert(0, str(Path(__file__).parent.parent))

from application.optimization_service.parallel_engine import (
    ParallelBacktestEngine,
    BacktestConfig,
    generate_param_grid
)


def resample_data(df, interval_min=10):
    """重采样数据到指定分钟间隔"""
    df = df.set_index('timestamp').copy()
    
    resampled = df.resample(f'{interval_min}min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'quote_volume': 'sum',
    })
    
    tech_cols = [c for c in df.columns if c in [
        'rsi_7', 'rsi_14', 'rsi_21',
        'sma_10', 'sma_20', 'sma_50', 'sma_100',
        'ema_10', 'ema_20', 'ema_50',
        'macd', 'macd_signal', 'macd_hist',
        'bb_upper', 'bb_lower', 'bb_width',
        'momentum_10'
    ]]
    
    for col in tech_cols:
        if col in df.columns:
            resampled[col] = df[col].resample(f'{interval_min}min').last()
    
    resampled = resampled.reset_index()
    resampled = resampled.dropna(subset=['close'])
    
    return resampled


async def main():
    print("="*80)
    print("批量策略优化 - ParallelBacktestEngine")
    print("="*80)
    
    # 配置
    config = BacktestConfig(
        initial_capital=10000.0,
        max_hold_hours=48,  # 2天
        stop_loss=0.02,
        take_profit=0.04,
        position_size=0.3,
        use_gpu=True,
        enable_slippage=False,
        enable_latency=False,
    )
    
    engine = ParallelBacktestEngine(config)
    
    # 加载原始特征数据
    cache_path = Path(__file__).parent.parent / "data_lake" / "features_cache"
    df_opt_1min = pd.read_parquet(cache_path / "features_opt.parquet")
    df_bt_1min = pd.read_parquet(cache_path / "features_backtest.parquet")
    
    print(f"\n原始数据:")
    print(f"  优化期 (1min): {len(df_opt_1min):,} 条")
    print(f"  回测期 (1min): {len(df_bt_1min):,} 条")
    
    # 重采样到10分钟
    df_opt_10min = resample_data(df_opt_1min, 10)
    df_bt_10min = resample_data(df_bt_1min, 10)
    
    print(f"\n重采样后:")
    print(f"  优化期 (10min): {len(df_opt_10min):,} 条")
    print(f"  回测期 (10min): {len(df_bt_10min):,} 条")
    
    # 保存临时文件给引擎使用
    temp_opt_path = Path(__file__).parent.parent / "data_lake" / "temp_opt_10min.parquet"
    temp_bt_path = Path(__file__).parent.parent / "data_lake" / "temp_bt_10min.parquet"
    
    df_opt_10min.to_parquet(temp_opt_path, index=False)
    df_bt_10min.to_parquet(temp_bt_path, index=False)
    
    # 时间范围
    opt_start = int(df_opt_10min['timestamp'].iloc[0].timestamp() * 1000)
    opt_end = int(df_opt_10min['timestamp'].iloc[-1].timestamp() * 1000)
    
    bt_start = int(df_bt_10min['timestamp'].iloc[0].timestamp() * 1000)
    bt_end = int(df_bt_10min['timestamp'].iloc[-1].timestamp() * 1000)
    
    symbol = "BTCUSDT"
    
    # 策略配置
    strategies = [
        {
            "id": "rsi_oversold",
            "name": "RSI超卖",
            "ranges": {"period": [7, 14], "threshold": [25, 30, 35]},
        },
        {
            "id": "sma_cross",
            "name": "SMA交叉",
            "ranges": {"fast": [10, 20], "slow": [50, 100]},
        },
        {
            "id": "macd_cross",
            "name": "MACD交叉",
            "ranges": {},
        },
        {
            "id": "ema_cross",
            "name": "EMA交叉",
            "ranges": {"fast": [10, 20], "slow": [50, 100]},
        },
        {
            "id": "bollinger_bands",
            "name": "布林带",
            "ranges": {},
        },
    ]
    
    all_results = []
    
    # 对