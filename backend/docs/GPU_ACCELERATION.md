# GPU 加速指南

## 概述

本项目使用 **PyTorch** 作为统一的 GPU 加速框架，支持：

| 平台 | 后端 | 设备 |
|------|------|------|
| Windows/Linux + NVIDIA GPU | CUDA | RTX 2060S, RTX 3080, etc. |
| Mac M1/M2/M3/M4 | MPS | Apple Silicon |
| 任何平台 | CPU | NumPy fallback |

## 架构兼容性

### 与现有架构的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                        Deploy Layer                              │
│                                                                  │
│  deploy/docker-compose.yml     docker/docker-compose.gpu.yml    │
│  (CPU 版本，生产部署)            (GPU 版本，可选)                  │
│         │                              │                         │
│         │ 使用                         │ 使用                     │
│         ▼                              ▼                         │
│  docker/Dockerfile             docker/Dockerfile.gpu            │
│  (CPU 镜像)                    (GPU 镜像)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Runtime Layer                             │
│                                                                  │
│  signal_runtime ──► GPU 特征计算 + LSTM 策略                     │
│  correlation_runtime ──► GPU 相关性矩阵计算                      │
│  execution_runtime ──► 无 GPU 需求                               │
│  projection_runtime ──► 无 GPU 需求                              │
│  narrative_runtime ──► 无 GPU 需求                               │
│                                                                  │
│  Runtime 只做编排，业务逻辑在 services/                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Domain Layer                              │
│                                                                  │
│  domain/feature/torch_calculator.py  (GPU 特征计算)              │
│  domain/strategy/lstm_strategy.py    (LSTM 策略)                 │
│                                                                  │
│  这些是工具，被 services/ 或 runtime/ 调用                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Shared Layer                              │
│                                                                  │
│  shared/acceleration/  (GPU 加速层，可选)                        │
│  shared/progress/      (进度追踪，可选)                          │
│                                                                  │
│  这些是基础设施，不改变任何架构                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 各 Runtime GPU 加速状态

| Runtime | GPU 加速 | 功能 | 自动降级 |
|---------|---------|------|---------|
| `signal_runtime` | ✅ 支持 | 特征计算 + LSTM 策略 | ✅ CPU fallback |
| `correlation_runtime` | ✅ 支持 | 相关性矩阵计算 | ✅ CPU fallback |
| `execution_runtime` | ❌ 不需要 | 订单执行逻辑 | - |
| `projection_runtime` | ❌ 不需要 | 数据存储 | - |
| `narrative_runtime` | ❌ 不需要 | AI 叙事生成 | - |
| `ingestion_runtime` | ❌ 不需要 | 数据采集 | - |
| `monitoring_runtime` | ❌ 不需要 | 监控 | - |
| `scheduler_runtime` | ❌ 不需要 | 调度 | - |

### 各 Service GPU 加速状态

| Service | GPU 加速 | 功能 | 自动降级 |
|---------|---------|------|---------|
| `backtest_service` | ✅ 支持 | 特征计算 + 并行优化 | ✅ CPU fallback |
| `factor_service` | ✅ 支持 | 因子计算 | ✅ CPU fallback |
| `strategy_service` | ✅ 支持 | LSTM 策略 | ✅ CPU fallback |
| `execution_service` | ❌ 不需要 | 订单执行 | - |
| `fusion_service` | ❌ 不需要 | 信号融合 | - |
| `data_service` | ❌ 不需要 | 数据采集 | - |

### GPU 加速配置

**signal_runtime 配置：**

```python
class SignalConfig(RuntimeConfig):
    enable_gpu: bool = True          # 启用 GPU 加速
    lstm_enabled: bool = False       # 启用 LSTM 策略
    lstm_sequence_length: int = 60   # LSTM 序列长度
```

**correlation_runtime 配置：**

```python
class CorrelationConfig(RuntimeConfig):
    enable_gpu: bool = True          # 启用 GPU 加速
```

### 兼容性矩阵

