# ClockAuthority 使用规范

> 确保三范式（LIVE/REPLAY/RESEARCH）时间一致性的设计原则

---

## 📋 核心原则

1. **所有业务逻辑时间必须通过 ClockAuthority 获取**
2. **禁止在业务核心逻辑中直接调用 `datetime.now()`**
3. **三范式共享同一个 ClockAuthority，确保时间一致性**

---

## ✅ 何时使用 ClockAuthority

### 业务核心逻辑（必须使用）

| 场景 | 使用方式 | 说明 |
|------|---------|------|
| Domain Kernel 处理事件 | `clock.now_ms()` | 获取当前时间用于状态更新 |
| Market State 更新 | 通过参数传入 timestamp | 由调用方提供，确保一致性 |
| 策略生成信号 | 从事件中获取时间 | 策略不应直接获取时间 |
| 事件发布 | 从事件或 ClockAuthority | 确保事件时间戳正确 |

### 示例代码

```python
# ✅ 正确：Domain Kernel 使用 ClockAuthority
class DomainKernel:
    async def handle_event(self, event: BaseEvent, features: Dict):
        # 获取当前时间（通过 ClockAuthority）
        current_time_ms = self._clock.now_ms()
        current_time = datetime.fromtimestamp(current_time_ms / 1000)
        
        # 传递给状态机
        self._state_machine.update(
            event_type=event.event_type,
            features=features,
            timestamp=current_time,
        )

# ✅ 正确：策略从事件获取时间
class SomeStrategy:
    def generate_signal(self, market_state, event, features):
        return StrategySignal(
            timestamp=event.timestamp,  # 从事件获取
            ...
        )

# ❌ 错误：直接使用 datetime.now()
class SomeComponent:
    def process(self):
        now = datetime.now()  # 错误！
```

---

## ❌ 何时可以使用 datetime.now()

### 基础设施层（允许使用）

| 场景 | 示例 | 说明 |
|------|------|------|
| 日志记录 | logger.info(...) | 日志时间无关业务逻辑 |
| 监控指标 | metrics.record(...) | 监控不参与业务决策 |
| 元数据存储 | created_at 字段 | 元数据可以使用实际时间 |
| WebSocket 消息 | gateway.send(...) | 通信层使用实际时间 |
| 健康检查 | health_check() | 运维相关，不影响业务 |

### 示例代码

```python
# ✅ 正确：基础设施层可以使用 datetime.now()
class LoggingHandler:
    def emit(self, message):
        log_entry = {
            "message": message,
            "timestamp": datetime.now().isoformat(),  # OK
        }

class MetricsCollector:
    def record(self, metric):
        self.storage.append({
            "metric": metric,
            "recorded_at": datetime.now(),  # OK
        })

# ❌ 错误：业务逻辑不能使用 datetime.now()
class BusinessLogic:
    def process_trade(self, trade):
        trade.time = datetime.now()  # 错误！应该从 ClockAuthority 获取
```

---

## 🏗️ 架构层级划分

```
┌─────────────────────────────────────────────────────────────┐
│                   业务核心层（必须使用 ClockAuthority）      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Domain      │  │ Market State│  │ V2 Strategies    │  │
│  │ Kernel      │  │ Machine     │  │                 │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                │                  │            │
│         └────────────────┼──────────────────┘            │
│                          │                               │
│                  ClockAuthority                         │
│                          │                               │
└──────────────────────────┼───────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────┐
│                   基础设施层（可以使用 datetime.now()）    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Logging     │  │ Monitoring  │  │ WebSocket       │  │
│  │             │  │             │  │ Gateway         │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 📝 检查清单

在提交代码前，请检查：

- [ ] **业务逻辑是否使用了 ClockAuthority？**
  - Domain Kernel
  - Market State Machine
  - 策略信号生成
  - 事件处理器

- [ ] **是否在禁止的地方使用了 datetime.now()？**
  - 检查 `datetime.now()`, `datetime.utcnow()`, `.now()`, `.utcnow()`

- [ ] **是否有合理的 fallback？**
  - 策略从事件获取时间
  - 事件应包含时间戳

---

## 🔍 代码审查重点

### 1. grep 检查

```bash
# 检查是否在业务逻辑中使用了 datetime.now()
grep -r "datetime\.now\(\)" backend/domain/
grep -r "datetime\.utcnow\(\)" backend/engines/compute/strategy/
grep -r "datetime\.now\(\)" backend/runtime/kernel/unified/
```

### 2. 导入检查

```bash
# 业务核心应该导入 ClockAuthority
grep -r "from.*ClockAuthority" backend/domain/
grep -r "from.*ClockAuthority" backend/engines/compute/strategy/
grep -r "from.*ClockAuthority" backend/runtime/kernel/
```

---

## 🎯 总结

### ✅ 应该使用 ClockAuthority 的地方

1. Domain Kernel - 所有业务逻辑的入口
2. Market State Machine - 状态更新的时间
3. 策略信号 - 从事件获取时间
4. 事件处理 - 确保时间戳正确

### ❌ 不应该使用 ClockAuthority 的地方

1. 日志和监控
2. WebSocket 通信
3. 元数据和配置
4. 健康检查和运维

### 🔑 核心原则

> **业务逻辑的时间必须来自 ClockAuthority**
> 
> **三范式（LIVE/REPLAY/RESEARCH）共享同一个时间源**
> 
> **确保 100% 可复现性**

---

## 📚 相关文档

- [三范式统一运行时架构](THREE_PARADIGM_UNIFIED_RUNTIME.md)
- [ClockAuthority 实现](backend/runtime/kernel/authority/clock_authority.py)
