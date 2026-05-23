# P0-3: Runtime Enforcement Layer - 运行时强制层

> **核心原则**: Runtime 必须"默认安全"，不能靠开发者自觉
>
> **阶段**: Quant Runtime Engineering

---

## 🚨 为什么这是 P0 的核心？

### Protocol Definition ≠ Runtime Enforcement

| 方面 | 我之前做的 | 真正需要的 |
|------|-----------|-----------|
| **内容** | Protocol Definition | Runtime Enforcement |
| **性质** | "应该怎么做" | "必须这么做，否则不行" |
| **安全** | 靠开发者自觉 | 系统强制保证 |
| **风险** | 看起来正确，实际错漏 | 任何违反都被拦截 |

---

## 🛡️ Runtime Enforcement System 架构

```
Raw Event
    ↓
┌─────────────────────────────────────────────┐
│         Runtime Authority System             │
│  ┌───────────┐  ┌─────────────┐  ┌───────┐ │
│  │ClockAuth  │  │Availability │  │Order  │ │
│  │           │→ │Auth         │→ │Auth   │ │
│  └───────────┘  └─────────────┘  └───────┘ │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│         Runtime Guard System                │
│  ┌─────────────────────────────────────┐   │
│  │  AvailabilityGuard (禁止未来数据)    │   │
│  │  OrderingGuard     (禁止乱序)        │   │
│  │  MutationGuard     (禁止修改Event)  │   │
│  │  PartialCandleGuard (禁止未完成K线) │   │
│  │  DuplicateGuard    (去重)            │   │
│  │  ReplayParityGuard (Replay=Live)     │   │
│  │  ClockGuard        (统一时间)        │   │
│  │  DependencyGuard   (检查特征依赖)    │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
    ↓
Runtime Bus
    ↓
Feature Runtime / Signal Runtime
```

---

## 🧠 1. Runtime Authority System（权威系统）

### 设计原则
- **不允许手填时间语义**
- **必须由 Authority 自动生成**
- **单点控制，全局一致**

### 1.1 Clock Authority（时钟权威）

```python
class ClockAuthority:
    """
    时钟权威：唯一的时间源
    
    不允许任何组件自己调用 datetime.now() 或 time.time()
    """
    
    def now_ms(self) -> int:
        """获取当前时间（唯一入口）"""
    
    def advance_to(self, target_ms: int):
        """REPLAY 模式：时间前进"""
    
    def freeze(self):
        """冻结时间（用于测试）"""
    
    def unfreeze(self):
        """解冻时间"""
```

### 1.2 Availability Authority（可用性权威）

```python
class AvailabilityAuthority:
    """
    可用性权威：计算特征可用时间
    
    不允许任何组件直接设置 available_time_ms
    """
    
    def compute_available_time(
        self,
        event_time_ms: int,
        event_type: str,
        latency_model: LatencyModel,
    ) -> int:
        """
        自动计算可用时间
        
        输入:
        - event_time_ms: 事件发生时间
        - event_type: 事件类型
        - latency_model: 延迟模型
        
        输出:
        - available_time_ms: 自动计算的可用时间
        """
    
    def is_available(
        self,
        available_time_ms: int,
        clock_ms: int,
    ) -> bool:
        """检查是否可用"""
```

### 1.3 Ordering Authority（顺序权威）

```python
class OrderingAuthority:
    """
    顺序权威：保证事件因果顺序
    
    不允许任何组件乱序发布事件
    """
    
    def validate_order(
        self,
        current_event: ImmutableEvent,
        last_event_time_ms: int,
    ) -> tuple[bool, str]:
        """
        验证顺序
        
        返回: (是否通过, 问题描述)
        """
    
    def assign_sequence_number(
        self,
        event: ImmutableEvent,
    ) -> int:
        """分配全局序列号"""
```

---

## 🛡️ 2. Runtime Guard System（守卫系统）

### 设计原则
- **Guard 是拦截器模式**
- **任何违反都抛出 SecurityViolation**
- **默认拒绝，显式允许**

### 2.1 Base Guard 接口

```python
class GuardViolation(Exception):
    """守卫违规异常"""
    pass

class BaseGuard:
    """守卫基类"""
    
    def before_process(self, event: ImmutableEvent) -> None:
        """
        处理前检查
        
        违反时抛出 GuardViolation
        """
        pass
    
    def after_process(self, event: ImmutableEvent, result: Any) -> None:
        """处理后检查"""
        pass
```

### 2.2 7个核心 Guard

