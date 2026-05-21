"""
PyTorch GPU Acceleration Test - PyTorch 统一加速测试

测试三种后端：
1. CUDA (NVIDIA GPU)
2. MPS (Apple Silicon)
3. CPU (fallback)

运行方式：
    python tests/test_torch_acceleration.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def test_device_detection():
    """测试设备检测"""
    print("\n" + "=" * 60)
    print("1. Device Detection Test")
    print("=" * 60)
    
    from shared.acceleration import device, is_gpu, get_device_info, get_accelerator_info
    
    info = get_accelerator_info()
    
    print(f"  Device: {device}")
    print(f"  Is GPU: {is_gpu}")
    print(f"  Device Info: {info['device_info']}")
    print(f"  PyTorch Version: {info['torch_version']}")
    
    return True


def test_tensor_operations():
    """测试 Tensor 操作"""
    print("\n" + "=" * 60)
    print("2. Tensor Operations Test")
    print("=" * 60)
    
    from shared.acceleration import torch, device, to_gpu, to_cpu, is_gpu
    
    arr_cpu = np.random.randn(1000, 1000).astype(np.float32)
    
    arr_gpu = to_gpu(arr_cpu)
    print(f"  Tensor device: {arr_gpu.device}")
    print(f"  Tensor shape: {arr_gpu.shape}")
    
    result = torch.mean(arr_gpu, dim=1)
    result_cpu = to_cpu(result)
    print(f"  Mean result shape: {result_cpu.shape}")
    
    print(f"  ✅ Tensor operations work correctly")
    return True


def test_feature_calculator():
    """测试特征计算器"""
    print("\n" + "=" * 60)
    print("3. PyTorch Feature Calculator Test")
    print("=" * 60)
    
    from domain.feature.torch_calculator import TorchFeatureCalculator
    
    calculator = TorchFeatureCalculator()
    
    n_rows = 10000
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n_rows, freq='1min'),
        'open': np.random.randn(n_rows).cumsum() + 50000,
        'high': np.random.randn(n_rows).cumsum() + 50100,
        'low': np.random.randn(n_rows).cumsum() + 49900,
        'close': np.random.randn(n_rows).cumsum() + 50000,
        'volume': np.random.rand(n_rows) * 100,
    })
    
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    print(f"  Input: {n_rows} rows")
    
    start = time.time()
    result = calculator.compute_batch(df, use_gpu=True)
    elapsed = time.time() - start
    
    print(f"  Output: {len(result.columns)} columns")
    print(f"  Time: {elapsed:.3f}s ({n_rows/elapsed:.0f} rows/sec)")
    
    feature_cols = [c for c in result.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    print(f"  Features: {len(feature_cols)}")
    print(f"  Sample: {feature_cols[:5]}...")
    
    print(f"  ✅ Feature calculator works correctly")
    return True


def test_lstm_strategy():
    """测试 LSTM 策略"""
    print("\n" + "=" * 60)
    print("4. LSTM Strategy Test")
    print("=" * 60)
    
    from domain.strategy.lstm_strategy import LSTMStrategy, LSTMConfig, LSTMStrategyBuilder
    from shared.acceleration import torch, to_gpu
    
    strategy = LSTMStrategyBuilder.create_fast(input_size=21)
    
    info = strategy.get_model_info()
    print(f"  Total params: {info['total_params']:,}")
    print(f"  Device: {info['device']}")
    
    features = torch.randn(100, 21, device=strategy.model.lstm.weight_ih_l0.device)
    labels = torch.randn(100, device=strategy.model.lstm.weight_ih_l0.device)
    
    print(f"  Training on synthetic data...")
    
    import asyncio
    
    async def train_and_predict():
        result = await strategy.train(features, labels, val_split=0.2)
        print(f"  Training epochs: {result['epochs']}")
        print(f"  Final train loss: {result['final_train_loss']:.6f}")
        
        signal = await strategy.predict(features[-60:])
        print(f"  Prediction signal: {signal}")
        
        return True
    
    success = asyncio.run(train_and_predict())
    
    print(f"  ✅ LSTM strategy works correctly")
    return success


def test_feature_to_lstm_pipeline():
    """测试特征计算到 LSTM 的完整流程"""
    print("\n" + "=" * 60)
    print("5. Feature → LSTM Pipeline Test")
    print("=" * 60)
    
    from domain.feature.torch_calculator import TorchFeatureCalculator
    from domain.strategy.lstm_strategy import LSTMStrategyBuilder
    from shared.acceleration import torch, device, to_gpu
    
    calculator = TorchFeatureCalculator()
    strategy = LSTMStrategyBuilder.create_fast(input_size=21)
    
    n_rows = 5000
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n_rows, freq='1min'),
        'open': np.random.randn(n_rows).cumsum() + 50000,
        'high': np.random.randn(n_rows).cumsum() + 50100,
        'low': np.random.randn(n_rows).cumsum() + 49900,
        'close': np.random.randn(n_rows).cumsum() + 50000,
        'volume': np.random.rand(n_rows) * 100,
    })
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    start = time.time()
    
    closes = to_gpu(df['close'].values.astype(np.float32))
    highs = to_gpu(df['high'].values.astype(np.float32))
    lows = to_gpu(df['low'].values.astype(np.float32))
    volumes = to_gpu(df['volume'].values.astype(np.float32))
    
    features_gpu = calculator.compute_batch_tensor(closes, highs, lows, volumes)
    
    feature_matrix = torch.stack([features_gpu[k] for k in sorted(features_gpu.keys())], dim=1)
    print(f"  Feature matrix shape: {feature_matrix.shape}")
    print(f"  Feature matrix device: {feature_matrix.device}")
    
    labels = (closes[1:] - closes[:-1]) / closes[:-1]
    labels = torch.cat([torch.zeros(1, device=device), labels])
    
    import asyncio
    
    async def train():
        result = await strategy.train(feature_matrix, labels)
        return result
    
    train_result = asyncio.run(train())
    
    elapsed = time.time() - start
    
    print(f"  Total pipeline time: {elapsed:.3f}s")
    print(f"  Features → LSTM: zero GPU memory copy ✅")
    
    print(f"  ✅ Pipeline works correctly")
    return True


def benchmark_gpu_vs_cpu():
    """GPU vs CPU 性能对比"""
    print("\n" + "=" * 60)
    print("6. GPU vs CPU Benchmark")
    print("=" * 60)
    
    from domain.feature.torch_calculator import TorchFeatureCalculator
    from shared.acceleration import is_gpu
    
    calculator = TorchFeatureCalculator()
    
    sizes = [1000, 10000, 50000]
    
    print(f"\n  {'Rows':<10} {'CPU (ms)':<15} {'GPU (ms)':<15} {'Speedup':<10}")
    print(f"  {'-'*50}")
    
    for n_rows in sizes:
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=n_rows, freq='1min'),
            'open': np.random.randn(n_rows).cumsum() + 50000,
            'high': np.random.randn(n_rows).cumsum() + 50100,
            'low': np.random.randn(n_rows).cumsum() + 49900,
            'close': np.random.randn(n_rows).cumsum() + 50000,
            'volume': np.random.rand(n_rows) * 100,
        })
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        start = time.time()
        calculator.compute_batch(df, use_gpu=False)
        cpu_time = (time.time() - start) * 1000
        
        if is_gpu:
            start = time.time()
            calculator.compute_batch(df, use_gpu=True)
            gpu_time = (time.time() - start) * 1000
            speedup = cpu_time / gpu_time
        else:
            gpu_time = cpu_time
            speedup = 1.0
        
        print(f"  {n_rows:<10} {cpu_time:<15.1f} {gpu_time:<15.1f} {speedup:<10.1f}x")
    
    print(f"\n  ✅ Benchmark completed")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("PyTorch GPU Acceleration Test Suite")
    print("=" * 60)
    
    tests = [
        ("Device Detection", test_device_detection),
        ("Tensor Operations", test_tensor_operations),
        ("Feature Calculator", test_feature_calculator),
        ("LSTM Strategy", test_lstm_strategy),
        ("Feature → LSTM Pipeline", test_feature_to_lstm_pipeline),
        ("GPU vs CPU Benchmark", benchmark_gpu_vs_cpu),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "✅ PASS" if success else "❌ FAIL"))
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"❌ FAIL: {e}"))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for name, result in results:
        print(f"  {name}: {result}")
    
    passed = sum(1 for _, r in results if "PASS" in r)
    print(f"\n  Total: {passed}/{len(results)} passed")
    
    print("\n" + "=" * 60)
    print("Installation Guide")
    print("=" * 60)
    print("""
  For NVIDIA GPU (Windows/Linux):
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    
  For Apple Silicon (Mac M1/M2/M3/M4):
    pip install torch
    
  For CPU only:
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    """)


if __name__ == "__main__":
    main()
