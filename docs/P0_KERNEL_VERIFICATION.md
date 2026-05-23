# P0: Deterministic Kernel Verification (决定性内核验证)

> **核心理念：Architecture Correctness ≠ Execution Correctness**
> 
> **唯一验证标准：Replay == Live (State Trajectory Level)**

---

## ⚠️ **当前阶段关键判断**

| 问题 | 状态 | 说明 |
|------|------|------|
| Architecture Completeness | ✅ 看起来完整 | Authority, Guard, Replay, Validator 都有了 |
| Single Entry Point | ❌ 缺失 | 可能有 bypass 路径 |
| State Trajectory Verification | ❌ 缺失 | 只是结构一致，不是行为一致 |
| Failure Mode Testing | ❌ 缺失 | 没有主动测试失效模式 |

---

## 🚀 **P0.1: Kernel Single-Entry Refactor (最关键)**

### 设计原则：**Forced Single Path**

```
                   ┌─────────────────────────┐
                   │  NO BYPASS GUARANTEE    │
                   └─────────────┬───────────┘
                                 │
         ┌───────────────────────▼───────────────────────┐
         │        RUNTIME KERNEL - SINGLE ENTRY          │
         │                                               │
         │  ┌─────────────────────────────────────────┐ │
         │  │ runtime.handle(raw_event) - ONLY ENTRY │ │
         │  └───────────────────┬─────────────────────┘ │
         │                      │                       │
         │  ┌───────────────────▼─────────────────────┐ │
         │  │   1. Authority Layer (MANDATORY)        │ │
         │  │      - Clock                           │ │
         │  │      - Availability                    │ │
         │  │      - Ordering                       │ │
         │  └───────────────────┬─────────────────────┘ │
         │                      │                       │
         │  ┌───────────────────▼─────────────────────┐ │
         │  │   2. Guard Chain (MANDATORY)           │ │
         │  │      - Mutation Guard                  │ │
         │  │      - Availability Guard              │ │
         │  │      - Ordering Guard                  │ │
         │  │      - Partial Candle Guard            │ │
         │  │      - Duplicate Guard                 │ │
         │  └───────────────────┬─────────────────────┘ │
         │                      │                       │
         │  ┌───────────────────▼─────────────────────┐ │
         │  │   3. State Transition Layer           │ │
         │  │      - Capture Before                  │ │
         │  │      - Process Business Logic          │ │
         │  │      - Capture After                   │ │
         │  └───────────────────┬─────────────────────┘ │
         │                      │                       │
         │  ┌───────────────────▼─────────────────────┐ │
         │  │   4. Emit Layer                        │ │
         │  │      - Output Events                   │ │
         │  │      - Signals                         │ │
         │  │      - Orders                          │ │
         │  └─────────────────────────────────────────┘ │
         │                                               │
         │  ⚠️  NO OTHER PATH TO ENTER SYSTEM          │
         └───────────────────────────────────────────────┘
```

### 禁止事项（必须代码级强制）

| 禁止 | 说明 | 强制执行机制 |
|------|------|-------------|
| ❌ `ImmutableEvent(...)` 直接 new | 只能通过 `runtime.handle()` 创建 | 使用工厂模式，构造函数私有 |
| ❌ Feature 自己设置 timestamp | 所有时间来自 Clock Authority | Feature 层没有时间 API |
| ❌ Bypass Guard Chain | Guard 是 Kernel 内部组件，外部无法跳过 | Guard 只在 Entry Point 后调用 |
| ❌ 绕过 Clock Authority | 所有时间必须来自 `clock.now_ms()` | 没有其他时间 API |

---

## 🎯 **P0.2: Trace-Level Replay Diff (真正的验证)**

### 不是 "结构一致"，而是 "State Trajectory 一致"

| 验证层级 | 旧做法 | 新做法 |
|---------|--------|--------|
| ❌ Structure Match | event 顺序一样 | 不够 |
| ❌ Output Match | signal 一样 | 不够 |
| ❌ State Diff | portfolio 一样 | 不够 |
| ❌ Side Effect Match | execution 一样 | 不够 |
| ✅ **State Trajectory** | **每一步 state hash 完全一致** | **这才是目标** |

### State Trajectory 验证

```
Step 0:
  Live State:    { hash: "abc123", portfolio: { ... } }
  Replay State:  { hash: "abc123", portfolio: { ... } }
  ✅ MATCH

Step 1:
  Live State:    { hash: "def456", portfolio: { ... } }
  Replay State:  { hash: "def456", portfolio: { ... } }
  ✅ MATCH

Step 2:
  Live State:    { hash: "ghi789", portfolio: { ... } }
  Replay State:  { hash: "xxx000", portfolio: { ... } }
  ❌ MISMATCH -> FATAL ERROR

→ System is NOT deterministic!
```

---

## 💥 **P0.3: Failure Mode Injection (工业级稳定性)**

### 主动测试所有失效模式

| 失效模式 | 注入方法 | 验证目标 |
|---------|---------|---------|
| Event Delay | `available_time = event_time + random(100, 1000)ms` | Availability Guard 拦截 |
| Out-of-Order | `event_time = last_event_time - random(100, 500)ms` | Ordering Guard 拦截 |
| Duplicate | `event_id = previous_event_id` | Duplicate Guard 拦截 |
| Missing Event | 跳跃式播放 log | State Trajectory 一致性验证 |
| Partial Candle | `is_complete = False` | Partial Candle Guard 拦截 |
| Clock Drift | `clock.advance(1000ms)` then `clock.advance(-500ms)` | Clock Authority 禁止时间回退 |
| Timestamp Tampering | 直接修改 event 字段 | Mutation Guard 验证 hash 失败 |

---

## 🎯 **实现路线（优先级严格）**

### Phase 1: Single Entry Point (P0.1)
- [ ] 重构 `runtime/kernel.py` - 单一入口
- [ ] 强制 `ImmutableEvent` 只能通过 Kernel 创建
- [ ] 移除所有 bypass 路径
- [ ] 提供 `RuntimeKernel.handle(raw_event)` - 唯一入口

### Phase 2: State Trajectory Diff (P0.2)
- [ ] 实现 `StateTrajectory` 类
- [ ] 每一步 state 都有 cryptographic hash
- [ ] 实现逐 step 比对
- [ ] 生成详细 diff 报告

### Phase 3: Failure Injection Harness (P0.3)
- [ ] 实现 `FailureInjector` 类
- [ ] 实现所有 7 种失效模式
- [ ] 自动化测试套件
- [ ] 验证 Guard 能正确拦截

---

## ✅ **Kernel 验收标准（最终标准）**

### Gold Standard: Replay == Live (State Trajectory Level)

```
输入: 同一个 event log
运行: Live Record → 记录 trajectory
运行: Replay → 生成 trajectory
比对: trajectory hash 逐 step 比对

结果:
  ✅ 100% match → Kernel is deterministic
  ❌ 任何 mismatch → Kernel 有 bug
```

### 额外验证

| 验证项 | 要求 |
|--------|------|
| 没有 bypass 路径 | 静态代码分析 |
| 所有失效模式被拦截 | 100% 覆盖率 |
| 1000 次回放一致性 | 0 次 diff |
| 1000 次随机失效注入 | 0 次 system crash |

---

## 📌 **当前阶段总结**

**你现在不是在做 Trading System，也不是在做 Event System。**

**你在做：「可验证的确定性交易内核（Deterministic Trading Kernel）」**

**唯一验收标准：State Trajectory Level 的 Replay == Live**

**不是设计图，是实际运行结果。**
