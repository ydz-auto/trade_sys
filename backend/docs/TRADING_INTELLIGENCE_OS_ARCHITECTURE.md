# 交易智能操作系统架构 - 2026-05-22 (最终收敛版)

## 总览

系统已经从原型进化为**分布式事件驱动交易操作系统**，完成了架构收敛，清理了所有绕过 Runtime 的代码。

## 核心架构图

```
┌───────────────────────────────────────────────────────────────────────┐
│                      Frontend / UI 层                                │
└────────────────────────────────────────┬──────────────────────────────┘
                                         │
                                         ↓
                              ┌───────────────────────┐
                              │ API Gateway / WS     │
                              │ Gateway              │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Runtime State Store  │
                              │ (唯一真实状态源)     │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Projection Runtime   │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Portfolio Runtime    │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Execution Runtime    │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Signal Runtime       │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Feature Matrix      │
                              │ Runtime (核心真理)   │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Runtime Bus         │
                              │ (唯一事件总线)       │
                              └───────────┬───────────┘
                                          │
                                          ↓
                              ┌───────────────────────┐
                              │ Ingestion Runtime    │
                              └───────────┬───────────┘
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────────┐
│           Data Service (事实层)          │                                       │
│  ┌──────────────┐  ┌──────────────┐  │                                       │
│  │ Collectors   │  │ WebSocket    │  │                                       │
│  │ Pipeline     │  │ Kafka        │  │                                       │
│  └──────────────┘  └──────────────┘  │                                       │
└─────────────────────────────────────────┘
                                          │
                                          ↓
                        ┌───────────────────────────────┐
                        │ Exchange / Replay             │
                        │ (真实或回放数据)             │
                        └───────────────────────────────┘

```

## 核心闭环

### Data → Ingestion → Runtime Bus → Feature Matrix → Signal → Execution → Portfolio → Projection → UI

这是现在系统的**完整智能闭环**，所有模块统一通过 Runtime 架构。

---

## 核心 Runtime 模块详解 (已收敛完成)

### 1. runtime/bus/ - 唯一事件总线
```
runtime/bus/
└── runtime_bus.py       # 统一事件总线，替代了旧的 EventBus
```
**关键特性：**
- 统一事件发布订阅
- 支持所有 Runtime 模块通信
- 完全移除了旧的事件总线兼容层

---

### 2. runtime/orchestrator/ - Runtime 内核
```
runtime/orchestrator/
├── manager.py          # 管理器
├── supervisor.py       # 监管器
├── lifecycle.py        # 生命周期
├── timeline.py         # 时间线
├── inspector.py        # 检查器
└── registry.py         # 注册表
```

**关键特性：**
- Runtime 全局协调
- 所有 Runtime 模块的生命周期管理
- 统一健康监控

---

### 3. runtime/feature_matrix_runtime.py - 核心特征层
```
runtime/
└── feature_matrix_runtime.py  # 特征矩阵 Runtime (核心真理层)
```

**关键特性：**
- 所有特征的统一管理
- 与 GPU 加速层（shared/acceleration）集成
- 支持点进点出 (Point-in-Time)

---

### 4. runtime/signal_runtime/ - 信号生成 Runtime
```
runtime/signal_runtime/
├── runtime.py
├── consumer.py
├── publisher.py
├── metrics.py
└── lifecycle.py
```

---

### 5. runtime/execution_runtime/ - 执行 Runtime
```
runtime/execution_runtime/
├── runtime.py
```

---

### 6. runtime/portfolio_runtime/ - 仓位 Runtime
```
runtime/portfolio_runtime/
└── __init__.py
```

---

### 7. runtime/projection_runtime/ - 投影 Runtime
```
runtime/projection_runtime/
└── runtime.py
```

---

### 8. runtime/replay_runtime/ - 唯一回测入口
```
runtime/replay_runtime/
└── runtime.py
```

---

### 9. shared/acceleration/ - GPU 基础设施 (已保留！)
```
shared/acceleration/
└── __init__.py        # 统一 PyTorch GPU 加速层
                       # - CUDA (NVIDIA)
                       # - MPS (Apple Silicon)
                       # - CPU fallback
```

---

### 10. shared/replay/ - 统一回放层
```
shared/replay/
├── orchestrator.py        # 回放编排器
├── market_event_emitter.py # 事件发射器
├── replay_manager.py      # 回放管理器
├── rebuild_manager.py     # 重建管理器
├── event_store.py        # 事件存储
└── models.py            # 模型
```

---

## 完整系统结构 (已清理完成)

