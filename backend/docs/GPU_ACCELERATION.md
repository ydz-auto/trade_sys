# GPU 加速指南

## 概述

本项目使用 **PyTorch** 作为统一的 GPU 加速框架，支持：

| 平台 | 后端 | 设备 |
|------|------|------|
| Windows/Linux + NVIDIA GPU | CUDA | RTX 2060S, RTX 3080, etc. |
| Mac M1/M2/M3/M4 | MPS | Apple Silicon |
| 任何平台 | CPU | NumPy fallback |

> **重要更新（2026-05-23）**：  
> GPU 加速模块已完成架构收敛：`infrastructure/acceleration/`（基础设施）、`services/feature_service/torch_calculator.py`（特征计算）、`services/research_service/lstm_strategy.py`（LSTM 策略）。

---

## 架构兼容性

### 与六层架构的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Server                              │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION                              │
│  Commands / Queries / Workflows (OptimizationService)           │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                     RUNTIME LAYER                               │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ FeatureRuntime   │  │ SignalRuntime    │  │ ReplayRuntime│  │
│  │ (特征生成/守卫)  │  │ (信号生成)       │  │ (回放)       │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
└───────────┼──────────────────────┼───────────────────┼──────────┘
            ↓                      ↓                   ↓
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICES                                 │
│  ┌──────────────────────────┐  ┌────────────────────────────┐  │
│  │ feature_service/         │  │ research_service/          │  │
│  │ torch_calculator.py      │  │ lstm_strategy.py           │  │
│  │ (GPU 特征计算)           │  │ (GPU LSTM 训练/推理)       │  │
│  └──────────────────────────┘  └────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌──────────────────────┐  ┌───────────────────────────────────────┐
│       DOMAIN         │  │          INFRASTRUCTURE                │
│  (纯交易规则)        │  │  acceleration/  (GPU 基础设施)        │
│  零外部依赖          │  │  http/          (HTTP 客户端)          │
│                      │  │  llm/           (LLM 客户端)          │
└──────────────────────┘  └───────────────────────────────────────┘
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
| `feature_runtime` | ✅ 支持 | 特征计算 | ✅ CPU fallback |

### 各 Service GPU 加速状态

| Service | GPU 加速 | 多线程/并行 | 功能 | 自动降级 |
|---------|---------|------------|------|---------|
| `backtest_service` | ✅ 通过 replay_runtime | ✅ asyncio.gather | 回测 | ✅ CPU fallback |
| `feature_service` | ✅ 原生 GPU | - | GPU 特征计算 | ✅ CPU fallback |
| `research_service` | ✅ 原生 GPU | - | LSTM 策略 | ✅ CPU fallback |
| `optimization_service` | ✅ 通过 OptimizationBacktestEngine | ✅ asyncio.gather + Semaphore | 优化 | ✅ CPU fallback |
| `execution_service` | ❌ 不需要 | - | 订单执行 | - |
| `data_service` | ❌ 不需要 | - | 数据采集 | - |

### GPU 模块分布

| 模块 | 位置 | GPU 加速 | 自动降级 |
|------|------|---------|---------|
| `acceleration/` | `infrastructure/acceleration/` | GPU 基础设施 | ✅ CPU fallback |
| `torch_calculator` | `services/feature_service/torch_calculator.py` | GPU 向量化特征计算 | ✅ CPU fallback |
| `unified_calculator` | `runtime/feature_runtime/unified_calculator.py` | 委托 TorchFeatureCalculator | ✅ CPU fallback |
| `matrix_builder` | `domain/feature/materializer/matrix_builder.py` | GPU 批量前向填充 | ✅ CPU fallback |
| `lstm_strategy` | `services/research_service/lstm_strategy.py` | GPU LSTM 训练/推理 | ✅ CPU fallback |

---

## 关键架构原则

### 1. **GPU 是基础设施，不是独立系统！**
```
✅ 正确方式：
  replay_runtime → feature_runtime → services/feature_service/torch_calculator → infrastructure/acceleration/ → GPU

❌ 错误方式：
  scripts/gpu_feature_backtest.py → 直接pandas → 独立运行
```

### 2. **所有回测必须走 Runtime 主链！**
```
✅ 正确方式：
  application/optimization_service/engine.py → replay_runtime

❌ 错误方式：
  application/optimization_service/parallel_engine.py → 直接pandas
```