| Guard | 作用 | 检查点 |
|-------|------|--------|
| `AvailabilityGuard` | 禁止未来数据 | `available_time > processing_time` |
| `OrderingGuard` | 禁止乱序 | `event_time < last_event_time` |
| `MutationGuard` | 禁止修改 Event | `verify_integrity()` 失败 |
| `PartialCandleGuard` | 禁止未完成K线 | `candle.is_complete` |
| `DuplicateGuard` | 去重 | `event_id` 已存在 |
| `ReplayParityGuard` | 验证 Replay=Live | 行为一致性检查 |
| `ClockGuard` | 强制统一时间 | 时间源检查 |
| `DependencyGuard` | 检查特征依赖 | 特征依赖链完整性 |

---

## 🎯 3. Deterministic Replay Engine（确定性回放引擎）

### 设计原则
- **Replay 不是读取文件**
- **Replay 是 Live Runtime 的 Deterministic Simulation**
- **同构：相同代码，不同 IO 源**

### 架构对比

| 组件 | Live | Replay |
|------|------|--------|
| 数据来源 | WebSocket / API | 历史数据回放器 |
| 时钟 | `wall_clock` | `replay_clock` |
| 延迟 | 网络真实延迟 | 延迟模拟器 |
| 下单 | 真实交易所 | 模拟引擎 |
| 并发 | async | sync (deterministic) |
| **代码** | **相同** | **相同** |

### 关键实现

```python
class DeterministicReplayEngine:
    """确定性回放引擎"""
    
    def __init__(self, runtime: Runtime, event_log: EventLog):
        self.runtime = runtime
        self.event_log = event_log
        
        # 注入 Replay IO 源
        self.runtime.replace_data_source(event_log)
        self.runtime.replace_clock(ReplayClock())
        self.runtime.replace_execution(SimulatedExecution())
    
    def run(self, start_ms: int, end_ms: int) -> ReplayResult:
        """
        运行确定性回放
        
        完全相同的代码流程，只是数据源不同
        """
        result = ReplayResult()
        
        for event in self.event_log.get_events(start_ms, end_ms):
            # 1. 时间前进
            self.runtime.clock.advance_to(event.event_time_ms)
            
            # 2. 通过 Guard 系统
            self.runtime.guard_system.process(event)
            
            # 3. 正常业务流程（与 Live 相同的代码）
            self.runtime.process_event(event)
            
            # 4. 记录状态（用于验证）
            result.capture_state(self.runtime)
        
        return result
```

---

## 🔗 4. Runtime Audit（全链路审计）

### 审计点

```
Raw Data
  ↓ [Audit Point 1] 数据采集验证
Event
  ↓ [Audit Point 2] 时间权威验证
ClockAuthority
  ↓ [Audit Point 3] 可用性验证
AvailabilityAuthority
  ↓ [Audit Point 4] 顺序验证
OrderingAuthority
  ↓ [Audit Point 5] Guard 检查
Guard System
  ↓ [Audit Point 6] 总线发布
Runtime Bus
  ↓ [Audit Point 7] 特征计算
Feature Runtime
  ↓ [Audit Point 8] 信号生成
Signal Runtime
  ↓ [Audit Point 9] 组合更新
Portfolio Runtime
  ↓ [Audit Point 10] 执行
Execution Runtime
```

### Audit Trail

```python
class AuditTrail:
    """审计追踪"""
    
    def record(
        self,
        audit_point: str,
        event: ImmutableEvent,
        state_before: Dict,
        state_after: Dict,
    ) -> None:
        """记录审计点"""
    
    def verify_causality(self) -> bool:
        """验证因果关系"""
    
    def export_timeline(self) -> Timeline:
        """导出时间线"""
```

---

## ✅ 验收标准

### 1. Runtime Guard System
- [ ] 任何违反都被拦截并抛出 `GuardViolation`
- [ ] 没有"后门"可以绕过 Guard
- [ ] Guard 配置化，可启用/禁用

### 2. Runtime Authority System
- [ ] 没有组件可以绕过 Authority 直接设置时间
- [ ] 所有时间语义由 Authority 自动生成
- [ ] Authority 是单点，全局一致

### 3. Deterministic Replay
- [ ] Replay 和 Live 使用 **相同代码**
- [ ] 相同输入产生 **相同输出**
- [ ] Replay 可以确定性重现任何 Live 行为

### 4. Runtime Audit
- [ ] 全链路可追踪
- [ ] 任何违规都有审计记录
- [ ] 可以导出完整时间线用于分析

---

## 🎯 实现优先级

### Phase 1: Core Authority (Now)
- [ ] Clock Authority
- [ ] Availability Authority
- [ ] Ordering Authority

### Phase 2: Guard System (Next)
- [ ] AvailabilityGuard
- [ ] OrderingGuard
- [ ] MutationGuard
- [ ] PartialCandleGuard

### Phase 3: Deterministic Replay (Then)
- [ ] DeterministicReplayEngine
- [ ] ReplayParityGuard

### Phase 4: Audit (Finally)
- [ ] RuntimeAuditTrail
- [ ] 全链路验证套件
