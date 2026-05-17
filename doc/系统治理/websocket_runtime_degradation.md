# WebSocket Runtime 推送降级机制文档

> 审计日期: 2026-05-17
> 文档版本: 1.0

---

## 一、概述

WebSocket Runtime 是后端推送到前端的核心组件，负责：
- 管理所有 WebSocket 连接
- 推送实时状态更新
- 降级控制与熔断保护
- 订阅管理与推送节流

---

## 二、架构设计

### 2.1 数据流架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         数据源层                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Binance WS  │  OKX WS  │  Bybit WS  │  REST APIs  │  News/Social   │
└──────┬───────────┬───────────┬──────────────┬─────────────┘
       │           │           │              │
       ▼           ▼           ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Runtime Governor                                  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │ PriorityQueue   │  │ DegradationCtrl │  │ CircuitBreaker  │      │
│  │ (P0-P4)         │  │ (6种模式)        │  │ (7个熔断器)      │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              SubscriptionManager                              │    │
│  │         (订阅管理 + 推送节流 + 防重复)                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    WebSocket Runtime                                 │
├─────────────────────────────────────────────────────────────────────┤
│  - 连接管理 (最大 1000 连接)                                         │
│  - 推送节流 (根据运行模式动态调整)                                    │
│  - 心跳检测 (30s)                                                    │
│  - 超时清理 (300s)                                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         前端                                         │
├─────────────────────────────────────────────────────────────────────┤
│  WebSocket 连接  ──────►  HTTP 轮询降级                              │
│  (主模式)                   (WS 断开时启用)                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 文件路径 | 职责 |
|-----|---------|-----|
| RuntimeGovernor | [governor.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/runtime_governor/governor.py) | 总控制器，管理所有运行时组件 |
| WebSocketRuntime | [websocket_runtime.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/runtime_governor/websocket_runtime.py) | WebSocket 连接管理与推送 |
| DegradationController | [degradation.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/runtime_governor/degradation.py) | 运行模式控制与降级 |
| CircuitBreakerManager | [circuit_breaker_manager.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/runtime_governor/circuit_breaker_manager.py) | 熔断器管理 |
| SubscriptionManager | [subscription_manager.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/runtime_governor/subscription_manager.py) | 订阅管理与防重复 |
| WSGateway | [gateway.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/websocket/gateway.py) | WebSocket 网关 |
| wsService | [wsService.ts](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/frontend/src/services/websocket/wsService.ts) | 前端 WebSocket 服务 |

---

## 三、已实现的降级机制

### 3.1 后端推送降级

#### 3.1.1 推送节流 (Throttling)

在 `WebSocketRuntime.broadcast()` 方法中实现三层过滤：

```python
async def broadcast(self, topic: str, message: Dict[str, Any], priority: EventPriority) -> int:
    # 第一层：订阅管理检查
    if not self._governor.subscriptions.should_push(topic):
        return 0  # 不推送
    
    # 第二层：优先级降级检查
    if self._governor.degradation.should_drop_event(priority):
        return 0  # 丢弃事件
    
    # 第三层：推送间隔节流
    if not self._should_send_topic(topic):
        return 0  # 间隔不够，不推送
    
    # 执行推送...
```

#### 3.1.2 运行模式自动切换

`DegradationController` 根据 CPU 和队列负载自动切换 6 种运行模式：

| 模式 | 触发条件 | 行为 |
|-----|---------|-----|
| NORMAL | CPU < 70%, 队列 < 1000 | 全功能运行 |
| DEGRADED | CPU > 70% 或 队列 > 1000 | 降低推送频率 |
| SAFE_MODE | CPU > 80% 或 队列 > 5000 | 关闭 AI/Replay |
| CRITICAL | CPU > 90% 或 队列 > 10000 | 只保留交易核心 |
| READ_ONLY | 手动触发 | 禁止下单 |
| RECOVERY | 手动触发 | 重建状态 |

不同模式下的推送间隔配置：

```python
DEGRADATION_PROFILES = {
    RuntimeMode.NORMAL: DegradationConfig(
        tick_interval_ms=100,      # 10Hz
        price_interval_ms=50,      # 20Hz
        signal_interval_ms=500,    # 2Hz
        ...
    ),
    RuntimeMode.DEGRADED: DegradationConfig(
        tick_interval_ms=500,      # 2Hz (降低 5x)
        price_interval_ms=200,     # 5Hz (降低 4x)
        signal_interval_ms=2000,   # 0.5Hz (降低 4x)
        ...
    ),
    RuntimeMode.CRITICAL: DegradationConfig(
        tick_interval_ms=2000,     # 0.5Hz
        price_interval_ms=1000,    # 1Hz
        signal_interval_ms=10000,  # 0.1Hz
        ...
    ),
}
```

