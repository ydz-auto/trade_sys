# 三范式统一运行时架构

> 基于您提出的核心洞察：**统一 Domain Kernel，不统一执行方式**

---

## 📋 核心原则

1. **统一 Domain Kernel** - LIVE/REPLAY/RESEARCH 共享同一套业务逻辑
2. **三个 Adapter，不是三套系统** - 仅连接外部系统的方式不同
3. **策略完全不知道范式** - 策略代码不感知是 LIVE/REPLAY/RESEARCH
4. **禁止策略分叉** - 永远不要写 `if mode == LIVE: ...`

---

## 🏗️ 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               外部系统层                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐             │
│  │  实时市场数据  │  │  历史数据存储  │  │  批量研究数据      │             │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬───────────┘             │
└─────────┼──────────────────┼────────────────────┼─────────────────────────┘
          │                  │                    │
┌─────────┼──────────────────┼────────────────────┼─────────────────────────┐
│         │                  │                    │                         │
│  ┌──────▼───────┐  ┌───────▼──────┐  ┌────────▼──────────┐             │
│  │   LIVE      │  │   REPLAY     │  │   RESEARCH        │             │
│  │  Adapter    │  │   Adapter    │  │   Adapter         │             │
│  └──────┬──────┘  └───────┬──────┘  └────────┬───────────┘             │
│         │                  │                   │                         │
└─────────┼──────────────────┼───────────────────┼─────────────────────────┘
          │                  │                   │
          └──────────────────┼───────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────────┐
│                          Domain Kernel（唯一）                              │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │Market State      │  │  Event Detectors │  │  V2 Strategies       │  │
│  │  Machine        │  │                  │  │                       │  │
│  └──────────────────┘  └──────────────────┘  └───────────────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Clock Authority + Runtime Bus + Guards                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘

关键点：
1. LIVE/REPLAY/RESEARCH 使用完全相同的 Domain Kernel 代码
2. 仅 Adapter 不同，分别连接不同的外部系统
3. 策略完全不知道是 LIVE/REPLAY/RESEARCH
```

---

## 📁 目录结构

```
backend/
├── domain/
│   ├── config/                      # 统一配置类型（新增）
│   │   ├── __init__.py
│   │   ├── strategy_config.py
│   │   ├── feature_config.py
│   │   ├── runtime_config.py
│   │   └── execution_config.py
│   ├── market_state/                # Market State Machine（新增）
│   │   ├── __init__.py
│   │   ├── state.py
│   │   └── machine.py
│   ├── event/
│   │   ├── event_type.py            # 已扩展
│   │   └── base_event.py
│   └── feature/
│       └── indicators/
│           └── trade_pressure.py    # Trade Pressure 事件检测器（新增）
│
├── engines/
│   └── compute/
│       └── strategy/
│           ├── v2_base.py           # V2 策略基类（新增）
│           ├── v2_core_strategies.py # V2 核心策略（新增）
│           └── v2_orchestrator.py   # 多策略编排器（新增）
│
├── runtime/
│   └── kernel/
│       ├── unified/                 # 三范式统一运行时（新增）
│       │   ├── __init__.py
│       │   ├── runtime_contract.py  # 强约束契约
│       │   ├── domain_kernel.py     # 唯一业务真相
│       │   └── adapters.py          # 三个 Adapter
│       ├── authority/               # 已有：ClockAuthority 等
│       ├── event/                   # 已有：RuntimeBus
│       └── ...                      # 其他已有组件
│
└── docs/
    ├── THREE_PARADIGM_UNIFIED_RUNTIME.md  # 本文档
    ├── FINAL_STRATEGY_PLAN.md
    └── ...
```

---

## 🔑 核心组件详解

### 1. Runtime Contract（runtime_contract.py）

定义所有 Adapter 必须遵守的强约束：

```python
class RuntimeAdapter(ABC):
    @abstractmethod
    async def initialize(self) -> bool: ...
    
    @abstractmethod
    async def run(self) -> None: ...
    
    @abstractmethod
    async def shutdown(self) -> None: ...
    
    @abstractmethod
    def publish_event(self, event: BaseEvent) -> None: ...
```

### 2. Domain Kernel（domain_kernel.py）

唯一的业务真相，三范式共享：

```python
class DomainKernel:
    """
    Domain Kernel - 唯一的业务真相
    
    核心职责：
    1. 管理 Market State Machine
    2. 管理策略实例（三范式共享）
    3. 处理事件 -> 状态转换 -> 信号生成
    4. 完全不区分 LIVE/REPLAY/RESEARCH
    """
    
    async def handle_event(self, event: BaseEvent, features: Dict[str, Any]) -> None:
        """
        处理事件（唯一入口）
        
        策略完全不知道是 LIVE/REPLAY/RESEARCH
        """
        # Step 1: 更新状态机
        # Step 2: 运行策略生成信号
        # Step 3: 发布结果事件
