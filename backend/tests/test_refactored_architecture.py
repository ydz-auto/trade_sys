#!/usr/bin/env python3
"""测试重构后的加速架构"""
import sys
import os
import time
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import pandas as pd


def test_infrastructure():
    """测试基础设施层"""
    print("=" * 80)
    print("[1/4] 测试基础设施层")
    print("=" * 80)

    from infrastructure.acceleration import DeviceManager, AccelerationService

    device = DeviceManager.detect()
    print(f"  设备: {device.device_type} ({device.device_name})")
    print(f"  GPU: {device.is_gpu}")

    service = AccelerationService.create_for_optimization(
        enable_multiprocess=True,
        enable_gpu=True
    )
    print(f"  GPU可用: {service.is_gpu_available()}")
    print()


def test_strategy_registry():
    """测试策略注册"""
    print("=" * 80)
    print("[2/4] 测试策略注册")
    print("=" * 80)

    from engines.compute.strategy.registry import get_strategy, list_strategies

    strategies = list_strategies()
    print(f"  已注册策略数: {len(strategies)}")

    strategy = get_strategy("long_liquidation_bounce", {"drop_threshold": -0.02})
    print(f"  long_liquidation_bounce: {type(strategy).__name__}")
    print()


def test_backtest_worker():
    """测试 backtest_worker"""
    print("=" * 80)
    print("[3/4] 测试 backtest_worker (串行)")
    print("=" * 80)

    from engines.optimization.backtest_worker import (
        run_single_backtest_worker,
        build_backtest_task
    )

    bars_data = _load_test_bars()
    if not bars_data:
        print("  ❌ 没有测试数据")
        return None

    print(f"  加载了 {len(bars_data)} 条K线")

    task = build_backtest_task(
        strategy_id="long_liquidation_bounce",
        params={"drop_threshold": -0.02, "rsi_threshold": 25, "volume_ratio_threshold": 2.0},
        bars_data=bars_data,
        enable_gpu=False
    )

    start = time.time()
    result = run_single_backtest_worker(task)
    elapsed = time.time() - start

    print(f"  Sharpe: {result.get('sharpe', 'N/A')}")
    print(f"  Trades: {result.get('trades', 'N/A')}")
    print(f"  Return: {result.get('total_return', 'N/A')}")
    print(f"  Error: {result.get('error', 'N/A')}")
    print(f"  耗时: {elapsed:.2f}秒")
    print()

    return bars_data


def test_parameter_optimizer(bars_data):
    """测试 ParameterOptimizer"""
    print("=" * 80)
    print("[4/4] 测试 ParameterOptimizer (多进程)")
    print("=" * 80)

    from engines.optimization import ParameterOptimizer

    optimizer = ParameterOptimizer(
        enable_multiprocess=True,
        enable_gpu=False,
        max_workers=8
    )

    param_grid = {
        "drop_threshold": [-0.015, -0.02],
        "rsi_threshold": [20, 25],
        "volume_ratio_threshold": [1.5, 2.0]
    }

    print(f"  参数组合数: {2*2*2} = 8")

    start = time.time()
    result = optimizer.optimize(
        strategy_id="long_liquidation_bounce",
        param_grid=param_grid,
        bars_data=bars_data
    )
    elapsed = time.time() - start

    print(f"  最佳参数: {result.best_params}")
    print(f"  最佳Sharpe: {result.best_sharpe:.4f}")
    print(f"  最佳Trades: {result.best_trades}")
    print(f"  成功结果数: {len(result.all_results)}")
    print(f"  耗时: {elapsed:.2f}秒")
    print()


def _load_test_bars():
    """加载测试K线数据"""
    data_path = backend_path / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / "year=2022"

    bars = []
    if not data_path.exists():
        print(f"  数据路径不存在: {data_path}")
        return bars

    from infrastructure.storage.parquet_reader import read_parquet_safe
    from runtimes.replay_runtime.backtest_engine import Bar

    for month_dir in sorted(data_path.iterdir())[:3]:
        if month_dir.is_dir() and month_dir.name.startswith("month="):
            parquet_file = month_dir / "data.parquet"
            if parquet_file.exists():
                df = read_parquet_safe(parquet_file)
                if df is not None and len(df) > 0:
                    for _, row in df.head(500).iterrows():
                        try:
                            bar = Bar(
                                timestamp=pd.to_datetime(row["timestamp"], utc=True),
                                open=float(row["open"]),
                                high=float(row["high"]),
                                low=float(row["low"]),
                                close=float(row["close"]),
                                volume=float(row["volume"])
                            )
                            bars.append(bar)
                        except:
                            continue

    return [
        {
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume
        }
        for bar in bars
    ]


if __name__ == "__main__":
    try:
        test_infrastructure()
        test_strategy_registry()
        bars_data = test_backtest_worker()
        if bars_data:
            test_parameter_optimizer(bars_data)
        print("=" * 80)
        print("✅ 所有测试完成!")
        print("=" * 80)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
