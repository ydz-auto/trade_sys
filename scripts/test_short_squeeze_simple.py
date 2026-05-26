#!/usr/bin/env python3
"""
简化版测试：直接运行 single backtest 来验证 short_squeeze 策略
"""

import sys
import os
import pandas as pd

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from infrastructure.logging import get_logger
from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, Bar, SignalType
from infrastructure.storage.parquet_reader import read_parquet_safe
from run_all_30_strategies_v2 import StrategyAdapter
from short_squeeze_pressure_strategy import ShortSqueezePressureStrategy

logger = get_logger("test_short_squeeze")


def load_bars_for_year(year: int):
    DATA_LAKE_PATH = os.path.join(backend_path, "data_lake")
    DATA_LAKE_KLINES_PATH = os.path.join(DATA_LAKE_PATH, "crypto", "binance", "klines", "symbol=BTCUSDT")
    
    bars = []
    year_path = os.path.join(DATA_LAKE_KLINES_PATH, f"year={year}")
    if os.path.exists(year_path):
        for month_dir in sorted(os.listdir(year_path)):
            if month_dir.startswith("month="):
                month_path = os.path.join(year_path, month_dir)
                parquet_path = os.path.join(month_path, "data.parquet")
                if os.path.exists(parquet_path):
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
    DATA_LAKE_PATH = os.path.join(backend_path, "data_lake")
    DATA_LAKE_TRADE_FEATURES_PATH = os.path.join(DATA_LAKE_PATH, "crypto", "binance", "trade_features", "symbol=BTCUSDT")
    
    dfs = []
    if os.path.exists(DATA_LAKE_TRADE_FEATURES_PATH):
        for year_dir in sorted(os.listdir(DATA_LAKE_TRADE_FEATURES_PATH)):
            if year_dir.startswith("year="):
                year_path = os.path.join(DATA_LAKE_TRADE_FEATURES_PATH, year_dir)
                for month_dir in sorted(os.listdir(year_path)):
                    if month_dir.startswith("month="):
                        month_path = os.path.join(year_path, month_dir)
                        parquet_path = os.path.join(month_path, "data.parquet")
                        if os.path.exists(parquet_path):
                            df = read_parquet_safe(parquet_path)
                            if df is not None and len(df) > 0:
                                dfs.append(df)
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        return df
    return None


def get_strategy_data(ts, closes, trade_features_df):
    data = {}
    if trade_features_df is not None:
        ts_naive = ts.replace(tzinfo=None)
        mask = trade_features_df["timestamp"] <= ts_naive
        if mask.any():
            latest_features = trade_features_df.loc[mask].iloc[-1]
            data["cvd_zscore"] = float(latest_features.get("cvd_zscore", 0.0))
            data["taker_buy_ratio"] = float(latest_features.get("taker_buy_ratio", 0.5))
            data["volume_zscore"] = float(latest_features.get("volume_zscore", 0.0))
            data["buy_sell_imbalance"] = float(latest_features.get("buy_sell_imbalance", 0.0))
            data["cvd_delta"] = float(latest_features.get("cvd_delta", 0.0))
            data["taker_buy_zscore"] = float(latest_features.get("taker_buy_zscore", 0.0))
    return data


def main():
    print("=== 开始测试 Short Squeeze Strategy ===")
    
    # 1. 加载数据
    test_bars = load_bars_for_year(2025)
    trade_features_df = load_trade_features()
    
    logger.info(f"加载了 {len(test_bars)} 条 K线数据")
    logger.info(f"加载了 {len(trade_features_df) if trade_features_df is not None else 0} 条 trade_features 数据")
    
    # 只测试前 1000 条数据
    test_bars = test_bars[:1000]
    
    # 2. 初始化策略和 Adapter
    strategy = ShortSqueezePressureStrategy(
        price_momentum_threshold=0.002,
        cvd_zscore_threshold=1.5,
        taker_buy_ratio_threshold=0.55,
        volume_zscore_threshold=1.0
    )
    strategy.enable()
    
    def data_getter(ts, closes):
        return get_strategy_data(ts, closes, trade_features_df)
    
    strategy_adapter = StrategyAdapter(strategy, data_getter)
    
    # 3. 配置回测
    config = BacktestConfig(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        max_leverage=5.0,
        position_size_pct=0.2
    )
    
    engine = BacktestEngine(config)
    
    # 4. 运行回测
    logger.info("开始运行回测...")
    for i, bar in enumerate(test_bars):
        if i % 100 == 0:
            logger.info(f"处理 {i}/{len(test_bars)} 条数据...")
        engine.process_bar(bar, strategy_adapter)
    
    # 5. 获取结果
    final_equity = engine.get_equity()
    trades = engine.get_trades()
    
    print(f"\n=== 回测完成 ===")
    print(f"最终权益: {final_equity:.2f}")
    print(f"总收益: {((final_equity / 10000 - 1) * 100):.2f}%")
    print(f"交易次数: {len(trades)}")
    
    if trades:
        print("\n前 5 笔交易:")
        for i, trade in enumerate(trades[:5]):
            print(f"{i+1}. {trade}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