#### 3.1.3 事件优先级队列

事件按优先级 P0-P4 排序处理：

| 优先级 | 名称 | 事件类型 |
|-------|-----|---------|
| P0 | 紧急 | 订单执行、风控警报 |
| P1 | 高 | 价格更新、持仓变化 |
| P2 | 正常 | 信号更新、因子计算 |
| P3 | 低 | 新闻推送、社交数据 |
| P4 | 后台 | 日志、统计 |

在 CRITICAL 模式下，P3-P4 事件会被丢弃。

#### 3.1.4 熔断器保护

预定义 7 个熔断器：

| 熔断器名称 | 保护目标 | 触发条件 |
|-----------|---------|---------|
| binance_api | Binance API | 5 次失败 / 60s |
| okx_api | OKX API | 5 次失败 / 60s |
| bybit_api | Bybit API | 5 次失败 / 60s |
| llm_service | LLM 服务 | 3 次失败 / 30s |
| database | 数据库 | 5 次失败 / 60s |
| redis | Redis | 5 次失败 / 60s |
| websocket | WebSocket | 10 次失败 / 60s |

熔断器状态：
- CLOSED: 正常运行
- OPEN: 熔断中，拒绝请求
- HALF_OPEN: 半开，尝试恢复

#### 3.1.5 订阅管理

- 共享订阅：多个客户端订阅同一频道时共享推送
- 防重复订阅：同一客户端重复订阅会被合并
- 推送计数：记录每个频道的推送次数
- 自动清理：清理不活跃的订阅

### 3.2 前端降级机制

#### 3.2.1 WebSocket 重连

```typescript
// wsService.ts
private attemptReconnect(): void {
  if (this.reconnectAttempts >= this.maxReconnectAttempts) {  // 最大 5 次
    console.error('[WS] Max reconnect attempts reached')
    return
  }
  
  this.reconnectAttempts++
  const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)  // 指数退避
  // 1s → 2s → 4s → 8s → 16s
  setTimeout(() => this.connect().catch(console.error), delay)
}
```

#### 3.2.2 HTTP 轮询降级

当 WebSocket 连接断开时，前端自动启用 HTTP 轮询：

```typescript
// useDataLoader.ts
const PRICE_POLL_INTERVAL = 5000  // 5秒轮询

// 价格轮询（WebSocket 失败时的降级）
priceIntervalId = window.setInterval(() => {
  if (mounted && !wsConnectedRef.current) {  // WS 断开时启用
    loadPricesOnly()
  }
}, PRICE_POLL_INTERVAL)
```

---

## 四、未实现的功能

### 4.1 SSE (Server-Sent Events) 降级

**状态**: ❌ 未实现

**说明**: SSE 作为 WebSocket 和 HTTP 轮询之间的中间方案，具有以下优势：
- 比 HTTP 轮询实时性更高
- 比 WebSocket 实现更简单
- 支持断线重连
- 单向推送，适合服务端推送场景

**建议**: 可作为 WebSocket 失败后的第二降级方案：

```
WebSocket (主) → SSE (降级) → HTTP 轮询 (最终降级)
```

### 4.2 前端感知后端运行模式

**状态**: ❌ 未实现

**说明**: 前端不知道后端当前是什么运行模式 (NORMAL/DEGRADED/CRITICAL)。

**建议**: 
1. 在 WebSocket 连接时返回当前运行模式
2. 当运行模式变化时推送通知
3. 前端根据运行模式调整 UI 展示

**后端已有接口**:
- `GET /api/v1/runtime/mode` - 获取当前运行模式
- `WebSocketRuntime.notify_mode_change()` - 模式变化通知（已实现但前端未处理）

### 4.3 前端订阅更多频道

**状态**: ⚠️ 部分实现

**说明**: 后端支持 12 个 WebSocket 频道，但前端只订阅了 2 个。

