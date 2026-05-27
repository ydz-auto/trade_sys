# MarketContext 统一架构（强制收敛）

## 问题识别（用户洞察）

您发现了关键问题：
- ❌ **状态机没有成为权威**：MarketStateMachine 只是一个库，不是系统内核
- ❌ **双 context 体系**：旧系统有分散的隐式上下文，新系统有显式状态机，两者并行
- ❌ **策略自己解释市场**：每个策略都在自己理解市场，没有统一的解释
- ❌ **危险的中间状态**：不是迁移中，而是系统在分裂

## 解决方案（强制收敛）

### 路线 B（推荐）：强制内核化

核心原则：
1. **MarketContext 是唯一真相源（Single Source of Truth）**
2. **禁止策略自己解释市场，只能消费 MarketContext**
3. **所有 runtime（LIVE/REPLAY/RESEARCH）对齐到 MarketContext**
4. **V1 策略通过 Adapter 访问 MarketContext**

---

## 架构图（新架构）

```
                    ┌──────────────────────────────────┐
                    │          Market Data             │
                    │  (LIVE/REPLAY/RESEARCH feed)    │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │     Event Adapter Layer          │
                    │  (consistent for all modes)      │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │         Event Flow               │
                    └──────────────┬───────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        │  ┌───────────────────────▼───────────────────────┐ │
        │  │       MarketContextAuthority (唯一)           │ │
        │  │         • 更新唯一真相源                      │ │
        │  │         • 确保所有 runtime 对齐               │ │
        │  └───────────────┬───────────────────────────────┘ │
        │                  │                                  │
        │  ┌───────────────▼───────────────────────────────┐ │
        │  │      MarketStateMachine (被包装)               │ │
        │  └───────────────┬───────────────────────────────┘ │
        │                  │                                  │
        │  ┌───────────────▼───────────────────────────────┐ │
        │  │         MarketContext (只读)                   │ │
        │  │  • Core: MarketState (显式状态)                │ │
        │  │  • Features: Snapshot (辅助)                   │ │
        │  │  • Semantic APIs: is_exhausted(), etc.        │ │
        │  └───────────────┬───────────────────────────────┘ │
        │                  │                                  │
        └──────────────────┼──────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
    ┌───────▼──────┐ ┌────▼──────┐ ┌────▼────────┐
    │   V2 Strategy│ │V1 Strategy│ │V1 Strategy  │
    │ (Native)     │ │(Wrapper)  │ │(Wrapper)    │
    └───────┬──────┘ └────┬──────┘ └────┬────────┘
            │              │             │
            └──────────────┼─────────────┘
                           │
                    ┌──────▼──────────┐
                    │Signal Orchestrator│
                    └─────────────────┘
```

---

## 核心组件说明

### 1. MarketContext（统一市场上下文）

位置：`domain/market_state/context.py`

关键特性：
- ✅ **只读对象**：策略不能修改，只能消费
- ✅ **语义化 API**：`is_exhausted()`, `is_liquid_vacuum()`, 等
- ✅ **分层设计**：
  - `core`：MarketState（来自状态机）
  - `features`：特征快照（辅助）
  - `recent_events`：最近事件列表

```python
# ✅ 正确：策略只消费语义化接口
if market_context.is_exhausted() and market_context.is_liquid_vacuum():
    signal = create_signal()

# ❌ 错误：策略自己解释市场
if features['pressure_zscore'] < -3 and features['bid_ask_spread'] > 2:
    signal = create_signal()
```

### 2. MarketContextAuthority（唯一真相源）

位置：`domain/market_state/context.py`

关键特性：
- ✅ **唯一更新入口**：所有状态更新必须经过这里
- ✅ **强制依赖**：DomainKernel 不能绕过它
- ✅ **历史记录**：保留上下文历史，用于回放验证

```python
# ✅ 正确：通过 Authority 更新
context = context_authority.update(event, features, timestamp)

# ❌ 错误：直接修改状态机
state_machine.update(...)  # 禁止！
```

### 3. DomainKernel（强制内核）

位置：`runtime/kernel/unified/domain_kernel.py`

关键变化：
- ✅ **强制依赖**：不再可选 `state_machine_enabled`
- ✅ **强制流程**：Event → Context → Strategy
- ✅ **只读接口**：只能通过 `get_current_context()` 访问

```python
# ✅ 正确的强制流程
async def handle_event(self, event, features):
    # 1. 时间来自 ClockAuthority
    current_time = get_time_from_clock()
    
    # 2. 状态来自 MarketContextAuthority（唯一）
    market_context = self._context_authority.update(event, features, current_time)
    
    # 3. 策略只能消费 MarketContext
    for strategy in strategies:
        signal = strategy.generate_signal(market_context, event, features)
```

### 4. V1StrategyAdapter（V1 策略适配器）

位置：`engines/compute/strategy/v1_adapter.py`

作用：
- ✅ 把 MarketContext → V1 策略期望的格式
- ✅ 渐进式迁移：旧策略不需要立即重写
- ✅ 最终目标：慢慢废弃 Adapter，全部迁移 V2

---

## 强制约束（重要）

### 约束 1：禁止策略自己解释市场

```python
# ❌ 错误：策略自己理解市场
if features['pressure_zscore'] < -3:  # 自己定阈值
    signal = Signal(...)

# ✅ 正确：策略消费 MarketContext
if market_context.is_exhausted():  # 统一解释
    signal = Signal(...)
```

### 约束 2：禁止绕过 MarketContextAuthority

```python
# ❌ 错误：直接修改状态机
self._state_machine.update(event_type, features)

# ✅ 正确：通过 Authority 更新
market_context = self._context_authority.update(event, features, timestamp)
```

### 约束 3：特征退化为观察输入

```python
# 旧观念：Feature → Strategy → Signal（直接决策）

# 新观念：Feature → MarketContext（隐式→显式）→ Strategy → Signal（消费）
```

---

## 迁移路径（渐进式）

### Phase 1：验证（1-2 天）
- 运行示例验证架构
- 理解强制约束

### Phase 2：核心策略包装（3-5 天）
- 把 Top 5 V1 策略包装成 V1Wrapper
- 在现有系统并行运行

### Phase 3：引擎集成（5-7 天）
- 在现有 runtime 集成 DomainKernel
- 保持现有 V1 工作，新 flow 走统一架构

### Phase 4：策略迁移（2-3 周）
- 逐个把 Top 策略从 V1 迁移到 V2
- 废弃 V1Wrapper

---

## 总结（关键）

### 解决的问题
- ❌ → ✅ 状态机从库变成权威内核
- ❌ → ✅ 双 context 体系合并为单一真相源
- ❌ → ✅ 策略从解释市场变成消费市场

### 核心原则
1. **单一真相源**：MarketContext 是唯一解释
2. **事件驱动**：Context 只通过事件更新
3. **分层消费**：策略只读，不能修改
4. **三范式对齐**：LIVE/REPLAY/RESEARCH 完全一致

---

## 相关文档
- [MarketStateMachine 迁移计划](./MARKET_STATE_MACHINE_MIGRATION_PLAN.md)
- [三范式统一架构](./THREE_PARADIGM_UNIFIED_RUNTIME.md)
- [最终策略计划](./FINAL_STRATEGY_PLAN.md)
- [时钟使用规范](./CLOCK_AUTHORITY_USAGE_GUIDE.md)
