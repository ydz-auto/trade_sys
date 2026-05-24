# TradeLab Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    TRADELAB SYSTEM                                       │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              FRONTEND LAYER                                        │  │
│  │                          (Vue.js + Vite + Tailwind)                               │  │
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
│                              RUNTIME LAYER                                                │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                     kernel/ (RuntimeOrchestrator 总控)                           │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │   │
│  │  │DependencyGraph│ │  Registry    │ │  StateMachine│ │  Authority   │          │   │
│  │  │(启动拓扑排序) │ │(Runtime注册) │ │(CREATED→RUN) │ │(时钟/排序)   │          │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘          │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │   │
│  │  │  Lifecycle   │ │  Supervisor  │ │   Guards     │ │   Snapshot   │          │   │
│  │  │(start/stop)  │ │(健康守护)    │ │(守卫系统)    │ │(检查点/恢复) │          │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  stateful/ (有状态 Runtime — State Owners)                                      │   │
│  │                                                                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                    │   │
│  │  │   Ingestion    │  │    Feature     │  │     Signal     │                    │   │
│  │  │   Runtime      │  │    Runtime     │  │     Runtime    │                    │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘                    │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                    │   │
│  │  │   Execution    │  │   Portfolio    │  │     Replay     │                    │   │
│  │  │   Runtime      │  │   Runtime      │  │     Runtime    │                    │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘                    │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  analytical/ (分析型 Runtime — 只读/投影)                                       │   │
│  │                                                                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                    │   │
│  │  │  Correlation   │  │  Projection    │  │     Regime     │                    │   │
│  │  │  Runtime       │  │  Runtime       │  │     Runtime    │                    │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘                    │   │
│  │  ┌────────────────┐                                                                 │   │
│  │  │  Narrative     │                                                                 │   │
│  │  │  Runtime       │                                                                 │   │
│  │  └────────────────┘                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
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
│                              ENGINES LAYER                                                │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  adapters/ (外部适配器)                                                         │   │
│  │  ┌────────────────────────────┐  ┌────────────────────────────┐                │   │
│  │  │  data/collectors/          │  │  exchange/                 │                │   │
│  │  │  (Binance WS, 新闻, ETF)   │  │  (Binance, OKX, Mock)     │                │   │
│  │  └────────────────────────────┘  └────────────────────────────┘                │   │
│  │  ┌────────────────────────────┐  ┌────────────────────────────┐                │   │
│  │  │  data/feeds/               │  │  data/sources/             │                │   │
│  │  │  (Odaily, QQ, Twitter)     │  │  (QQ, Telegram 实时)       │                │   │
│  │  └────────────────────────────┘  └────────────────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  compute/ (业务计算引擎)                                                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │Aggregat- │ │Correlat- │ │ Feature  │ │   Risk   │ │  Signal  │            │   │
│  │  │  ion     │ │  ion     │ │ Compute  │ │ Compute  │ │ Compute  │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                                       │   │
│  │  │ Strategy │ │ Scoring  │ │  Models  │                                       │   │
│  │  │ Compute  │ │  (LLM)   │ │          │                                       │   │
│  │  └──────────┘ └──────────┘ └──────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  ml/ (机器学习)                                                                 │   │
│  │  LSTM Compute │ LSTM Dataset Builder │ LSTM Strategy                            │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Trading Decision Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   News /    │     │  Ingestion  │     │   Market    │
│   Social    │────▶│   Runtime   │────▶│   Events    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Validation  │     │   Signal    │     │   Signal   │
│  Boundary    │◀────│   Runtime   │◀────│   Events    │
└──────┬──────┘     └─────────────┘     └──────┬──────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Approved  │     │   Multi-   │     │   Signal    │
│   Signals   │────▶│ Timeframe  │────▶│   Narrative │
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

### Runtime Layer

```
┌─────────────────────────────────────────────────────────────┐
│                      Runtime Layer                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  kernel/                                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  orchestrator/   RuntimeOrchestrator (总控)           │   │
│  │  authority/      时钟/排序/可用性/所有权              │   │
│  │  context/        RuntimeContext + Session             │   │
│  │  event/          RuntimeBus (纯 transport)            │   │
│  │  guards/         守卫系统 (9个守卫)                   │   │
│  │  lifecycle/      StateMachine + HealthSystem          │   │
│  │  namespace/      模式隔离                             │   │
│  │  replay/         回放内核                             │   │
│  │  shared/         运行时共享组件                       │   │
│  │  snapshot/       检查点/恢复                          │   │
│  │  state/          RuntimeStateStore (只读聚合)         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  stateful/                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  IngestionRuntime   FeatureRuntime   SignalRuntime   │   │
│  │  ExecutionRuntime   PortfolioRuntime  ReplayRuntime  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  analytical/                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CorrelationRuntime  ProjectionRuntime               │   │
│  │  RegimeRuntime       NarrativeRuntime                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  contracts/   pipeline/   replay/   verification/   jobs/   │
└─────────────────────────────────────────────────────────────┘
```

### Engines Layer

```
┌─────────────────────────────────────────────────────────────┐
│                      Engines Layer                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  adapters/                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  data/collectors/   数据采集器 (Binance WS, 新闻)    │   │
│  │  data/feeds/        数据源适配器 (Odaily, QQ)        │   │
│  │  data/sources/      实时数据源 (QQ, Telegram)        │   │
│  │  exchange/          交易所适配器 (Binance, OKX)      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  compute/                                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  aggregation/       K线聚合                           │   │
│  │  correlation/       相关性分析                        │   │
│  │  feature/           特征计算 (GPU, 统一计算器)        │   │
│  │  models/            数据模型 (Candle, OrderBook)      │   │
│  │  risk/              风险计算引擎 (9个检查器)          │   │
│  │  signal/            信号生成 (融合引擎, 评分器)       │   │
│  │  strategy/          策略管理 (注册/发现/符号)         │   │
│  │  scoring/           LLM 评分                          │   │
│  │  schemas/           信号 Schema                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ml/                                                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  lstm_compute.py        LSTM 计算                     │   │
│  │  lstm_dataset_builder.py ML 数据集构建                │   │
│  │  lstm_strategy.py       LSTM 策略                     │   │
│  └──────────────────────────────────────────────────────┘   │
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
| backend | 8001 | FastAPI server |
| redis | 6379 | Redis cache |
| kafka | 9092 | Kafka broker |
| zookeeper | 2181 | Zookeeper |
| clickhouse | 8123 | ClickHouse |
| frontend | 3000 | Vue.js frontend |
| kafka-ui | 8080 | Kafka management UI |

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
| `/api/v1/trading/dashboard` | GET | Trading dashboard |
| `/api/v1/backtest/start` | POST | Start backtest |
| `/api/v1/optimization/start` | POST | Start optimization |
| `/api/v1/feature/matrix` | GET | Feature matrix |
| `/api/v1/factors` | GET | Factor data |
| `/api/v1/alpha/lifecycle` | GET | Alpha lifecycle |

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
| Frontend | Vue.js 3, Vite, Tailwind CSS, Zustand |
| API | FastAPI, Uvicorn |
| WebSocket | FastAPI WebSockets |
| State | Redis |
| Events | Kafka |
| Storage | ClickHouse, PostgreSQL, Parquet |
| Monitoring | Prometheus, Grafana, Tempo |
| Container | Docker, Docker Compose |
| ML | PyTorch, LSTM |
| LLM | Minimax / OpenRouter / Local Models |
