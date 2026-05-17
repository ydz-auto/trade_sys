# Runtime State Architecture - 完整架构

## 概述

本文档描述了系统的完整架构，包括：

1. **Runtime State Architecture** - Runtime 状态层
2. **Validation Boundary** - Research → Runtime 隔离
3. **Event Schema Registry** - 统一事件 Schema
4. **Portfolio Projection** - 持仓状态分离

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESEARCH DOMAIN                                    │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Factor       │  │ Alpha        │  │ Walk         │  │ Proposal     │     │
│  │ Generator    │  │ Lifecycle    │  │ Forward      │  │ Generator    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │              │
│         └─────────────────┼─────────────────┼─────────────────┘              │
│                           │                 │                               │
└───────────────────────────┼─────────────────┼───────────────────────────────┘
                            │                 │
                            ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       VALIDATION BOUNDARY                                    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Validation Pipeline                                                   │   │
│  │                                                                       │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │   │
│  │  │ Receive  │──▶│ Validate │──▶│ Approve  │──▶│ Deploy   │         │   │
│  │  │ Proposal │   │          │   │          │   │          │         │   │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘         │   │
│  │       │              │              │              │                 │   │
│  │       │              │              │              │                 │   │
│  │       ▼              ▼              ▼              ▼                 │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │   │
│  │  │ IC Score │   │ Sharpe   │   │ Signal   │   │ Runtime  │         │   │
│  │  │ Regimes  │   │ Drawdown │   │ Approved │   │ Config   │         │   │
│  │  │ Decay    │   │ Coverage │   │          │   │          │         │   │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘         │   │
│  │                                                                       │   │
│  │  Validation Criteria:                                                  │   │
│  │  - min_ic: 0.02                                                       │   │
│  │  - min_sharpe: 0.5                                                    │   │
│  │  - max_drawdown: 0.2                                                  │   │
│  │  - regime_coverage: 0.6                                               │   │
│  │  - decay_threshold: 0.3                                                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RUNTIME DOMAIN                                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        EVENT SCHEMA REGISTRY                           │ │
│  │                                                                        │ │
│  │  BaseEventV2:                                                          │ │
│  │  - event_id, trace_id, parent_event_id                                 │ │
│  │  - event_type, source                                                  │ │
│  │  - timestamp (ISO), symbol (normalized)                                │ │
│  │  - exchange, timeframe                                                 │ │
│  │  - metadata                                                            │ │
│  │                                                                        │ │
│  │  Event Types:                                                         │ │
│  │  - raw_data, market, event, signal, decision                           │ │
│  │  - risk_checked, order, fill, pnl, system                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                        │
│  │ DataWorker   │  │StrategyWorker│  │ExecutionWorker│                       │
│  │              │  │              │  │              │                        │
│  │ - RawData    │  │ - Signal     │  │ - RiskCheck  │                        │
│  │ - Market     │  │ - Decision   │  │ - Order      │                        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                        │
│         │                 │                 │                                │
│         └─────────────────┼─────────────────┘                                │
│                           │                                                 │
│                           ▼                                                 │
│                    ┌──────────────┐                                           │
│                    │    Kafka    │                                           │
│                    │  Event Bus  │                                           │
│                    └──────┬───────┘                                           │
│                           │                                                  │
└───────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROJECTION LAYER                                     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Projection Worker                                                      │   │
│  │                                                                        │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐          │   │
│  │  │ Dashboard      │  │ Decision       │  │ Risk           │          │   │
│  │  │ Projection     │  │ Projection     │  │ Projection     │          │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘          │   │
│  │                                                                        │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐          │   │
│  │  │ Position       │  │ Event         │  │ Portfolio      │          │   │
│  │  │ Projection     │  │ Timeline      │  │ Projection     │          │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘          │   │
│  │                                                                        │   │
│  │  Schema Validation:                                                   │   │
│  │  - All events validated against EventSchemaRegistry                   │   │
│  │  - Symbol normalization (BTC/USDT → BTCUSDT)                          │   │
│  │  - Timestamp standardization                                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STATE LAYER                                         │
│                                                                              │
│         ┌──────────────┐           ┌──────────────┐                         │
│         │    Redis     │           │ ClickHouse   │                         │
│         │              │           │              │                         │
│         │ Current      │           │ History      │                         │
│         │ State        │           │ Snapshots    │                         │
│         │              │           │ Timeline     │                         │
│         │ - dashboard  │           │ - events     │                         │
│         │ - decisions  │           │ - positions  │                         │
│         │ - risk       │           │ - fills      │                         │
│         │ - positions  │           │ - pnl        │                         │
│         │ - timeline    │           │              │                         │
│         └──────────────┘           └──────────────┘                         │
│                                                                              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
┌────────────────────────────┐    ┌────────────────────────────────────┐
│         REST API           │    │         WS GATEWAY                 │
│                            │    │                                    │
│ /projection/dashboard      │    │  channel:dashboard                 │
│ /projection/decision/*     │    │  channel:decision                  │
│ /projection/risk/*         │    │  channel:risk                     │
│ /projection/position/*     │    │  channel:position                 │
│ /projection/timeline       │    │  channel:timeline                  │
│                            │    │  channel:signal                   │
│                            │    │  channel:order                    │
└────────────────────────────┘    └────────────────────────────────────┘
              │                                 │
              └────────────────┬────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Realtime Store (Zustand)                                             │   │
│  │                                                                       │   │
│  │  - dashboard: prices, signals, regime                                │   │
│  │  - decisions: latest, history, stats                                │   │
│  │  - risk: level, components, warnings                                  │   │
│  │  - positions: current, pnl                                           │   │
│  │  - timeline: events[]                                                │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Components:                                                                │
│  - Dashboard: composite score, factors, positions                          │
│  - EventTimeline: real-time event stream                                   │
│  - RiskPanel: risk level, components                                        │
│  - PositionTable: current positions, PnL                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Validation Boundary

**位置**: `domain/validation_boundary.py`

**职责**:
- 隔离 Research 和 Runtime
- 验证 Proposal 是否满足标准
- 将通过的 Proposal 转换为 Runtime Signal

**验证标准**:
```python
ValidationCriteria:
    min_ic: 0.02
    min_sharpe: 0.5
    max_drawdown: 0.2
    regime_coverage: 0.6
    decay_threshold: 0.3
```

**生命周期**:
```
PROPOSED → VALIDATING → VALIDATED/REJECTED → DEPLOYED → MONITORING/DEGRADED
```

### 2. Event Schema Registry

**位置**: `infrastructure/messaging/schema_registry.py`

**BaseEventV2 规范**:
```python
BaseEventV2:
    event_id: str          # 事件唯一ID
    event_type: EventType  # 事件类型
    trace_id: str          # 链路追踪ID
    parent_event_id: str   # 父事件ID（可选）
    timestamp: datetime    # ISO 格式时间戳
    source: EventSource    # 事件来源
    symbol: str           # 标准化品种 (BTCUSDT)
    exchange: str          # 交易所
    timeframe: str         # 时间周期
    metadata: dict         # 扩展元数据
```

**Symbol 标准化**:
- `BTC/USDT` → `BTCUSDT`
- `BTC-USDT` → `BTCUSDT`
- `BTC` → `BTCUSDT`

### 3. Portfolio Projection

**位置**: `domain/portfolio_projection.py`

**职责**:
- 持仓状态持久化
- PnL 计算
- 持仓历史和回溯

**Position 核心属性**:
```python
Position:
    symbol: str
    side: long/short/flat
    size: float
    entry_price: float
    current_price: float
    leverage: int
    
    # Computed
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    pnl_percentage: float
```

### 4. Projection Worker

**位置**: `services/projection_worker/`

**Projections**:

| Projection | 消费 Topics | 输出 |
|------------|-------------|------|
| DashboardProjection | RAW_DATA, SIGNALS, EVENTS | Redis dashboard state |
| DecisionProjection | DECISIONS, RISK_CHECKED | Redis decisions |
| RiskProjection | RISK_CHECKED, ORDERS | Redis risk state |
| PositionProjection | ORDERS, FILLS | Redis positions |
| EventTimelineProjection | ALL | Redis timeline |
| PortfolioProjection | FILLS | Redis + snapshots |

**Schema 验证**:
- 所有事件经过 EventSchemaRegistry 验证
- 无效事件被拒绝并记录
- 验证通过率统计

## 数据流

### 决策流程

```
1. Research 生成 Proposal
   ↓
2. Validation Boundary 接收
   ↓
3. 验证 IC, Sharpe, Drawdown 等
   ↓
4. 通过 → 生成 ApprovedSignal
   ↓
5. StrategyWorker 消费 Signal
   ↓
6. 发布 Decision Event
   ↓
7. Projection Worker 消费
   ↓
8. 更新 Redis 状态
   ↓
9. 推送 WebSocket
   ↓
10. Frontend 更新
```

### Event Timeline

```
09:31 📰 ETF inflow detected (raw_data)
09:32 ⚡ 4H bullish regime confirmed (event)
09:33 📊 Signal: BTC_BULLISH (signal)
09:34 🎯 Decision: LONG BTCUSDT (decision)
09:35 🛡️ Risk Check: LOW (risk_checked)
09:35 📝 Order: buy BTCUSDT (order)
09:35 💰 Fill: 0.01 @ 62345 (fill)
```

## 启动顺序

```bash
# 1. 启动基础设施
docker-compose up -d redis kafka

# 2. 启动 Projection Worker
python -m services.projection_worker.main

# 3. 启动 Validation Boundary (嵌入 Worker)
# 已包含在 Projection Worker

# 4. 启动 API Server
python api_server.py

# 5. 启动前端
cd frontend && npm run dev
```

## 验证

```bash
# 验证完整架构
python scripts/verify_architecture.py
```

## 后续扩展

### P1: Timeframe Coordinator

多周期协调：
- 1h signal → 4h confirmation → 1d context
- Regime hierarchy
- Signal aggregation

### P2: Replay Engine

从 ClickHouse 重放事件：
- Historical backtesting
- Strategy validation
- AI explainability

### P3: Narrative Engine

AI 记忆和推理：
- Event sequence summarization
- Decision explanation
- Runtime cognition
