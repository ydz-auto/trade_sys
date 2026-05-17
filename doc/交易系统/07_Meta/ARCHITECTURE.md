# TradeLab Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    TRADELAB SYSTEM                                       │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              FRONTEND LAYER                                        │  │
│  │                                                                                  │  │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │  │
│  │   │  Dashboard  │  │   Decision  │  │    Risk    │  │  Timeline   │          │  │
│  │   │    Page     │  │    Page     │  │    Panel    │  │    Page     │          │  │
│  │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │  │
│  │          │                │                │                │                   │  │
│  │          └────────────────┴────────────────┴────────────────┘                    │  │
│  │                                     │                                             │  │
│  │                    ┌────────────────┴────────────────┐                         │  │
│  │                    │      Realtime Store           │                         │  │
│  │                    │    (Zustand + WS Service)     │                         │  │
│  │                    └────────────────┬────────────────┘                         │  │
│  └─────────────────────────────────────┼───────────────────────────────────────┘  │
│                                        │                                                        │
└────────────────────────────────────────┼────────────────────────────────────────────────┘
                                         │ HTTP/WebSocket
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  API LAYER (FastAPI)                                       │
│                                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  /dashboard │  │ /projection  │  │  /factors   │  │   /alpha    │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                │                          │
│         └────────────────┴────────────────┴────────────────┘                          │
│                                     │                                                    │
│                    ┌────────────────┴────────────────┐                                │
│                    │   Projection Reader Service    │                                │
│                    │    (Reads from Redis)          │                                │
│                    └────────────────┬────────────────┘                                │
│                                     │                                                  │
│                    ┌────────────────┴────────────────┐                                │
│                    │       WS Gateway              │                                │
│                    │  (Redis Pub/Sub + WebSocket)  │                                │
│                    └────────────────┬────────────────┘                                │
└─────────────────────────────────────┼────────────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
┌───────────────────────────────────┐    ┌───────────────────────────────────┐
│             REDIS                 │    │            KAFKA                 │
│                                   │    │                                   │
│  projection:dashboard:state       │    │  ┌─────────────────────────┐     │
│  projection:decision:latest       │    │  │ tradeagent.events.all    │     │
│  projection:risk:state            │    │  │ tradeagent.decisions     │     │
│  projection:position:current       │    │  │ tradeagent.risk          │     │
│  projection:timeline:events        │    │  └─────────────────────────┘     │
│                                   │    │                                   │
└───────────────────────────────────┘    └───────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              PROJECTION WORKER                                           │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           Schema Validation Layer                                │   │
│  │                    (BaseEventV2 + Schema Registry)                              │   │
│  └─────────────────────────────────┬───────────────────────────────────────────────┘   │
│                                    │                                                        │
│  ┌─────────────────────────────────┴───────────────────────────────────────────────┐   │
│  │                         Projection Layer                                        │   │
│  │                                                                                │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                   │   │
│  │  │   Dashboard   │  │   Decision     │  │     Risk      │                   │   │
│  │  │  Projection   │  │   Projection   │  │   Projection  │                   │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘                   │   │
│  │                                                                                │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                   │   │
│  │  │   Position     │  │    Event       │  │  Portfolio     │                   │   │
│  │  │  Projection   │  │   Timeline     │  │   Projection   │                   │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                               RUNTIME DOMAIN                                              │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                     Multi-Timeframe Coordinator                                 │   │
│  │                                                                                │   │
│  │      1D (Macro)  ──►  4H (Swing)  ──►  1H (Intraday)  ──►  15M (Micro)       │   │
│  │                                                                                │   │
│  │      • Signal Alignment    • Position Sizing    • Risk Calculation           │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  Validation      │  │     Replay      │  │   Narrative      │                     │
│  │  Boundary        │  │     Engine       │  │     Engine       │                     │
│  │                  │  │                  │  │                  │                     │
│  │  • IC Check      │  │  • Historical    │  │  • Decision     │                     │
│  │  • Sharpe        │  │    Replay       │  │    Explanation  │                     │
│  │  • Drawdown      │  │  • Strategy     │  │  • Signal        │                     │
│  │  • Regime         │  │    Simulation  │  │    Narrative    │                     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘                     │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           Observability Layer                                   │   │
│  │                                                                                │   │
│  │  signal_latency │ factor_staleness │ regime_conflict │ kafka_lag │ ws_latency│   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 WORKER RUNTIMES                                           │
│                                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Data        │  │  Strategy    │  │  Execution   │  │   Research   │              │
│  │   Worker      │  │  Worker      │  │  Worker      │  │   System     │              │
│  │               │  │              │  │              │  │              │              │
│  │ • News Feed   │  │ • Signals    │  │ • Risk Check │  │ • Alpha      │              │
│  │ • Price Feed  │  │ • Decisions   │  │ • Orders     │  │ • Walk Fwd   │              │
│  │ • Social      │  │ • Alpha Gen   │  │ • Fills      │  │ • Proposals   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                 │                        │
│         └─────────────────┴─────────────────┴─────────────────┘                        │
│                                   │                                                    │
└───────────────────────────────────┼────────────────────────────────────────────────────┘
                                    ▼
                              ┌──────────────┐
                              │    Kafka     │
                              │   Event Bus  │
                              └──────────────┘
