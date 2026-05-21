# GPU 加速指南

## 概述

本项目使用 **PyTorch** 作为统一的 GPU 加速框架，支持：

| 平台 | 后端 | 设备 |
|------|------|------|
| Windows/Linux + NVIDIA GPU | CUDA | RTX 2060S, RTX 3080, etc. |
| Mac M1/M2/M3/M4 | MPS | Apple Silicon |
| 任何平台 | CPU | NumPy fallback |

> **重要更新（2026-05-22）**：  
> 所有 GPU 加速现在必须**通过 Runtime 架构**！独立的 GPU 脚本（`scripts/gpu_*.py`）已删除！

---

## 架构兼容性

### 与现有架构的关系（最终收敛版）

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend / API                           │
└────────────────────────────────────────┬────────────────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │ Runtime State Store  │
                              │ (唯一真实状态源)     │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ Projection Runtime   │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ Portfolio Runtime    │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ Execution Runtime    │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ Signal Runtime       │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ Feature Matrix      │
                              │ Runtime (核心真理)   │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ Runtime Bus         │
                              │ (唯一事件总线)       │
                              └───────────┬───────────┘
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────────┐
│           Data Service (事实层)          │                                       │
└─────────────────────────────────────────┘                                       │
                                          │                                       │
                                          ▼                                       │
                        ┌───────────────────────────────┐                          │
                        │ Exchange / Replay             │                          │
                        └───────────────────────────────┘                          │
                                                                                   │
┌───────────────────────────────────────────────────────────────────────────────┐
│                          Infrastructure (加速层)                               │
│                                                                               │
│  ┌───────────────────────┐  ┌───────────────────────┐                         │
│  │ shared/acceleration/  │  │  domain/feature/      │                         │
│  │ (GPU基础设施层)        │  │  torch_calculator.py │                         │
│  │ (保留！)               │  │ (GPU特征计算)        │                         │
│  └───────────────────────┘  └───────────────────────┘                         │
└───────────────────────────────────────────────────────────────────────────────┘
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
| `replay_runtime` | ✅ 支持 | 回测时特征计算 | ✅ CPU fallback |
| `feature_matrix_runtime` | ✅ 支持 | 特征计算 | ✅ CPU fallback |

### 各 Service GPU 加速状态

| Service | GPU 加速 | 功能 | 自动降级 |
|---------|---------|------|---------|
| `backtest_service` | ✅ 通过 replay_runtime | 回测 | ✅ CPU fallback |
| `factor_service` | ✅ 通过 feature_runtime | 因子计算 | ✅ CPU fallback |
| `strategy_service` | ✅ 通过 signal_runtime | LSTM 策略 | ✅ CPU fallback |
| `optimization_service` | ✅ 通过 OptimizationBacktestEngine (走 Runtime) | 优化 | ✅ CPU fallback |
| `execution_service` | ❌ 不需要 | 订单执行 | - |
| `fusion_service` | ❌ 不需要 | 信号融合 | - |
| `data_service` | ❌ 不需要 | 数据采集 | - |

---

## 关键架构原则（2026-05-22 更新）

### 1. **GPU 是基础设施，不是独立系统！**
```
✅ 正确方式：
  replay_runtime → feature_runtime → shared/acceleration/ → GPU计算

❌ 错误方式（已删除）：
  scripts/gpu_feature_backtest.py → 直接pandas → 独立运行
```

### 2. **所有回测必须走 Runtime 主链！**
```
✅ 正确方式：
  application/optimization_service/engine.py → replay_runtime

❌ 错误方式（已删除）：
  application/optimization_service/parallel_engine.py → 直接pandas
```

---

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

---

## 快速开始

### 1. 检测设备

```python
from shared.acceleration import device, is_gpu, get_accelerator_info

info = get_accelerator_info()
print(f"Device: {info['device_type']}")
print(f"Is GPU: {info['is_gpu']}")
print(f"Device Info: {info['device_info']}")
```

### 2. 通过 Runtime 使用 GPU（推荐！唯一方式！）

#### 2.1 回测（走 replay_runtime）
```python
from shared.replay.orchestrator import ReplayOrchestrator

orchestrator = ReplayOrchestrator()
# GPU 加速由 shared/acceleration/ 自动处理
await orchestrator.run_replay(...)
```

#### 2.2 优化（走 OptimizationBacktestEngine）
```python
from application.optimization_service.engine import OptimizationBacktestEngine

engine = OptimizationBacktestEngine()
# GPU 加速自动启用（如果可用）
await engine.optimize(...)
```

### 3. 特征计算（直接使用 TorchFeatureCalculator）

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

### 4. LSTM 策略

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

---

## 性能对比

### 特征计算 (10万行 K 线)

| 平台 | 时间 | 加速比 |
|------|------|--------|
| RTX 2060S (CUDA) | ~0.3s | **28x** |
| Mac M4 (MPS) | ~0.5s | **17x** |
| CPU (NumPy) | ~8.5s | 1x |

---

## 架构（最终收敛版）

```
┌─────────────────────────────────────────────────────────────┐
│                  Exchange / Replay Data                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Ingestion Runtime   │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │    Runtime Bus        │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Feature Matrix       │
              │ Runtime (核心真理)    │
              └───────────┬───────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │    domain/feature/torch_calculator.py   │
        │                                         │
        │   closes → GPU Tensor (to_gpu())        │
        │   highs  → GPU Tensor                   │
        │   lows   → GPU Tensor                   │
        │   volumes→ GPU Tensor                   │
        │                                         │
        │   RSI / SMA / EMA / MACD / BB / ATR →  │
        │   GPU Tensor (零拷贝!)                  │
        └─────────────────┬───────────────────────┘
                          │ 零拷贝传递
                          ▼
              ┌───────────────────────┐
              │   Signal Runtime      │
              │   (LSTM Strategy)     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Execution Runtime    │
              └───────────────────────┘
```

---

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

---

## 环境变量

```bash
# 强制使用特定设备
export TORCH_DEVICE=cuda   # NVIDIA GPU
export TORCH_DEVICE=mps    # Apple Silicon
export TORCH_DEVICE=cpu    # CPU only
```

---

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

---

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

---

## 重要更新记录（2026-05-22）

### 已删除
- ❌ `scripts/gpu_feature_backtest.py` - 绕过 Runtime
- ❌ `scripts/gpu_optimize_backtest.py` - 绕过 Runtime
- ❌ `application/optimization_service/parallel_engine.py` - 绕过 Runtime

### 保留
- ✅ `shared/acceleration/` - GPU 基础设施
- ✅ `domain/feature/torch_calculator.py` - GPU 特征计算器
- ✅ `domain/strategy/lstm_strategy.py` - LSTM 策略
- ✅ 所有 Runtime 模块

### 必须遵循的原则
1. **所有 GPU 计算必须走 Runtime 主链**
2. **所有回测必须走 replay_runtime**
3. **所有优化必须走 OptimizationBacktestEngine（走 Runtime）**