| 频道 | 后端支持 | 前端订阅 | 数据获取方式 |
|-----|---------|---------|------------|
| channel:prices | ✅ | ✅ | WebSocket |
| channel:position | ✅ | ✅ | WebSocket |
| channel:risk | ✅ | ❌ | HTTP 轮询 (60s) |
| channel:signal | ✅ | ❌ | HTTP 轮询 (60s) |
| channel:factor | ✅ | ❌ | HTTP 轮询 (60s) |
| channel:decision | ✅ | ❌ | HTTP 轮询 (60s) |
| channel:news | ✅ | ❌ | HTTP 轮询 (5min) |
| channel:timeline | ✅ | ❌ | HTTP 轮询 |
| channel:order | ✅ | ❌ | HTTP 轮询 |
| channel:dashboard | ✅ | ❌ | HTTP 轮询 |

**建议**: 扩展前端 WebSocket 订阅，减少 HTTP 轮询。

---

## 五、API 端点

### 5.1 Runtime 管理 API

| 端点 | 方法 | 说明 |
|-----|-----|-----|
| `/api/v1/runtime/stats` | GET | 获取完整运行时统计 |
| `/api/v1/runtime/mode` | GET | 获取当前运行模式 |
| `/api/v1/runtime/mode` | POST | 切换运行模式 |
| `/api/v1/runtime/recovery` | POST | 强制恢复 |
| `/api/v1/runtime/circuit-breakers` | GET | 获取所有熔断器状态 |
| `/api/v1/runtime/circuit-breakers/{name}/reset` | POST | 重置熔断器 |
| `/api/v1/runtime/subscriptions` | GET | 获取订阅统计 |
| `/api/v1/runtime/queue` | GET | 获取事件队列统计 |

### 5.2 WebSocket 端点

| 端点 | 说明 |
|-----|-----|
| `/ws` | 主 WebSocket 端点，支持动态订阅 |
| `/ws/{channel}` | 单频道 WebSocket 端点 |

### 5.3 WebSocket 消息类型

**客户端 → 服务端**:

```json
// 订阅频道
{"type": "subscribe", "channels": ["channel:dashboard", "channel:risk"]}

// 取消订阅
{"type": "unsubscribe", "channels": ["channel:dashboard"]}

// 心跳
{"type": "ping"}

// 获取状态
{"type": "get_state"}
```

**服务端 → 客户端**:

```json
// 欢迎消息
{
  "type": "welcome",
  "connection_id": "ws_123456",
  "available_channels": ["channel:dashboard", ...],
  "runtime_mode": "normal",
  "timestamp": "2026-05-17T10:00:00Z"
}

// 订阅确认
{"type": "subscribed", "channels": ["channel:dashboard"]}

// 数据推送
{
  "channel": "channel:dashboard",
  "data": {...},
  "timestamp": "2026-05-17T10:00:01Z"
}

// 心跳响应
{"type": "pong", "timestamp": 1715942400.0}

// 运行模式变化通知
{
  "type": "mode_change",
  "old_mode": "normal",
  "new_mode": "degraded",
  "timestamp": "2026-05-17T10:00:00Z"
}
```

---

## 六、监控指标

### 6.1 Runtime Stats 响应示例

```json
{
  "state": "running",
  "governor_stats": {
    "events_processed": 1234567,
    "events_dropped": 1234,
    "errors": 56,
    "uptime_seconds": 86400
  },
  "event_rate": 847.5,
  "queue_stats": {
    "size": 234,
    "total_pushed": 1234567,
    "total_popped": 1234333,
    "by_priority": {
      "P0": 12,
      "P1": 45,
      "P2": 128,
      "P3": 67,
      "P4": 23
    }
  },
  "degradation_stats": {
    "current_mode": "normal",
    "mode_history": [...],
    "cpu_percent": 45.2,
    "queue_lag": 234
  },
  "circuit_breaker_stats": {
    "binance_api": {"state": "closed", "failure_count": 0},
    "okx_api": {"state": "closed", "failure_count": 0},
    "llm_service": {"state": "half_open", "failure_count": 2}
  },
  "subscription_stats": {
    "total_subscriptions": 156,
    "by_channel": {
      "channel:dashboard": 64,
      "channel:risk": 32,
      "channel:position": 60
    }
  }
}
```

### 6.2 关键监控指标

| 指标 | 说明 | 告警阈值 |
|-----|-----|---------|
| `event_rate` | 事件处理速率 | > 10000/s |
| `events_dropped` | 丢弃事件数 | > 1000 |
| `queue_stats.size` | 队列深度 | > 5000 |
| `degradation_stats.current_mode` | 运行模式 | CRITICAL |
| `circuit_breaker_stats.*.state` | 熔断器状态 | OPEN |
| `subscription_stats.total_subscriptions` | 订阅数 | > 10000 |

---

## 七、前端卡片展示分析

