#!/usr/bin/env python3
"""验证完整的 Walk-Forward 优化流程"""
import sys
import os
import time
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

print(f"Backend path: {backend_path}")

from infrastructure.logging import get_logger
from infrastructure.acceleration import DeviceManager, AccelerationService
from runtime.replay_runtime.backtest_engine import Bar
from infrastructure.storage.parquet_reader import read_parquet_safe
import pandas as pd


def test_full_walkforward():
    """测试完整的 Walk-Forward 优化流程"""
    print("=" * 80)
    print("测试完整的 Walk-Forward 优化流程")
    print("=" * 80)
    
    # 1. 设备检测
    print("\n[1/5] 设备检测")
    device = DeviceManager.detect()
    print(f"  设备: {device.device_type} ({device.device_name})")
    print(f"  GPU可用: {device.is_gpu}")
    
    # 2. 创建加速服务
    print("\n[2/5] 创建加速服务")
    acc_service = AccelerationService.create_for_optimization(
        enable_multiprocess=True,
        enable_gpu=True
    )
    print(f"  加速服务已创建")
    print(f"  GPU可用: {acc_service.is_gpu_available()}")
    
    # 3. 加载测试数据
    print("\n[3/5] 加载测试数据 (2022)")
    data_path = backend_path / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / "year=2022"
    
    bars = []
    if data_path.exists():
        for month_dir in sorted(data_path.iterdir())[:2]:  # 只测试前2个月
            if month_dir.is_dir() and month_dir.name.startswith("month="):
                parquet_file = month_dir / "data.parquet"
                if parquet_file.exists():
                    print(f"  读取: {parquet_file}")
                    df = read_parquet_safe(parquet_file)
                    if df is not None and len(df) > 0:
                        df_sample = df.head(100)
                        for _, row in df_sample.iterrows():  # 每个文件只取100条
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
    else:
        print(f"  数据路径不存在: {data_path}")
        print(f"  列出 backend 目录下的内容: {list(backend_path.iterdir())[:10]}")
    
    print(f"  加载了 {len(bars)} 条 K线数据")
    
    # 4. 测试优化流程
    print("\n[4/5] 测试参数优化 (8组参数)")
    param_grid = {
        "drop_threshold": [-0.015, -0.02],
        "rsi_threshold": [20, 25],
        "volume_ratio_threshold": [1.5, 2.0]
    }
    
    from itertools import product
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    param_combinations = [dict(zip(keys, combo)) for combo in product(*values)]
    
    print(f"  参数组合数: {len(param_combinations)}")
    
    # 准备回测任务
    import importlib.util
    project_root = backend_path.parent
    scripts_path = project_root / 'scripts'
    print(f"  脚本路径: {scripts_path}")
    spec = importlib.util.spec_from_file_location(
        "run_walkforward_fixed", 
        scripts_path / "run_walkforward_fixed.py"
    )
    wf_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wf_module)
    run_single_backtest_module = wf_module.run_single_backtest_module
    
    config_dict = {
        "initial_capital": 10000.0,
        "commission": 0.0004,
        "slippage": 0.0005,
        "position_size": 0.1,
        "stop_loss": 0.1,
        "take_profit": 0.2,
        "leverage": 5.0,
        "use_realistic_fees": True
    }
    
    bars_data = [
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
    
    tasks = [
        ("long_liquidation_bounce", params, bars_data, config_dict, False, None, None)
        for params in param_combinations
    ]
    
    print("\n  测试多进程模式:")
    start = time.time()
    results = acc_service.parallel_map(
        func=run_single_backtest_module,
        tasks=tasks,
        executor="process",
        progress_callback=lambda done, total: print(f"    进度: {done}/{total}")
    )
    time_mp = time.time() - start
    
    successful_results = [r for r in results if r is not None and not r.get("error")]
    print(f"  成功: {len(successful_results)}/{len(results)}")
    if successful_results:
        best = max(successful_results, key=lambda x: x.get("sharpe", -float('inf')))
        print(f"  最佳 Sharpe: {best.get('sharpe', -float('inf')):.4f}")
        print(f"  最佳参数: {best.get('params')}")
    print(f"  耗时: {time_mp:.2f}秒")
    
    print("\n  测试串行模式:")
    start = time.time()
    results_seq = []
    for i, args in enumerate(tasks):
        result = run_single_backtest_module(args)
        results_seq.append(result)
        if (i + 1) % 4 == 0:
            print(f"    进度: {i+1}/{len(tasks)}")
    time_seq = time.time() - start
    
    successful_seq = [r for r in results_seq if r is not None and not r.get("error")]
    print(f"  成功: {len(successful_seq)}/{len(results_seq)}")
    print(f"  耗时: {time_seq:.2f}秒")
    
    print("\n[5/5] 性能对比")
    print(f"  多进程: {time_mp:.2f}秒")
    print(f"  串行:   {time_seq:.2f}秒")
    if time_mp > 0:
        print(f"  加速比: {time_seq/time_mp:.2f}x")
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)


if __name__ == "__main__":
    import pandas as pd
    try:
        test_full_walkforward()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
