# P0: Runtime 收敛方案（第一阶段）

> **核心理念**：不要横向加功能，要纵向收敛 Runtime
> 
> **目标**：让系统变得「可信」—— 所有东西都建立在正确的时间线上

---

## 📋 P0 必做清单（极高优先级）

| 序号 | 模块 | 重要性 | 验收标准 |
|------|------|--------|----------|
| 1 | **Event Protocol** | 🔴 极高 | 三种时间语义完整 |
| 2 | **Immutable Event** | 🔴 极高 | 事件不可变，有修改检测 |
| 3 | **Availability Time** | 🔴 极高 | 特征可用性验证，泄漏检测 0 阳性 |
| 4 | **Replay = Live** | 🔴 极高 | 两者输出一致性 ≥ 99% |
| 5 | **Runtime Lifecycle** | 🔴 极高 | 生命周期状态机完整 |
| 6 | **Event Ordering** | 🔴 极高 | 事件因果顺序严格 |
| 7 | **Runtime Audit** | 🔴 极高 | 全链路审计系统 |

---

## 🎯 P0 核心目标

### 你现在的真正核心资产
```
1. Runtime (统一 Backtest/Replay/Paper/Live)
2. Feature System (统一 Historical/Realtime/Materialized/Streaming)
3. Event Semantics (统一时间/顺序/因果)
4. Research Infrastructure (统一验证方法)
```

### 这四个决定了你的系统上限

---

## 📐 P0-1: Event Protocol 完善

### 三种时间语义

```
┌─────────────────────────────────────────────────────────┐
│                     Event Time Semantics                  │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │ event_time   │ →  │available_time│ →  │process_time │ │
│  │ (发生时间)   │    │ (可用时间)   │    │ (处理时间)  │ │
│  └──────────────┘    └──────────────┘    └─────────────┘ │
│         │                  │                  │          │
│         │                  │                  │          │
│    数据产生          特征可用          策略使用        │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### 时间语义规则

| 时间类型 | 定义 | 约束 |
|---------|------|------|
| `event_time` | 事件实际发生时间（交易所时间） | 严格递增 |
| `available_time` | 特征可用时间（通常 = event_time + 延迟） | ≥ event_time |
| `processing_time` | 系统处理时间 | ≥ available_time |

### 关键约束
1. **策略只能看到 available_time ≤ processing_time 的事件**
2. **feature_time 是计算该特征的最新 event_time**
3. **Replay 模式下，processing_time = replay_clock**

---

## 🔒 P0-2: Immutable Event

### 设计原则
- 事件一旦创建，**任何字段都不可修改**
- 任何修改尝试都会被检测并拒绝
- 事件有 cryptographic hash 验证完整性

### Immutable Event 结构
```python
@dataclass(frozen=True)  # frozen=True 保证不可变
class ImmutableEvent:
    event_id: str              # 唯一标识
    event_type: EventType
    symbol: str
    exchange: str
    
    # 三种时间语义
    event_time_ms: int         # 事件发生时间
    available_time_ms: int     # 特征可用时间
    processing_time_ms: int    # 系统处理时间
    
    # 数据载荷
    payload: FrozenDict[str, Any]
    
    # 完整性验证
    verification_hash: str     # 内容哈希
    created_at_ms: int         # 创建时间（不可变）
```

---

## ⏰ P0-3: Availability Time

### Feature Availability 规则

每个特征都必须明确：
1. **feature_time**: 特征计算的时间戳（源数据时间）
2. **available_after**: 特征需要多少时间才可用
3. **available_time**: feature_time + available_after

### 泄漏检测矩阵

| 检查点 | 检测内容 | 严重程度 |
|--------|----------|----------|
| replay_clock < available_time | 提前使用特征 | Critical |
| feature 依赖 future 数据 | 未来数据泄漏 | Critical |
| 状态回滚不一致 | 时间旅行错误 | High |

---

## 🔄 P0-4: Replay = Live

### 验证维度

| 维度 | Replay | Live | 要求 |
|------|--------|------|------|
| Event Ordering | 严格按时间 | 严格按时间 | ✅ 一致 |
| Feature Calculation | 离线计算 | 在线计算 | ✅ 一致 |
| Signal Generation | 相同输入 → 相同输出 | 相同输入 → 相同输出 | ✅ 一致 |
| Time Semantics | replay_clock | wall_clock | ✅ 语义一致 |

### 验证套件
- **Unit Test**: 单个组件比对
- **Integration Test**: 端到端比对
- **Regression Test**: 防止回归

---

## 🔧 P0-5: Runtime Audit

### 全链路审计点

```
Raw Data
    ↓
[Audit Point 1] 数据采集验证
    ↓
Event
    ↓
[Audit Point 2] 事件协议验证
    ↓
RuntimeBus
    ↓
[Audit Point 3] 事件流转验证
    ↓
Feature
    ↓
[Audit Point 4] 特征可用性验证
    ↓
Strategy
    ↓
[Audit Point 5] 策略输入验证
    ↓
Signal
    ↓
[Audit Point 6] 信号生成验证
    ↓
Portfolio
    ↓
[Audit Point 7] 组合状态验证
    ↓
Execution
    ↓
[Audit Point 8] 执行验证
```

---

## 📦 实现优先级

### Week 1-2: 基础
- [ ] P0-1: Event Protocol 完善
- [ ] P0-2: Immutable Event

### Week 3-4: 验证
- [ ] P0-3: Availability Time 验证
- [ ] P0-5: Runtime Audit 框架

### Week 5-6: 收敛
- [ ] P0-4: Replay=Live 验证套件
- [ ] 全链路集成测试

---

## ✅ P0 验收清单

- [ ] Event Protocol 三种时间语义完整
- [ ] Immutable Event 机制正常工作
- [ ] Availability Time 验证 0 泄漏
- [ ] Replay=Live 一致性 ≥ 99%
- [ ] Runtime Audit 全链路覆盖
- [ ] 端到端回归测试通过

---

## 🎯 为什么这是第一优先级？

### 如果 Runtime 不收敛：
```
所有 feature → 建立在错误时间线上
所有 backtest → 建立在错误时间线上  
所有 strategy → 建立在错误时间线上
所有 AI → 建立在错误时间线上
→ 后面全部重做
```

### 这是量化系统最昂贵的问题

---

## 你的下一个阶段

**P0 完成后** → P1 Feature Pipeline → P2 Research → P3 Portfolio+Risk

**现在**：专注 P0，不要横向扩展！
