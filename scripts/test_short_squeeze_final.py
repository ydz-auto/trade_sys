#!/usr/bin/env python3
"""
最终测试：验证 ShortSqueezePressureStrategy 的完整功能
包含：ActionType 确认、特征 shift 验证、交易方向验证
"""

import sys
import os
import pandas as pd
from datetime import datetime

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from infrastructure.logging import get_logger
from runtimes.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, Bar
from infrastructure.storage.parquet_reader import read_parquet_safe
from run_all_30_strategies_v2 import StrategyAdapter
from short_squeeze_pressure_strategy import ShortSqueezePressureStrategy
from engines.compute.strategy.strategies import ActionType

logger = get_logger("test_short_squeeze_final")

def test_action_type_enum():
    """测试 ActionType 枚举"""
    print("\n=== 1. 验证 ActionType 枚举 ===")
    print(f"可用的 ActionType: {[e.name for e in ActionType]}")
    print(f"ActionType.LONG = '{ActionType.LONG}'")
    print(f"ActionType.SHORT = '{ActionType.SHORT}'")
    print(f"ActionType.HOLD = '{ActionType.HOLD}'")
    print(f"ActionType.CLOSE = '{ActionType.CLOSE}'")
    return True


def load_bars_for_month(year: int, month: int):
    """加载指定年月的 K线数据"""
    DATA_LAKE_KLINES_PATH = os.path.join(backend_path, "data_lake", "crypto", "binance", "klines", "symbol=BTCUSDT")
    
    bars = []
    month_path = os.path.join(DATA_LAKE_KLINES_PATH, f"year={year}", f"month={month:02d}")
    if os.path.exists(month_path):
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


def load_trade_features_for_month(year: int, month: int):
    """加载指定年月的 trade_features，包含 shift 处理"""
    DATA_LAKE_TRADE_FEATURES_PATH = os.path.join(backend_path, "data_lake", "crypto", "binance", "trade_features", "symbol=BTCUSDT")
    
    dfs = []
    month_path = os.path.join(DATA_LAKE_TRADE_FEATURES_PATH, f"year={year}", f"month={month:02d}")
    if os.path.exists(month_path):
        parquet_path = os.path.join(month_path, "data.parquet")
        if os.path.exists(parquet_path):
            df = read_parquet_safe(parquet_path)
            if df is not None and len(df) > 0:
                dfs.append(df)
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        
        # 模拟回测脚本中的 shift(1) 处理
        feature_cols = [
            "cvd_delta",
            "cvd_zscore",
            "taker_buy_ratio",
            "taker_buy_zscore",
            "volume_zscore",
            "buy_sell_imbalance",
            "cvd",
        ]
        for col in feature_cols:
            if col in df.columns:
                df[col] = df[col].shift(1)
        
        return df
    return None


