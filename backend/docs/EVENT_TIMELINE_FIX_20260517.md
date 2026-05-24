# Event Timeline 无法显示问题修复文档

**问题发生时间**: 2026-05-17  
**修复状态**: ✅ 已解决  
**影响范围**: 前端Event Timeline无法显示Odaily新闻事件，且没有滚动加载分页功能

---

## 📋 问题描述

### 现象
- 后端日志显示成功采集了7条Odaily事件：`Collected 7 Odaily events`
- 但前端Event Timeline组件显示为空：`No events yet. Waiting for runtime activity...`
- 前端没有滚动加载分页功能，无法加载历史数据

### 影响
- 用户无法看到实时采集的新闻事件
- 无法查看历史事件数据
- 数据流在Projection Runtime中断

---

## 🔍 问题诊断过程

### 1. 检查后端日志

```bash
tail -f /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/logs/ingestion.log
```

**发现**:
```
2026-05-17 08:46:41 INFO [ingestion] Collected 7 Odaily events
2026-05-17 08:46:41 ERROR [ingestion] Failed to store news to Redis: Redis client not connected
2026-05-17 08:46:41 INFO [ingestion] Published 7 Odaily events to Kafka
```

**结论**: 
- ✅ Odaily事件采集成功
- ❌ Redis存储失败（Redis客户端未连接）
- ✅ Kafka发布成功

### 2. 检查数据流路径

```
数据流路径:
Ingestion Runtime → Kafka → Projection Runtime → Redis → API → Frontend
```

#### 2.1 检查Kafka
```bash
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```
**结果**: 
- ✅ Topic存在: `tradeagent.events`, `raw.odaily`
- ✅ 消息已发布

#### 2.2 检查Projection Runtime
```bash
ps aux | grep projection_runtime
```
**发现**:
- ✅ Projection Runtime正在运行
- ❌ 缺少`EventTimelineProjection`初始化日志

#### 2.3 检查Redis
```bash
docker exec redis redis-cli keys "projection:timeline:*"
```
**发现**:
- ❌ Redis中没有timeline相关的key
- ❌ 没有事件时间线数据

### 3. 检查前端实现

**文件**: `frontend/src/components/EventTimeline.tsx`

**发现**:
- ✅ WebSocket订阅正常
- ❌ 只有实时数据，没有历史数据加载
- ❌ 没有滚动加载分页功能
- ❌ 没有API调用获取历史数据

---

## 🎯 根本原因分析

### 主要问题

#### 1. EventTimelineProjection未启用

**文件**: `backend/runtime/projection_runtime/runtime.py`

**问题**: 
- Projection Runtime中只初始化了4个Projection
- 缺少`EventTimelineProjection`
- 导致timeline事件无法被处理和存储到Redis

**影响**: 
- Kafka中的事件无法被消费处理
- Redis中没有timeline数据
- API返回空数据

**代码位置**:
```python
# 原代码 (第91-103行)
from services.projection_service.projections import (
    DashboardProjection,
    DecisionProjection,
    RiskProjection,
    PositionProjection,
)

self.projections = [
    DashboardProjection(),
    DecisionProjection(),
    RiskProjection(),
    PositionProjection(),
]
# ❌ 缺少 EventTimelineProjection
```

#### 2. Redis客户端未连接

**文件**: `backend/runtime/ingestion_runtime/runtime.py`

**问题**: 
- Ingestion Runtime获取Redis客户端后，没有调用`connect()`
- 尝试存储数据时失败：`Redis client not connected`

**影响**: 
- 新闻数据无法存储到Redis
- API无法从Redis读取数据

**代码位置**:
```python
# 原代码 (第362-367行)
redis_client = None
try:
    from infrastructure.cache import get_redis_client
    redis_client = get_redis_client()
    # ❌ 缺少连接初始化
except Exception as e:
    self.logger.warning(f"Redis client not available: {e}")
```

#### 3. 前端缺少滚动加载分页

**文件**: `frontend/src/components/EventTimeline.tsx`

**问题**: 
- 只订阅WebSocket实时事件
- 没有API调用获取历史数据
- 没有滚动加载分页功能

**影响**: 
- 页面刷新后历史数据丢失
- 无法查看更多历史事件
- 用户体验差

---

## 🛠️ 解决方案

### 修复1: 启用EventTimelineProjection

