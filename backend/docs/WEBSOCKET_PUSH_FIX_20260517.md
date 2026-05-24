# WebSocket 实时推送架构修复

**日期**: 2026-05-17  
**修复者**: AI Assistant

## 问题描述

后端无法主动推送数据到前端，WebSocket 实时数据推送链路中断。

## 架构分析

### 数据推送链路

```
┌─────────────┐    Kafka     ┌─────────────────┐   Redis Pub/Sub   ┌────────────┐   WebSocket   ┌────────┐
│ Ingestion   │──────────────│ Projection      │──────────────────│ WS Gateway │──────────────│ Frontend│
│ Runtime     │              │ Runtime         │                   │            │               │        │
└─────────────┘              └─────────────────┘                   └────────────┘               └────────┘
     ↑                              ↑                                    ↑
  市场数据                       投影计算                            实时推送
```

## 问题根因分析

### 问题 1: Projection Runtime 缺少 Redis Pub/Sub 发布

- **问题**: Projection Runtime 虽然消费了 Kafka 事件，但没有发布到 Redis Pub/Sub
- **影响**: WS Gateway 无法接收到新数据进行推送
- **代码位置**: [runtime/projection_runtime/runtime.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/runtime/projection_runtime/runtime.py)

### 问题 2: 缺少 event_type 到 channel 的映射

- **问题**: Kafka 事件只有 `event_type` 字段，缺少 `channel` 字段
- **影响**: 无法确定将事件发布到哪个 Redis 频道
- **影响的事件类型**:
  - `price_update` → 价格数据
  - `raw_data` → 原始数据
  - `news` → 新闻
  - `signal` → 信号
  - `event` → 事件
  - `market` → 市场
  - `order` → 订单
  - `position` → 持仓
  - `risk` → 风险
  - `decision` → 决策

### 问题 3: API Server 未启动 Redis 订阅者

- **问题**: `api_server.py` 中调用了 `get_ws_gateway()` 但没有启动 `run_redis_subscriber()` 任务
- **影响**: WS Gateway 订阅不了 Redis Pub/Sub 消息

## 修复方案

### 修复 1: 添加 EVENT_TYPE_TO_CHANNEL 映射

在 [runtime/projection_runtime/runtime.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/runtime/projection_runtime/runtime.py#L51-L63) 中添加：

```python
EVENT_TYPE_TO_CHANNEL = {
    "price_update": "channel:prices",
    "raw_data": "channel:dashboard",
    "news": "channel:dashboard",
    "signal": "channel:signal",
    "event": "channel:timeline",
    "market": "channel:dashboard",
    "order": "channel:order",
    "position": "channel:position",
    "risk": "channel:risk",
    "decision": "channel:decision",
}
```

### 修复 2: 添加 Redis 发布逻辑

在 `_dispatch_event` 方法中添加：

```python
if self._redis:
    try:
        channel = event.get("channel") or self.EVENT_TYPE_TO_CHANNEL.get(event_type, "channel:dashboard")
        projection_data = event.get("data", {})
        
        payload = {
            "type": "data_update",
            "event_type": event_type,
            "channel": channel,
            "data": projection_data,
            "timestamp": event.get("timestamp", ""),
        }
        
        await self._redis.publish(channel, json.dumps(payload))
        self.metrics.increment("events_published")
        self.logger.info(f"[REDIS-PUB] event={event_type} channel={channel}")
    except Exception as e:
        self.logger.warning(f"Failed to publish to Redis: {e}")
```

### 修复 3: 在 API Server 启动 Redis 订阅者

在 [api_server.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/api_server.py#L42-L45) 中添加：

```python
ws_gateway = await get_ws_gateway()
asyncio.create_task(ws_gateway.run_redis_subscriber())
logger.info("WebSocket Gateway Redis subscriber started")
```

### 修复 4: 添加监控日志

在 WS Gateway 中添加消息处理计数：

```python
msg_count = 0
async for message in pubsub.listen():
    # ... 处理消息
    await self.broadcast(channel, data)
    msg_count += 1
    if msg_count % 100 == 0:
        logger.info(f"[WS-GATEWAY] Processed {msg_count} messages")
```

## 验证结果

### Projection Runtime 验证

- ✅ Redis 连接成功: `Redis connected for pub/sub`
- ✅ 事件发布正常: `[REDIS-PUB] event=price_update channel=channel:prices`
- ✅ 发布频率: 每分钟约 200 条消息

### WS Gateway 验证

- ✅ Redis 订阅成功: `Subscribed to Redis channels: ['channel:prices', ...]`
- ✅ 消息处理: `[WS-GATEWAY] Processed 200 messages`
- ✅ 前端订阅: `conn_xxx subscribed to: ['channel:prices', 'channel:position']`

### 前端验证

- ✅ WebSocket 连接成功
- ✅ 频道订阅成功
- ✅ 实时数据推送中

## 频道映射表

| 事件类型 (event_type) | Redis 频道 | 用途 |
|----------------------|------------|------|
| price_update | channel:prices | 价格更新 |
| raw_data | channel:dashboard | 原始数据 |
| news | channel:dashboard | 新闻 |
| signal | channel:signal | 交易信号 |
| event | channel:timeline | 事件时间线 |
| market | channel:dashboard | 市场数据 |
| order | channel:order | 订单更新 |
| position | channel:position | 持仓更新 |
| risk | channel:risk | 风险预警 |
| decision | channel:decision | 决策更新 |

## 相关文件修改

- [backend/runtime/projection_runtime/runtime.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/runtime/projection_runtime/runtime.py)
- [backend/infrastructure/websocket/gateway.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/websocket/gateway.py)
- [backend/api_server.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/api_server.py)

## 后续优化建议

1. 添加 Redis Pub/Sub 的重连机制
2. 实现消息去重，避免重复推送
3. 添加推送失败的重试机制
4. 增加更详细的推送监控指标
5. 考虑添加消息积压告警