| 层级 | 原有架构 | GPU 加速 | 冲突？ |
|------|---------|---------|--------|
| **Deploy** | `deploy/docker-compose.yml` (CPU) | `docker/docker-compose.gpu.yml` (GPU) | ❌ 独立 |
| **Runtime** | `signal_runtime`, `execution_runtime`... | 无变化 | ❌ 无影响 |
| **Services** | `strategy_service`, `factor_service`... | 可选择使用 GPU | ❌ 可选 |
| **Domain** | `domain/feature/unified_calculator.py` | `domain/feature/torch_calculator.py` | ❌ 并存 |
| **Shared** | 无 | `shared/acceleration/` | ❌ 新增 |

### 关键原则

1. **GPU 加速是可选的**：不使用 GPU 时，系统完全正常工作
2. **向后兼容**：所有现有代码无需修改
3. **独立部署**：GPU 版本和 CPU 版本可以独立部署
4. **零侵入**：GPU 模块不修改任何现有架构

## 为什么选择 PyTorch？

1. **LSTM 深度学习原生支持** - 必须用 PyTorch/TensorFlow
2. **技术指标计算也能 GPU 加速** - `torch.mean`, `torch.conv1d` 等
3. **零拷贝数据流** - 特征计算 → LSTM 模型，数据保持在 GPU 上
4. **统一技术栈** - 只需学习一个框架

## 安装

### Windows (NVIDIA GPU)

```bash
# CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Mac (Apple Silicon)

```bash
pip install torch
```

### CPU Only

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 快速开始

### 1. 检测设备

```python
from shared.acceleration import device, is_gpu, get_accelerator_info

info = get_accelerator_info()
print(f"Device: {info['device_type']}")
print(f"Is GPU: {info['is_gpu']}")
print(f"Device Info: {info['device_info']}")
```

### 2. 特征计算

```python
from domain.feature.torch_calculator import TorchFeatureCalculator

calculator = TorchFeatureCalculator()

# 方式1: DataFrame 输入输出
features_df = calculator.compute_batch(df, use_gpu=True)

# 方式2: GPU Tensor 输入输出（零拷贝，适合 LSTM）
from shared.acceleration import to_gpu

closes = to_gpu(df['close'].values)
highs = to_gpu(df['high'].values)
lows = to_gpu(df['low'].values)
volumes = to_gpu(df['volume'].values)

features = calculator.compute_batch_tensor(closes, highs, lows, volumes)
# features 是 Dict[str, torch.Tensor]，数据在 GPU 上
```

### 3. LSTM 策略

```python
from domain.strategy.lstm_strategy import LSTMStrategyBuilder

# 创建策略
strategy = LSTMStrategyBuilder.create_fast(input_size=21)

# 训练（数据在 GPU 上）
await strategy.train(feature_matrix, labels)

# 预测
signal = await strategy.predict(features_tensor)
# 返回: 1 (买入), -1 (卖出), 0 (持有)
```

### 4. 并行回测

```python
from application.optimization_service.parallel_engine import (
    ParallelBacktestEngine, generate_param_grid
)

engine = ParallelBacktestEngine()

# 生成参数网格
param_grid = generate_param_grid("rsi_oversold", {
    "period": [7, 14, 21],
    "threshold": [20, 25, 30],
})

# 并行优化
results = await engine.optimize_parallel(
    symbol="BTCUSDT",
    strategy_id="rsi_oversold",
    param_grid=param_grid,
    start_time=1704067200000,
    end_time=1735689600000,
    n_workers=8,
)
```

## 性能对比

### 特征计算 (10万行 K 线)

| 平台 | 时间 | 加速比 |
|------|------|--------|
| RTX 2060S (CUDA) | ~0.3s | **28x** |
| Mac M4 (MPS) | ~0.5s | **17x** |
| CPU (NumPy) | ~8.5s | 1x |

### 参数优化 (100 组参数)

| 平台 | 时间 | 加速比 |
|------|------|--------|
| RTX 2060S | ~15s | **8x** |
| Mac M4 | ~20s | **6x** |
| CPU | ~120s | 1x |

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Data (Parquet)                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              TorchFeatureCalculator                          │
│                                                              │
│   closes → GPU Tensor                                        │
│   highs  → GPU Tensor                                        │
│   lows   → GPU Tensor                                        │
│                                                              │
│   RSI / SMA / EMA / MACD / BB / ATR → GPU Tensor            │
└─────────────────────────┬───────────────────────────────────┘
                          │ 零拷贝传递
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    LSTM Strategy                             │
│                                                              │
│   feature_matrix (GPU Tensor)                                │
│            ↓                                                 │
│   LSTM Model (GPU)                                           │
│            ↓                                                 │
│   Signal: 1 / 0 / -1                                         │
└─────────────────────────────────────────────────────────────┘
```