### 3. **依赖方向必须合规！**
```
✅ 正确：
  services/feature_service → infrastructure/acceleration  (Services → Infrastructure)
  runtime/feature_runtime  → services/feature_service     (Runtime → Services via DI)

❌ 错误：
  domain/ → infrastructure/  (Domain 零外部依赖)
  domain/ → services/        (Domain 零外部依赖)
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
from infrastructure.acceleration import device, is_gpu, get_accelerator_info

info = get_accelerator_info()
print(f"Device: {info['device_type']}")
print(f"Is GPU: {info['is_gpu']}")
print(f"Device Info: {info['device_info']}")
```

### 2. 通过 Runtime 使用 GPU（推荐！唯一方式！）

#### 2.1 回测（走 replay_runtime）
```python
from runtime.replay_runtime.shared_replay.orchestrator import ReplayOrchestrator

orchestrator = ReplayOrchestrator()
# GPU 加速由 infrastructure/acceleration/ 自动处理
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
from services.feature_service.torch_calculator import TorchFeatureCalculator

calculator = TorchFeatureCalculator()

# 方式1: DataFrame 输入输出
features_df = calculator.compute_batch(df, use_gpu=True)

# 方式2: GPU Tensor 输入输出（零拷贝，适合 LSTM）
from infrastructure.acceleration import to_gpu

closes = to_gpu(df['close'].values)
highs = to_gpu(df['high'].values)
lows = to_gpu(df['low'].values)
volumes = to_gpu(df['volume'].values)

features = calculator.compute_batch_tensor(closes, highs, lows, volumes)
# features 是 Dict[str, torch.Tensor]，数据在 GPU 上
```

### 4. LSTM 策略

```python
from services.research_service.lstm_strategy import LSTMStrategyBuilder

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

## 架构（GPU 数据流）

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
              │ Feature Runtime       │
              │ (特征生成/守卫/物化)  │
              └───────────┬───────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │  services/feature_service/               │
        │  torch_calculator.py                     │
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

### infrastructure.acceleration

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
from services.feature_service.torch_calculator import TorchFeatureCalculator

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
from services.research_service.lstm_strategy import LSTMStrategyBuilder

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
from infrastructure.acceleration import clear_cache

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

## 重要更新记录

### 2026-05-23 架构收敛

#### 迁移
- ✅ `shared/acceleration/` → `infrastructure/acceleration/` — GPU 基础设施归入 Infrastructure 层
- ✅ `domain/feature/torch_calculator.py` → `services/feature_service/torch_calculator.py` — GPU 特征计算归入 Services 层
- ✅ `domain/strategy/lstm_strategy.py` → `services/research_service/lstm_strategy.py` — LSTM 策略归入 Services 层
- ✅ `domain/feature/unified_calculator.py` → `runtime/feature_runtime/unified_calculator.py` — 统一计算器归入 Runtime 层
- ✅ `shared/` 层完全消亡，所有模块已迁移至正确的架构层

#### 必须遵循的原则
1. **所有 GPU 计算必须走 Runtime 主链**
2. **所有回测必须走 replay_runtime**
3. **所有优化必须走 OptimizationBacktestEngine（走 Runtime）**
4. **Domain 层零外部依赖，不包含 GPU 逻辑**
5. **GPU 基础设施在 infrastructure/acceleration/，特征计算在 services/feature_service/**

### 2026-05-22 加速改造

#### 新增
- ✅ `UnifiedFeatureCalculator` 委托 `TorchFeatureCalculator` 实现 GPU 加速
- ✅ `UnifiedMatrixBuilder` 多线程并行对齐填充（ThreadPoolExecutor）
- ✅ `UnifiedMatrixBuilder` GPU 批量前向填充（大数据量 > 10000 行）
- ✅ `OptimizationService` asyncio.gather 并行参数优化（走 Runtime 主链）
- ✅ `OptimizationBacktestEngine` GPU 特征计算加速
- ✅ `backtest_service.run_parallel_optimization` 改用 asyncio.gather（走 Runtime 主链）

#### 修复
- ✅ 清理 `backtest_engine.py` 对已删除 `parallel_engine.py` 的幽灵引用

### 2026-05-22 架构收敛（旧）

#### 已删除
- ❌ `scripts/gpu_feature_backtest.py` - 绕过 Runtime
- ❌ `scripts/gpu_optimize_backtest.py` - 绕过 Runtime
- ❌ `application/optimization_service/parallel_engine.py` - 绕过 Runtime