### 7.1 Runtime 相关卡片缺失

以下后端已实现的功能在前端没有对应的展示卡片：

| 功能 | 后端实现 | 前端卡片 | 优先级 |
|-----|---------|---------|-------|
| 运行模式 | ✅ DegradationController | ❌ 无 | P0 |
| 事件队列 | ✅ PriorityEventQueue | ❌ 无 | P1 |
| 熔断器状态 | ✅ CircuitBreakerManager | ⚠️ 静态数据 | P0 |
| 订阅管理 | ✅ SubscriptionManager | ❌ 无 | P1 |
| Runtime 统计 | ✅ /api/v1/runtime/stats | ❌ 无 | P1 |
| WebSocket 详情 | ✅ wsService | ⚠️ 仅连接状态 | P2 |

### 7.2 建议新增卡片

**SystemMonitorPage 新增卡片**:

```
┌─────────────────────────────────┐
│ ⚡ Runtime Mode: NORMAL         │
├─────────────────────────────────┤
│ CPU: 45%  │ 队列: 234          │
│ 事件率: 847/s │ 丢弃: 1234      │
│                                 │
│ [切换模式] [强制恢复]           │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 📦 Event Queue                 │
├─────────────────────────────────┤
│ P0 (紧急): 12                   │
│ P1 (高): 45                     │
│ P2 (正常): 128                  │
│ P3 (低): 67                     │
│ P4 (后台): 23                   │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 🔌 Circuit Breakers            │
├─────────────────────────────────┤
│ Binance API: ✅ CLOSED          │
│ OKX API: ✅ CLOSED              │
│ LLM Service: ⚠️ HALF_OPEN      │
│ Database: ✅ CLOSED             │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 📡 Subscriptions               │
├─────────────────────────────────┤
│ dashboard: 64 订阅              │
│ position: 60 订阅               │
│ risk: 32 订阅                   │
│ 共享订阅: 45                    │
└─────────────────────────────────┘
```

---

## 八、改进建议

### 8.1 短期改进 (P0)

1. **修复 SystemMonitorPage 熔断器卡片**
   - 当前使用静态模拟数据
   - 改为调用 `/api/v1/runtime/circuit-breakers` API

2. **新增运行模式卡片**
   - 展示当前运行模式
   - 提供模式切换按钮
   - 显示 CPU/队列负载

3. **前端处理运行模式变化通知**
   - 监听 `type: "mode_change"` 消息
   - 更新 UI 显示当前模式
   - 模式为 CRITICAL 时显示警告

### 8.2 中期改进 (P1)

1. **扩展前端 WebSocket 订阅**
   ```typescript
   wsService.subscribe([
     'channel:prices',
     'channel:position',
     'channel:risk',      // 新增
     'channel:signal',    // 新增
     'channel:factor',    // 新增
     'channel:decision',  // 新增
     'channel:news',      // 新增
   ])
   ```

2. **新增事件队列卡片**
   - 展示各优先级事件数量
   - 实时更新

3. **新增订阅管理卡片**
   - 展示各频道订阅数
   - 共享订阅统计

### 8.3 长期改进 (P2)

1. **实现 SSE 降级**
   ```
   WebSocket (主) → SSE (降级) → HTTP 轮询 (最终降级)
   ```

2. **前端自适应推送频率**
   - 根据运行模式调整 UI 刷新频率
   - CRITICAL 模式下减少非必要更新

3. **Runtime 监控大盘**
   - 独立页面展示所有 Runtime 指标
   - 历史趋势图表
   - 告警配置

---

## 九、总结

### 已实现 ✅

- WebSocket 连接管理 (最大 1000 连接)
- 推送节流 (根据运行模式动态调整)
- 事件优先级队列 (P0-P4)
- 运行模式自动切换 (6 种模式)
- 熔断器保护 (7 个预定义熔断器)
- 订阅管理 (共享订阅、防重复)
- 前端 WebSocket 重连 (指数退避)
- 前端 HTTP 轮询降级

### 未实现 ❌

- SSE 降级
- 前端感知后端运行模式
- 前端订阅更多频道 (当前只订阅 2 个)
- Runtime 相关前端展示卡片

### 核心结论

WebSocket Runtime **会自动降级**，降级路径为：

```
高负载 → 降低推送频率 → 丢弃低优先级事件 → 切换运行模式
```

前端降级路径为：

```
WebSocket 断开 → 重连 (5次) → HTTP 轮询
```

**不会降级到 SSE**，SSE 方案未实现。
