#!/usr/bin/env python3
"""
测试 Short Squeeze Pressure Strategy 测试脚本
"""

import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, Bar, SignalType
from infrastructure.storage.parquet_reader import read_parquet_safe

# 导入新策略
sys.path.insert(0, os.path.dirname(__file__))
from short_squeeze_pressure_strategy import ShortSqueezePressureStrategy

logger = get_logger("test_short_squeeze")

def load_test_bars():
    """加载一些测试用的 K线数据
    """
    DATA_LAKE_PATH = Path(backend_path) / "data_lake"
    DATA_LAKE_KLINES_PATH = DATA_LAKE_PATH / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"
    
    bars = []
    
    # 加载 2025年1月数据
    year_path = DATA_LAKE_KLINES_PATH / "year=2025"
    if year_path.exists():
        month_dir = year_path / "month=01"
        parquet_path = month_dir / "data.parquet"
        if parquet_path.exists():
            df = read_parquet_safe(parquet_path)
            if df is not None and len(df) > 0:
                for _, row in df.iterrows():
                    try:
                        if 'timestamp' in df.columns:
                            ts = pd.to_datetime(row['timestamp']).tz_localize('UTC')
                        elif 'open_time' in df.columns:
                            ts = pd.to_datetime(row['open_time'], unit='ms').tz_localize('UTC')
                        else:
                            continue
                        bar = Bar(
                            timestamp=ts,
                            open=float(row.get('open', 0)),
                            high=float(row.get('high', 0)),
                            low=float(row.get('low', 0)),
                            close=float(row.get('close', 0)),
                            volume=float(row.get('volume', 0)),
                        )
                        bars.append(bar)
                    except Exception as e:
                        continue
    return bars


def load_trade_features():
    """加载 trade_features 数据
    """
    DATA_LAKE_PATH = Path(backend_path) / "data_lake"
    DATA_LAKE_TRADE_FEATURES_PATH = DATA_LAKE_PATH / "crypto" / "binance" / "trade_features" / "symbol=BTCUSDT"
    
    import pandas as pd
    dfs = []
    
    # 加载 2025年1月数据
    year_dir = DATA_LAKE_TRADE_FEATURES_PATH / "year=2025"
    if year_dir.exists():
        month_dir = year_dir / "month=01"
        parquet_path = month_dir / "data.parquet"
        if parquet_path.exists():
            df = read_parquet_safe(parquet_path)
            if df is not None and len(df) > 0:
                dfs.append(df)
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        return df
    return None


def test_strategy():
    """测试策略运行"""
    import pandas as pd
    logger.info("=== 开始测试 Short Squeeze Pressure Strategy ===")
    
    # 加载测试数据
    test_bars = load_test_bars()
    logger.info(f"加载了 {len(test_bars)} 条 K线数据")
    
    trade_features_df = load_trade_features()
    logger.info(f"加载了 {len(trade_features_df) if trade_features_df is not None else 0} 条 trade_features 数据")
    
    # 策略实例化
    strategy = ShortSqueezePressureStrategy(
        price_momentum_threshold=0.003,
        cvd_zscore_threshold=2.0,
        taker_buy_ratio_threshold=0.6,
        volume_zscore_threshold=1.5
    )
    strategy.enable()
    
    logger.info("策略实例化成功")
    
    # 模拟策略回测
    signals = []
    close_prices = []
    
    for bar in test_bars[:1000]:
        close_prices.append(bar.close)
        
        # 获取补充数据
        data = {
            "close_prices": close_prices[-24:],
            "symbol": "BTCUSDT",
        }
        
        # 添加 trade_features 指标
        if trade_features_df is not None:
            ts_naive = bar.timestamp.replace(tzinfo=None)
            mask = trade_features_df["timestamp"] <= ts_naive
            if mask.any():
                latest_features = trade_features_df.loc[mask].iloc[-1]
                data["cvd_zscore"] = float(latest_features.get("cvd_zscore", 0.0))
                data["taker_buy_ratio"] = float(latest_features.get("taker_buy_ratio", 0.5))
                data["volume_zscore"] = float(latest_features.get("volume_zscore", 0.0))
                data["buy_sell_imbalance"] = float(latest_features.get("buy_sell_imbalance", 0.0))
                data["cvd_delta"] = float(latest_features.get("cvd_delta", 0.0))
                data["taker_buy_zscore"] = float(latest_features.get("taker_buy_zscore", 0.0))
        
        # 策略计算
        signal = strategy.calculate(data)
        if signal:
            signals.append((bar.timestamp, signal))
            logger.info(f"信号触发: {bar.timestamp}, 信号: {signal.action}")
    
    logger.info(f"=== 测试完成 ===")
    logger.info(f"总共触发了 {len(signals)} 个信号")
    
    for ts, signal in signals[:5]:
        logger.info(f"  - {ts}: {signal.action} {signal.metadata}")
    
    return len(signals) > 0


if __name__ == "__main__":
    test_strategy()