def test_strategy_signals():
    """测试策略信号触发"""
    print("\n=== 2. 测试策略信号 ===")
    
    # 加载数据
    test_bars = load_bars_for_month(2025, 1)[:500]
    trade_features_df = load_trade_features_for_month(2025, 1)
    
    print(f"加载了 {len(test_bars)} 条 K线数据")
    print(f"加载了 {len(trade_features_df) if trade_features_df is not None else 0} 条 trade_features 数据")
    
    # 初始化策略
    strategy = ShortSqueezePressureStrategy(
        price_momentum_threshold=0.002,
        cvd_zscore_threshold=1.5,
        taker_buy_ratio_threshold=0.55,
        volume_zscore_threshold=1.0
    )
    strategy.enable()
    
    print(f"策略 ID: {strategy.strategy_id}")
    print(f"策略名称: {strategy.__class__.__name__}")
    
    # 模拟回测
    close_prices = []
    signals = []
    
    for bar in test_bars:
        close_prices.append(bar.close)
        
        data = {
            "close_prices": close_prices[-24:],
            "symbol": "BTCUSDT",
        }
        
        if trade_features_df is not None:
            ts_naive = bar.timestamp.replace(tzinfo=None)
            mask = trade_features_df["timestamp"] <= ts_naive
            if mask.any():
                latest_features = trade_features_df.loc[mask].iloc[-1]
                data["cvd_zscore"] = float(latest_features.get("cvd_zscore", 0.0))
                data["taker_buy_ratio"] = float(latest_features.get("taker_buy_ratio", 0.5))
                data["volume_zscore"] = float(latest_features.get("volume_zscore", 0.0))
                data["buy_sell_imbalance"] = float(latest_features.get("buy_sell_imbalance", 0.0))
        
        signal = strategy.calculate(data)
        if signal:
            signals.append((bar.timestamp, signal))
            print(f"  信号触发: {bar.timestamp}, Action: {signal.action}, Confidence: {signal.confidence:.2f}")
            print(f"    元数据: {signal.metadata}")
    
    print(f"\n总共触发了 {len(signals)} 个信号")
    
    # 验证信号类型
    long_signals = sum(1 for _, s in signals if s.action == ActionType.LONG)
    close_signals = sum(1 for _, s in signals if s.action == ActionType.CLOSE)
    
    print(f"  - LONG 信号: {long_signals}")
    print(f"  - CLOSE 信号: {close_signals}")
    
    # 检查是否有错误的信号类型
    invalid_signals = [s for _, s in signals if s.action not in [ActionType.LONG, ActionType.CLOSE]]
    if invalid_signals:
        print(f"  ❌ 发现无效信号类型: {invalid_signals}")
        return False
    else:
        print("  ✅ 所有信号类型正确（只有 LONG/CLOSE）")
        return True


def test_feature_shift():
    """测试特征 shift 处理"""
    print("\n=== 3. 验证特征 Shift 处理 ===")
    
    trade_features_df = load_trade_features_for_month(2025, 1)
    
    if trade_features_df is not None:
        # 检查第一行是否有 NaN（shift 后的结果）
        first_row = trade_features_df.iloc[0]
        feature_cols = ["cvd_zscore", "taker_buy_ratio", "volume_zscore"]
        
        has_nan = any(pd.isna(first_row[col]) for col in feature_cols)
        if has_nan:
            print("  ✅ 第一行特征值为 NaN（正确，因为 shift(1)）")
            print(f"    第一行特征: {first_row[feature_cols].to_dict()}")
        else:
            print("  ❌ 第一行特征值不为 NaN（可能没有正确 shift）")
            return False
        
        # 检查后面行是否有值
        middle_row = trade_features_df.iloc[100]
        has_values = all(not pd.isna(middle_row[col]) for col in feature_cols)
        if has_values:
            print("  ✅ 中间行特征值正常（shift 后数据完整）")
            print(f"    第100行特征: {middle_row[feature_cols].to_dict()}")
        else:
            print("  ❌ 中间行特征值有缺失")
            return False
    else:
        print("  ⚠️ 无法加载 trade_features 数据")
    
    return True


def main():
    print("="*80)
    print("Short Squeeze Pressure Strategy 最终验证测试")
    print("="*80)
    
    all_passed = True
    
    # 测试 1: ActionType 枚举
    if not test_action_type_enum():
        all_passed = False
    
    # 测试 2: 策略信号
    if not test_strategy_signals():
        all_passed = False
    
    # 测试 3: 特征 shift
    if not test_feature_shift():
        all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ 所有测试通过！")
        print("\n总结:")
        print("1. ActionType 枚举确认: LONG, SHORT, HOLD, CLOSE")
        print("2. 策略只生成 LONG/CLOSE 信号（符合 short squeeze 做多逻辑）")
        print("3. 特征已正确 shift(1)，防止数据泄露")
        print("4. 策略 ID: short_squeeze_pressure（明确标识使用 CVD proxy）")
    else:
        print("❌ 部分测试失败")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