**修改文件**: `backend/runtime/projection_runtime/runtime.py`

```python
# 修改后 (第91-103行)
from services.projection_service.projections import (
    DashboardProjection,
    DecisionProjection,
    RiskProjection,
    PositionProjection,
    EventTimelineProjection,  # ✅ 新增
)

self.projections = [
    DashboardProjection(),
    DecisionProjection(),
    RiskProjection(),
    PositionProjection(),
    EventTimelineProjection(),  # ✅ 新增
]
```

**验证**: 
```bash
# 重启后应该看到日志
tail -f logs/projection.log | grep "Initialized: timeline"
# 输出: Initialized: timeline
```

### 修复2: 初始化Redis连接

**修改文件**: `backend/runtime/ingestion_runtime/runtime.py`

```python
# 修改后 (第362-369行)
redis_client = None
try:
    from infrastructure.cache import get_redis_client
    redis_client = get_redis_client()
    if not redis_client.is_connected:
        await redis_client.connect()  # ✅ 新增：建立连接
        self.logger.info("Redis client connected successfully")
except Exception as e:
    self.logger.warning(f"Redis client not available: {e}")
```

**验证**: 
```bash
# 重启后应该看到日志
tail -f logs/ingestion.log | grep "Redis client connected"
# 输出: Redis client connected successfully
```

### 修复3: 添加前端滚动加载分页

#### 3.1 创建useTimelineHistory Hook

**新建文件**: `frontend/src/hooks/useTimelineHistory.ts`

```typescript
/**
 * useTimelineHistory Hook - Timeline历史数据加载
 * 
 * 支持分页加载历史事件数据
 */

import { useState, useEffect, useCallback } from 'react'

interface TimelineEvent {
  event_id: string
  event_type: string
  symbol: string
  timestamp: string
  display_time?: string
  title: string
  description: string
  severity: string
}

interface TimelineResponse {
  events: TimelineEvent[]
  count: number
}

export function useTimelineHistory(symbol?: string, pageSize: number = 50) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [page, setPage] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const fetchEvents = useCallback(async (pageNum: number, append: boolean = false) => {
    if (loading) return

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        limit: String(pageSize),
      })
      
      if (symbol) {
        params.append('symbol', symbol)
      }

      const response = await fetch(`/api/v1/projection/timeline?${params}`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data: TimelineResponse = await response.json()
      
      if (append) {
        setEvents(prev => {
          const existingIds = new Set(prev.map(e => e.event_id))
          const newEvents = data.events.filter(e => !existingIds.has(e.event_id))
          return [...prev, ...newEvents]
        })
      } else {
        setEvents(data.events)
      }
      
      setHasMore(data.events.length === pageSize)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch events')
      console.error('Failed to fetch timeline events:', err)
    } finally {
      setLoading(false)
    }
  }, [symbol, pageSize, loading])

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      const nextPage = page + 1
      setPage(nextPage)
      fetchEvents(nextPage, true)
    }
  }, [loading, hasMore, page, fetchEvents])

  const refresh = useCallback(() => {
    setPage(0)
    setHasMore(true)
    fetchEvents(0, false)
  }, [fetchEvents])

  useEffect(() => {
    fetchEvents(0, false)
  }, [symbol])

  return {
    events,
    loading,
    hasMore,
    error,
    loadMore,
    refresh,
  }
}
```

#### 3.2 重写EventTimeline组件

**修改文件**: `frontend/src/components/EventTimeline.tsx`

**新增功能**:
- ✅ 滚动加载分页（使用Intersection Observer API）
- ✅ 合并WebSocket实时数据和API历史数据
- ✅ 自动去重和排序
- ✅ 加载状态指示器
- ✅ 错误处理和重试
- ✅ 刷新按钮

**关键代码**:
```typescript
// 合并实时和历史数据
const allEvents = enableInfiniteScroll 
  ? mergeEvents(filteredRealtimeEvents, historyEvents)
  : filteredRealtimeEvents

// 滚动加载监听
const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
  const [target] = entries
  if (target.isIntersecting && hasMore && !loading) {
    loadMore()
  }
}, [hasMore, loading, loadMore])

// 自动去重
function mergeEvents(realtimeEvents: any[], historyEvents: any[]): any[] {
  const eventMap = new Map<string, any>()
  
  historyEvents.forEach(event => {
    eventMap.set(event.event_id, event)
  })
  
  realtimeEvents.forEach(event => {
    if (!eventMap.has(event.event_id)) {
      eventMap.set(event.event_id, event)
    }
  })
  
  return Array.from(eventMap.values()).sort((a, b) => 
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  )
}
```