## API 参考

### shared.acceleration

```python
# 设备信息
device: torch.device          # 当前设备
is_gpu: bool                  # 是否使用 GPU

# 函数
get_accelerator_info() -> dict
to_gpu(data) -> torch.Tensor
to_cpu(tensor) -> np.ndarray
clear_cache()
synchronize()
```

### TorchFeatureCalculator

```python
calculator = TorchFeatureCalculator()

# DataFrame 输入输出
calculator.compute_batch(df, symbol="BTCUSDT", use_gpu=True) -> pd.DataFrame

# GPU Tensor 输入输出（零拷贝）
calculator.compute_batch_tensor(closes, highs, lows, volumes) -> Dict[str, torch.Tensor]

# 单条计算（兼容原有接口）
calculator.compute(symbol, open, high, low, close, volume) -> Dict[str, float]

# 从 Parquet 计算
calculator.compute_from_parquet(parquet_path, symbol, output_path, use_gpu=True) -> pd.DataFrame
```

### LSTMStrategy

```python
# 创建策略
strategy = LSTMStrategyBuilder.create_fast(input_size=21)    # 快速配置
strategy = LSTMStrategyBuilder.create_default(input_size=21) # 默认配置
strategy = LSTMStrategyBuilder.create_deep(input_size=21)    # 深度配置

# 训练
await strategy.train(features, labels, val_split=0.2) -> dict

# 预测
await strategy.predict(features) -> int  # 1, -1, 0
await strategy.predict_batch(features) -> torch.Tensor

# 保存/加载
strategy.save(path)
strategy.load(path)

# 模型信息
strategy.get_model_info() -> dict
```

### ParallelBacktestEngine

```python
engine = ParallelBacktestEngine(config)

# 并行优化
await engine.optimize_parallel(
    symbol, strategy_id, param_grid,
    start_time, end_time, data_path, n_workers
) -> List[BacktestResult]

# 单次回测
await engine.run_single(symbol, strategy_id, params, start_time, end_time) -> BacktestResult

# 生成参数网格
generate_param_grid(strategy_id, ranges) -> List[dict]
```

## 环境变量

```bash
# 强制使用特定设备
export TORCH_DEVICE=cuda   # NVIDIA GPU
export TORCH_DEVICE=mps    # Apple Silicon
export TORCH_DEVICE=cpu    # CPU only
```

## 测试

```bash
cd backend
python tests/test_torch_acceleration.py
```

测试内容：
1. 设备检测（CUDA/MPS/CPU）
2. Tensor 操作
3. 特征计算
4. LSTM 训练和预测
5. 完整流程：特征计算 → LSTM（零拷贝）
6. GPU vs CPU 性能对比

## 故障排除

### CUDA Out of Memory

```python
from shared.acceleration import clear_cache

# 清理 GPU 缓存
clear_cache()

# 或减小 batch_size
config = LSTMConfig(batch_size=32)  # 默认 64
```

### MPS 不可用

```bash
# 检查 PyTorch 版本
python -c "import torch; print(torch.__version__)"

# 需要 PyTorch 2.0+
pip install --upgrade torch
```

### CPU 太慢

```bash
# 强制使用 GPU（如果可用）
export TORCH_DEVICE=cuda

# 或在代码中
import os
os.environ["TORCH_DEVICE"] = "cuda"
```