```

## Data Flow

### Trading Decision Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   News /    │     │    Data     │     │   Market    │
│   Social    │────▶│   Worker    │────▶│   Events    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Validation  │     │  Strategy   │     │   Signal   │
│  Boundary    │◀────│  Worker     │◀────│   Events    │
└──────┬──────┘     └─────────────┘     └──────┬──────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Approved  │     │   Multi-   │     │   Signal    │
│   Signals   │────▶│  Timeframe  │────▶│   Narrative │
└─────────────┘     │  Coordinator │     └─────────────┘
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Decision  │     │     Risk    │
                    │   Events    │────▶│   Check     │
                    └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Orders    │
                                        │   / Fills   │
                                        └──────┬──────┘
                                               │
                    ┌────────────────────────────┘
                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Event     │     │  Portfolio  │     │  Narrative  │
│   Timeline  │◀────│  Projection │◀────│   Engine   │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Multi-Timeframe Coordination

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Multi-Timeframe Coordinator                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    1D (Macro)        4H (Swing)        1H (Intraday)    15M        │
│       │                 │                 │            │          │
│       ▼                 ▼                 ▼            ▼          │
│   ┌───────┐         ┌───────┐         ┌───────┐    ┌───────┐       │
│   │ Bull  │         │ Bull  │         │ Bull  │    │Mixed  │       │
│   │ 80%   │    +    │ 75%   │    +    │ 65%   │ =  │ 40%   │       │
│   └───────┘         └───────┘         └───────┘    └───────┘       │
│       │                 │                 │            │             │
│       └─────────────────┴─────────────────┴────────────┘             │
│                              │                                      │
│                              ▼                                      │
│                     ┌────────────────┐                               │
│                     │ PERFECT        │                               │
│                     │ ALIGNMENT      │                               │
│                     │ Score: 0.85    │                               │
│                     └────────────────┘                               │
│                              │                                       │
│              ┌───────────────┼───────────────┐                       │
│              ▼               ▼               ▼                       │
│       Position Size    Stop Loss       Take Profit                  │
│          2.0x             1.5%             4.5%                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Projection Worker

```
┌─────────────────────────────────────────────────────────────┐
│                   Projection Worker                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: Kafka Events                                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  tradeagent.events.all    - All events               │   │
│  │  tradeagent.decisions    - Decision events           │   │
│  │  tradeagent.risk         - Risk check events         │   │
│  │  tradeagent.orders       - Order events              │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                                │
│                              ▼                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Schema Validation                         │   │
│  │                 (BaseEventV2)                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                                │
│                              ▼                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Projection Layer                          │   │
│  │                                                        │   │
│  │   ┌──────────────┐    ┌──────────────┐               │   │
│  │   │  Dashboard   │    │  Decision    │               │   │
│  │   │  Projection  │    │  Projection  │               │   │
│  │   └──────┬───────┘    └──────┬───────┘               │   │
│  │          │                   │                       │   │
│  │   ┌──────┴───────┐    ┌──────┴───────┐               │   │
│  │   │ Risk        │    │ Position    │               │   │
│  │   │ Projection  │    │ Projection  │               │   │
│  │   └─────────────┘    └─────────────┘               │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                                │
│                              ▼                                │
│  Output: Redis State + WebSocket                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  projection:dashboard:state    → Dashboard State      │   │
│  │  projection:decision:latest    → Latest Decision      │   │
│  │  projection:risk:state         → Risk Status         │   │
│  │  projection:position:current   → Current Positions  │   │
│  │  projection:timeline:events     → Event Timeline     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  + WebSocket Push: channel:dashboard, channel:decision, etc │
└─────────────────────────────────────────────────────────────┘
```

### Validation Boundary

```
┌─────────────────────────────────────────────────────────────┐
│                  Validation Boundary                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Research Domain          │        Runtime Domain           │
│  ┌──────────────┐         │         ┌──────────────┐        │
│  │  Alpha       │─────────┼────────▶│   Strategy   │        │
│  │  Proposals   │         │         │   Worker     │        │
│  └──────────────┘         │         └──────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Validation Pipeline                    │   │
│  │                                                        │   │
│  │   ┌─────────┐   ┌─────────┐   ┌─────────┐            │   │
│  │   │ Receive │──▶│ Validate│──▶│ Deploy  │            │   │
│  │   │Proposal │   │         │   │         │            │   │
│  │   └─────────┘   └─────────┘   └────┬────┘            │   │
│  │                                   │                 │   │
│  │   Criteria:                       │                 │   │
│  │   • IC ≥ 0.02                     │                 │   │
│  │   • Sharpe ≥ 0.5                  │                 │   │
│  │   • Drawdown ≤ 20%               │                 │   │
│  │   • Regime Coverage ≥ 60%         │                 │   │
│  │   • Decay ≤ 30%                  │                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Lifecycle:                                                  │
│  PROPOSED → VALIDATING → VALIDATED/REJECTED → DEPLOYED →   │
│  → MONITORING → DEGRADED → ROLLBACK                         │
└─────────────────────────────────────────────────────────────┘
```

## Deployment

### Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.simple.yml up

# Start production
docker-compose -f docker-compose.yml up -d

# View logs
docker-compose -f docker-compose.simple.yml logs -f

# Stop
docker-compose -f docker-compose.simple.yml down
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| backend | 8000 | FastAPI server |
| redis | 6379 | Redis cache |
| kafka | 9092 | Kafka broker |
| zookeeper | 2181 | Zookeeper |
| clickhouse | 8123 | ClickHouse |
| frontend | 3000 | Next.js frontend |

## API Endpoints

### Core APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/dashboard` | GET | Dashboard data |
| `/api/v1/projection/dashboard` | GET | Projection state |
| `/api/v1/projection/decision/latest` | GET | Latest decision |
| `/api/v1/projection/risk/state` | GET | Risk state |
| `/api/v1/projection/position/current` | GET | Current positions |
| `/api/v1/projection/timeline` | GET | Event timeline |

### WebSocket

```
WS /ws

# Subscribe
{"type": "subscribe", "channels": ["channel:dashboard", "channel:decision"]}

# Channels
- channel:dashboard
- channel:decision
- channel:risk
- channel:position
- channel:timeline
- channel:signal
- channel:order
```

## Observability

### Metrics

| Metric | Description |
|--------|-------------|
| `signal_latency_ms` | Signal generation to execution latency |
| `factor_staleness_minutes` | Time since factor last update |
| `regime_conflict` | Regime alignment conflict score |
| `proposal_decay` | Alpha decay rate |
| `replay_divergence` | Divergence between replay and live |
| `kafka_lag` | Kafka consumer lag |
| `ws_latency_ms` | WebSocket message latency |
| `decision_latency_ms` | End-to-end decision latency |

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js, React, Zustand |
| API | FastAPI, Uvicorn |
| WebSocket | FastAPI WebSockets |
| State | Redis |
| Events | Kafka |
| Storage | ClickHouse |
| Monitoring | Prometheus, Grafana |
| Container | Docker, Docker Compose |