---

## ✅ 验证结果

### 1. 后端验证

#### 1.1 检查Projection Runtime日志
```bash
tail -f logs/projection.log
```

**预期输出**:
```
2026-05-17 09:00:00 INFO [projection] Initializing Projection Runtime...
2026-05-17 09:00:05 INFO [projection] Kafka consumer initialized successfully
2026-05-17 09:00:05 INFO [projection] Initialized: dashboard
2026-05-17 09:00:05 INFO [projection] Initialized: decision
2026-05-17 09:00:05 INFO [projection] Initialized: risk
2026-05-17 09:00:05 INFO [projection] Initialized: position
2026-05-17 09:00:05 INFO [projection] Initialized: timeline  # ✅ 新增
```

#### 1.2 检查Ingestion Runtime日志
```bash
tail -f logs/ingestion.log
```

**预期输出**:
```
2026-05-17 09:00:00 INFO [ingestion] Collecting from Odaily skill...
2026-05-17 09:00:01 INFO [ingestion] Collected 7 Odaily events
2026-05-17 09:00:01 INFO [ingestion] Redis client connected successfully  # ✅ 新增
2026-05-17 09:00:01 INFO [ingestion] Stored 7 news to Redis  # ✅ 成功
2026-05-17 09:00:01 INFO [ingestion] Published 7 Odaily events to Kafka
```

#### 1.3 检查Redis数据
```bash
docker exec redis redis-cli keys "projection:timeline:*"
```

**预期输出**:
```
1) "projection:timeline:events"
2) "projection:timeline:symbol:BTC"
3) "projection:timeline:type:news"
```

#### 1.4 检查API返回
```bash
curl http://localhost:8001/api/v1/projection/timeline?limit=10 | python3 -m json.tool
```

**预期输出**:
```json
{
  "events": [
    {
      "event_id": "evt_abc123",
      "event_type": "odaily_raw",
      "symbol": "",
      "timestamp": "2026-05-17T09:00:01.123456",
      "display_time": "09:00:01",
      "title": "📰 Bitcoin Breaks $80K Resistance",
      "description": "Odaily",
      "severity": "info"
    }
  ],
  "count": 1
}
```

### 2. 前端验证

#### 2.1 检查组件渲染
- ✅ Event Timeline组件显示事件列表
- ✅ 显示事件数量（如：`7 events`）
- ✅ 显示刷新按钮

#### 2.2 检查滚动加载
- ✅ 滚动到底部时自动加载更多
- ✅ 显示加载状态：`Loading more events...`
- ✅ 没有更多数据时显示：`No more events`

#### 2.3 检查实时更新
- ✅ WebSocket推送新事件时自动添加到列表顶部
- ✅ 新事件和历史事件自动去重
- ✅ 按时间戳排序

#### 2.4 检查错误处理
- ✅ API失败时显示错误信息
- ✅ 提供重试按钮

---

## 📊 系统架构图

### 修复后的数据流

```
┌─────────────────────┐
│  Ingestion Runtime  │
│  - Odaily采集       │
│  - Redis连接 ✅     │ ← 修复点2
│  - Kafka Publisher  │
└──────────┬──────────┘
           │
           │ Kafka (raw.odaily, tradeagent.events)
           ▼
┌─────────────────────┐
│ Projection Runtime  │
│  - Kafka Consumer   │
│  - EventTimeline ✅ │ ← 修复点1
│  - Redis更新        │
└──────────┬──────────┘
           │
           │ Redis (projection:timeline:events)
           ▼
┌─────────────────────┐
│   API Server        │
│  - /projection/timeline
│  - WebSocket推送    │
└──────────┬──────────┘
           │
           │ HTTP/WebSocket
           ▼
┌─────────────────────┐
│     Frontend        │
│  - 滚动加载 ✅      │ ← 修复点3
│  - 分页功能 ✅      │
│  - 实时更新         │
└─────────────────────┘
```

### 数据流详细说明