```

### 3. 三个 Adapter（adapters.py）

#### LiveRuntimeAdapter

- **时钟来源**: `ClockAuthority.LIVE` (wall clock)
- **事件来源**: 实时市场数据流
- **执行**: 真实交易所连接

#### ReplayRuntimeAdapter

- **时钟来源**: `ClockAuthority.REPLAY` (手动控制)
- **事件来源**: 历史数据回放
- **执行**: 模拟执行

#### ResearchRuntimeAdapter

- **时钟来源**: `ClockAuthority.REPLAY` (手动控制)
- **事件来源**: 批量历史数据
- **执行**: 无执行，专注研究

---

## 💡 使用示例

### LIVE 模式（实盘/模拟盘）

```python
from runtime.kernel.unified import (
    create_runtime_adapter,
    RuntimeMode,
)

# 创建 LIVE Adapter
adapter = create_runtime_adapter(
    mode=RuntimeMode.LIVE,
    symbol="BTCUSDT",
)

# 初始化并运行
await adapter.initialize()
await adapter.run()
```

### REPLAY 模式（历史回放）

```python
from runtime.kernel.unified import (
    create_runtime_adapter,
    RuntimeMode,
)

# 创建 REPLAY Adapter
adapter = create_runtime_adapter(
    mode=RuntimeMode.REPLAY,
    symbol="BTCUSDT",
    start_time_ms=1717228800000,
    end_time_ms=1717315200000,
)

# 初始化并运行
await adapter.initialize()
await adapter.run()
```

### RESEARCH 模式（离线研究）

```python
from runtime.kernel.unified import (
    create_runtime_adapter,
    RuntimeMode,
)

# 创建 RESEARCH Adapter
adapter = create_runtime_adapter(
    mode=RuntimeMode.RESEARCH,
    symbol="BTCUSDT",
)

# 初始化并运行
await adapter.initialize()
await adapter.run()

# 获取研究结果
results = adapter.get_results()
```

---

## ⚠️ 关键禁止事项

### ❌ 禁止：策略感知范式

```python
# ❌ 绝对禁止！
if runtime_mode == RuntimeMode.LIVE:
    do_something()
elif runtime_mode == RuntimeMode.REPLAY:
    do_something_else()

# ✅ 正确：策略只看到 Event + State
signal = strategy.generate_signal_v2(
    market_state=current_state,
    triggering_event=event,
    current_features=features,
)
```

### ❌ 禁止：两套业务逻辑

```python
# ❌ 绝对禁止！
# 不要在 Adapter 里写业务逻辑！
class LiveRuntimeAdapter:
    def some_business_logic(self):
        # 这是 Kernel 的职责！
        ...

# ✅ 正确：所有业务在 Domain Kernel 中
```

### ❌ 禁止：直接调用 `datetime.now()`

```python
# ❌ 禁止！
now = datetime.datetime.now()

# ✅ 正确：通过 ClockAuthority
now = clock_authority.now_ms()
```

---

## 🚀 迁移计划

### Phase 1: 核心组件就绪（已完成 ✅）

- ✅ 统一配置类型
- ✅ 扩展 EventType（Trade Pressure 事件）
- ✅ Market State Machine
- ✅ V2 策略基类
- ✅ 三个 Runtime Adapter
- ✅ Domain Kernel

### Phase 2: 策略迁移（下一步）

1. **迁移 Top 5 策略到 V2 架构**
   - OpenInterestBehavior → OpenInterestBehaviorV2
   - TradePressureExhaustion → TradePressureExhaustionV2
   - ...

2. **并行运行 V1 和 V2**
   - 验证行为一致性
   - 逐步淘汰 V1

3. **归档 Legacy 策略**
   - 标记为 `legacy_*`
   - 默认禁用
   - 保留用于历史对比

### Phase 3: 集成与验证

1. **集成到现有运行时**
2. **回测验证一致性**
3. **实盘测试**

---

## 📊 架构对比

| 维度 | 之前（可能分裂） | 现在（统一） |
|-----|-----------------|------------|
| 业务逻辑 | 可能三套代码 | 一套 Domain Kernel |
| 策略代码 | 可能感知范式 | 完全不知道范式 |
| 时钟来源 | 可能不统一 | 统一 ClockAuthority |
| 事件模型 | 可能不统一 | 统一 BaseEvent + EventType |
| 可维护性 | 高（三套代码） | 低（一套代码） |
| 可复现性 | 可能不一致 | 完全一致 |

---

## 🎯 总结

### 我们解决了什么

1. ✅ **参数管理问题** - 统一配置类型，不再是散装 `params`
2. ✅ **Event vs Signal 问题** - Trade Pressure 现在产生事件，不是直接信号
3. ✅ **Market State 问题** - 统一的 Market State Machine
4. ✅ **三范式分裂问题** - 统一 Kernel + 三个 Adapter

### 核心思想

```
三套范式不是三套系统，而是
同一套 Domain Kernel + 三个 Runtime Adapter
```

### 最终目标

- LIVE 策略 ≡ REPLAY 策略 ≡ RESEARCH 策略
- 代码完全一致，仅数据源不同
- 100% 可复现性，可追溯性