```
backend/
├── api/                    # API 层
├── application/            # 应用层
│   ├── optimization_service/  # 参数优化服务 (走 Runtime!)
│   └── services/
├── domain/                 # 领域层
│   ├── feature/            # 特征领域
│   │   └── torch_calculator.py # GPU 特征计算器
│   ├── signal/             # 信号领域
│   ├── execution/          # 执行领域
│   │   └── intelligence/   # 执行智能
│   ├── replay/             # 回放领域
│   ├── portfolio/          # 组合领域
│   └── analysis/           # 分析领域
├── runtime/                # 运行时层 (收敛完成！)
│   ├── ingestion_runtime/
│   ├── feature_matrix_runtime.py
│   ├── signal_runtime/
│   ├── execution_runtime/
│   ├── portfolio_runtime/
│   ├── projection_runtime/
│   ├── replay_runtime/
│   ├── correlation_runtime/
│   ├── regime_runtime/
│   ├── narrative_runtime/
│   ├── orchestrator/       # Runtime Kernel
│   ├── bus/               # 唯一总线
│   ├── context/           # Runtime 上下文
│   └── state/             # 状态存储
├── services/               # 服务层
│   ├── data_service/       # 数据服务 (事实层，保留！)
│   ├── backtest_service/   # 回测服务 (facade 层)
│   ├── event_service/      # 事件服务
│   ├── execution_service/
│   └── risk_service/
├── infrastructure/         # 基础设施层 (成熟！)
│   ├── event/             # 事件基础设施
│   ├── feature/           # 特征基础设施
│   ├── replay/            # 回放基础设施
│   ├── observability/     # 可观测性
│   └── runtime/           # Runtime 基础设施
├── research/               # 研究层 (已清理)
│   └── __init__.py
├── scripts/                # 脚本 (已清理)
│   ├── check_gpu.py
│   ├── download_*.py
│   └── test_api_optimization.py
└── config/
```

---

## 数据流向闭环 (收敛后唯一路径)

### 1. 数据摄入
```
Exchange / Replay → ingestion_runtime → Runtime Bus
```

### 2. 特征工程
```
Runtime Bus → Feature Materializer → Feature Matrix Runtime
```

### 3. 信号生成
```
Feature Matrix Runtime → Signal Runtime
```

### 4. 执行与组合
```
Signal Runtime → Execution Runtime → Portfolio Runtime
```

### 5. 状态投影
```
Execution / Portfolio → Projection Runtime → Runtime State Store → API/WS → Frontend
```

---

## 清理完成总结 (2026-05-22)

### 已删除的遗留模块：
- ❌ `research/backtest/` - 旧 pandas 回测
- ❌ `research/correlation/` - 绕过 Runtime 的研究
- ❌ `research/factor/` - 绕过 Runtime 的因子
- ❌ `scripts/gpu_feature_backtest.py` - 独立 GPU 回测
- ❌ `scripts/gpu_optimize_backtest.py` - 独立 GPU 优化
- ❌ `application/optimization_service/parallel_engine.py` - 绕过 Runtime 的并行引擎
- ❌ `runtime/monitoring_runtime/` - 独立监控 Runtime
- ❌ `runtime/scheduler_runtime/` - wrapper 调度 Runtime
- ❌ `services/data_service/event_bus/` - 旧事件总线 (作为兼容层保留但不推荐)
- ❌ `api/services/replay_service.py` - 独立回放服务

### 保留的核心模块：
- ✅ `shared/acceleration/` - GPU 基础设施
- ✅ `shared/replay/` - 统一回放层
- ✅ 所有 Runtime 模块
- ✅ `services/data_service/` - 事实层
- ✅ 所有 Infrastructure 层

---

## 架构收敛原则

### 唯一总线原则
- `runtime/bus/runtime_bus.py` 是唯一的事件总线

### 唯一回测入口
- `runtime/replay_runtime/` 是唯一的回测入口

### GPU 是基础设施
- GPU 加速层 (`shared/acceleration`) 是基础设施，不是独立系统
- 所有 GPU 计算必须走 Runtime 架构

### 单一真实状态
- `runtime/state/` 是唯一的真实状态存储

---

## 下一阶段建议

### 第一阶段：Runtime 深化
- [ ] Runtime Dependency Graph - Runtime 依赖图
- [ ] Runtime DAG Scheduler - Runtime 有向无环图调度
- [ ] Runtime Metrics - Runtime 指标
- [ ] Runtime Tracing - Runtime 追踪
- [ ] Runtime Health Check - Runtime 健康检查
- [ ] Runtime Recovery - Runtime 恢复

### 第二阶段：Runtime 完善
- [ ] Runtime Snapshot Recovery - 快照恢复
- [ ] Runtime Persistence - 持久化
- [ ] Runtime Resource Isolation - 资源隔离

---

## 总结

系统现在已经完全收敛，成为真正的 **Runtime-Oriented Trading OS**！

核心优势：
- ✅ 唯一事件总线 (Runtime Bus)
- ✅ 唯一回测入口 (Replay Runtime)
- ✅ 统一 GPU 基础设施
- ✅ 清除所有绕过 Runtime 的代码
- ✅ 清晰的架构边界