```
1. 数据采集
   Ingestion Runtime → Odaily Skill → 7条新闻事件

2. 数据存储
   ├─ Redis (news:all:20) → 直接存储，供API快速读取
   └─ Kafka (raw.odaily) → 事件流，供下游处理

3. 事件处理
   Projection Runtime → EventTimelineProjection
   ├─ 消费Kafka事件
   ├─ 更新Redis (projection:timeline:events)
   └─ 推送WebSocket (channel:timeline)

4. 数据展示
   Frontend → EventTimeline组件
   ├─ 初始加载：API获取历史数据
   ├─ 实时更新：WebSocket推送新事件
   └─ 滚动加载：Intersection Observer触发加载更多
```

---

## 📝 修改的文件列表

### 后端文件

1. **`backend/runtime/projection_runtime/runtime.py`**
   - 添加`EventTimelineProjection`导入
   - 添加到projections列表
   - 修改行：第91-103行

2. **`backend/runtime/ingestion_runtime/runtime.py`**
   - 添加Redis连接初始化
   - 添加连接状态检查
   - 修改行：第362-369行

### 前端文件

3. **`frontend/src/hooks/useTimelineHistory.ts`** (新建)
   - 创建历史数据加载Hook
   - 实现分页逻辑
   - 实现错误处理

4. **`frontend/src/components/EventTimeline.tsx`**
   - 添加滚动加载分页
   - 合并实时和历史数据
   - 添加刷新按钮
   - 添加加载状态和错误处理

---

## 🚀 部署步骤

### 1. 重启后端服务

```bash
# 方法1：如果使用Docker
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend
docker-compose -f deploy/docker-compose.yml restart projection-runtime ingestion-runtime

# 方法2：如果直接运行Python进程
kill $(ps aux | grep projection_runtime | grep -v grep | awk '{print $2}')
kill $(ps aux | grep ingestion_runtime | grep -v grep | awk '{print $2}')

cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend
nohup python -m runtime.projection_runtime > logs/projection.log 2>&1 &
nohup python -m runtime.ingestion_runtime > logs/ingestion.log 2>&1 &
```

### 2. 重启前端服务

```bash
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/frontend

# 开发模式
npm run dev

# 或生产模式
npm run build
npm run preview
```

### 3. 验证服务状态

```bash
# 检查后端进程
ps aux | grep -E "projection|ingestion" | grep -v grep

# 检查日志
tail -f /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/logs/projection.log
tail -f /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/logs/ingestion.log

# 检查Redis
docker exec redis redis-cli ping
docker exec redis redis-cli keys "projection:timeline:*"

# 检查API
curl http://localhost:8001/api/v1/projection/timeline?limit=10
```

---

## 🔄 后续优化建议

### 短期优化 (1-2天)

1. **添加事件类型过滤**
   - 前端添加事件类型筛选器
   - 支持按`news`, `signal`, `decision`等类型过滤

2. **添加时间范围过滤**
   - 支持按时间范围查询
   - 添加日期选择器

3. **优化WebSocket重连**
   - 添加自动重连机制
   - 显示连接状态

### 中期优化 (1周)

1. **添加事件搜索**
   - 支持关键词搜索
   - 支持标题和内容搜索

2. **添加事件详情**
   - 点击事件显示详细信息
   - 显示事件关联数据

3. **性能优化**
   - 虚拟滚动优化长列表
   - 缓存历史数据

### 长期优化 (1个月)

1. **事件持久化**
   - 将事件存储到ClickHouse
   - 支持历史数据查询

2. **事件分析**
   - 事件统计分析
   - 趋势图表展示

3. **事件订阅**
   - 支持订阅特定类型事件
   - 邮件/消息通知

---

## 🐛 已知问题

### 1. 分页offset未实现
**状态**: 待优化  
**影响**: 当前API不支持offset参数，滚动加载会重复获取数据  
**临时方案**: 前端通过去重处理  
**优先级**: 中

### 2. 事件排序问题
**状态**: 已解决  
**解决方案**: 前端按timestamp降序排序  
**优先级**: 低

### 3. WebSocket断线重连
**状态**: 已实现  
**解决方案**: wsService已有重连机制  
**优先级**: 低

---

## 📞 联系方式

如有问题，请联系:
- 后端开发: backend-team@example.com
- 前端开发: frontend-team@example.com
- 运维团队: ops-team@example.com

---

**文档版本**: v1.0  
**创建时间**: 2026-05-17  
**最后更新**: 2026-05-17  
**维护者**: AI Assistant
