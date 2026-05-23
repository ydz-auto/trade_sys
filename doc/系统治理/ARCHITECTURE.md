# 系统架构文档

**更新日期**: 2026-05-23
**架构版本**: Runtime-Oriented Architecture v4.0

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Server                              │
│  FastAPI lifespan: orchestrator.start() / orchestrator.stop()   │
│  Routes: 只调 APPLICATION，不碰 Runtime/Services/Infrastructure │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION                              │
│                                                                 │
│  Commands (写)              Queries (读)           Workflows    │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────┐  │
│  │ TradingCommands │   │ PortfolioQueries │   │ Optimization │  │
│  │ ModeCommands    │   │ ExecutionQueries │   │   Service    │  │
│  │ BacktestCommands│   │ SystemQueries    │   │              │  │
│  └────────┬────────┘   └────────┬────────┘   └──────┬───────┘  │
│           │  Registry           │                    │          │
└───────────┼──────────────────────┼───────────────────┼──────────┘
            ↓                      ↓                   ↓
┌─────────────────────────────────────────────────────────────────┐
│                     RUNTIME LAYER                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              RuntimeOrchestrator (总控)                   │   │
│  │                                                          │   │
│  │  职责：系统级生命周期，不处理业务请求                       │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │   │
│  │  │DependencyGraph│ │  Registry    │ │  StateMachine    │  │   │
│  │  │(启动拓扑排序) │ │(Runtime注册) │ │(CREATED→RUNNING) │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────┘  │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │   │
│  │  │  Lifecycle   │ │  Supervisor  │ │  HealthSystem    │  │   │
│  │  │(start/stop)  │ │(健康守护)    │ │(健康检查)        │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────┘  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              RuntimeBus (纯 transport)                    │   │
│  │  subscribe / publish / broadcast / route                  │   │
│  │  ⚠️ 不持有业务状态，不做业务路由                           │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Runtimes (State Owners)                      │   │
│  │                                                          │   │
│  │  IngestionRuntime   FeatureRuntime     SignalRuntime     │   │
│  │  ExecutionRuntime   PortfolioRuntime   ProjectionRuntime │   │
│  │  CorrelationRuntime ReplayRuntime      RegimeRuntime     │   │
│  │  NarrativeRuntime                                     │   │
│  │                                                          │   │
│  │  每个 Runtime 是自己领域的 State Owner:                   │   │
│  │    position → PortfolioRuntime                           │   │
│  │    order    → ExecutionRuntime                           │   │
│  │    signal   → SignalRuntime                              │   │
│  │    feature  → FeatureRuntime                             │   │
│  │    replay   → ReplayRuntime                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Runtime 编排组件:                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  timeframe_coordinator.py  多周期信号协调                  │   │
│  │  validation_boundary.py    Research→Runtime 隔离          │   │
│  │  trading_mode_manager.py   模式状态机+Adapter管理          │   │
│  │  isolation/namespace.py    模式隔离 (有状态，合法 Runtime) │   │
│  │  feature_runtime/          特征生成/守卫/物化              │   │
│  │    generation_guard.py     特征可用性守卫                  │   │
│  │    realtime_materializer.py 实时特征物化                   │   │
│  │    time_discipline.py      特征时间纪律                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICES                                 │
│                                                                 │
│  execution_service/   correlation_service/   projection_service/ │
│  data_service/        aggregation_service/   backtest_service/   │
│  strategy_service/    feature_service/       research_service/   │
│  portfolio_service/   repair_service/                            │
│                                                                 │
│  feature_service/       (从 Domain 迁入)                        │
│    torch_calculator.py      GPU 特征计算                        │
│    historical_materializer.py 历史数据管道                      │
│    unified_calculator.py    统一特征计算器 (从 runtime 迁入)     │
│                                                                 │
│  strategy_service/      (从 runtime 迁入)                       │
│    strategy_registry.py     策略注册中心                        │
│                                                                 │
│  research_service/      (从 Domain 迁入)                        │
│    lstm_dataset_builder.py  ML 数据集构建                       │
│    lstm_strategy.py         LSTM 策略                          │
│                                                                 │
│  portfolio_service/     (从 Domain 迁入)                        │
│    service.py               组合服务                            │
│                                                                 │
│  ⚠️ 不 import Runtime，通过 DI 接收 Bus/回调                    │
│  ⚠️ 不 import Application                                       │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌──────────────────────┐  ┌───────────────────────────────────────┐
│       DOMAIN         │  │          INFRASTRUCTURE                │
│                      │  │                                       │
│  纯交易规则与语义    │  │  无状态原语                            │
│  零业务层依赖        │  │  Kafka / Redis / DB / WebSocket        │
│  计算基础设施:       │  │  Logging / Config / Storage / Clock    │
│  numpy/pandas/pydant │  │  Pipeline / Replay(data only)          │
│  behaviour/          │  │  CircuitBreaker / PriorityQueue        │
│  event/              │  │  SubscriptionManager                  │
│  execution/          │  │  acceleration/ (GPU加速)              │
│  feature/            │  │  progress/   (进度追踪)               │
│  portfolio/          │  │  state/      (状态管理)               │
│  replay/             │  │  messaging/  (Kafka 消费者/发布者)    │
│  risk/               │  │  observability/ (运行时指标)          │
│  signal/             │  │                                       │
│  strategy/           │  │  → DOMAIN (仅类型/枚举)               │
│  trading_mode/       │  │                                       │
│  analysis/           │  │                                       │
│  runtime_commands.py │  │                                       │
│  logging.py          │  │                                       │
└──────────────────────┘  └───────────────────────────────────────┘
```

---

## 依赖方向规则

```
API ──→ APPLICATION ──┬──→ RUNTIME (Orchestrator + 各 Runtime)
                      ├──→ SERVICES
                      ├──→ DOMAIN
                      └──→ INFRASTRUCTURE

RUNTIME ──→ DOMAIN
RUNTIME ──→ INFRASTRUCTURE
RUNTIME ──→ SERVICES (⚠️ 通过 DI 注入，不 import)

SERVICES ──→ DOMAIN
SERVICES ──→ INFRASTRUCTURE
SERVICES ──✗ RUNTIME     (禁止)
SERVICES ──✗ APPLICATION (禁止)

INFRASTRUCTURE ──→ DOMAIN (仅类型/枚举)
INFRASTRUCTURE ──✗ RUNTIME / SERVICES / APPLICATION (禁止)

DOMAIN ──✗ 任何其他业务层 (零业务层依赖)
DOMAIN ──→ 计算基础设施 (numpy, pandas, pydantic) — 视同标准库
DOMAIN ──→ INFRASTRUCTURE (仅通过 DI 注入 + lazy import fallback)
```

### 依赖规则速查表

| 层 | 可依赖 | 不可依赖 |
|---|---|---|
| **API** | APPLICATION | RUNTIME, SERVICES, INFRA, DOMAIN |
| **APPLICATION** | SERVICES, RUNTIME, DOMAIN, INFRA | — |
| **RUNTIME** | DOMAIN, INFRA, SERVICES(通过DI) | API, APPLICATION |
| **SERVICES** | DOMAIN, INFRA | RUNTIME, API, APPLICATION |
| **DOMAIN** | 标准库 + 计算基础设施(numpy/pandas/pydantic) | API, RUNTIME, SERVICES, APPLICATION |
| **INFRASTRUCTURE** | DOMAIN(仅类型/枚举) | RUNTIME, SERVICES, API, APPLICATION |

---

## 各层职责

### API 层
- HTTP 路由、请求校验、序列化
- WebSocket 端点
- **只调 APPLICATION**，不直接碰 Runtime/Services/Infrastructure

### APPLICATION 层
- **Commands**: 写操作，编排跨 Service/Runtime 的写流程
- **Queries**: 读操作，聚合多个 Runtime 的状态给 API 用
- **Workflows**: 长流程，跨多步骤的用例（如 OptimizationService）
- **Registry**: 领域配置注册表

### RUNTIME 层
- **RuntimeOrchestrator**: 系统级生命周期管理（启动/停止/模式切换）
- **RuntimeBus**: 纯 transport（pub/sub/routing），不持有业务状态
- **各 Runtime**: 自己领域的 State Owner
- **Runtime 编排组件**: 从 Domain 迁入的 runtime 逻辑（特征生成/守卫/物化、模式管理、时间协调等）

### SERVICES 层
- 单领域业务逻辑
- 通过 DI 接收 Bus/回调，不 import Runtime
- **feature_service/**: GPU 特征计算、历史数据管道
- **research_service/**: ML 数据集构建、LSTM 策略
- **portfolio_service/**: 组合服务

### DOMAIN 层
- **纯交易规则与语义**，零业务层依赖
- 允许**计算基础设施**：numpy（数学计算）、pandas（数据结构）、pydantic（模型验证）— 视同标准库
- 允许 **INFRASTRUCTURE** 依赖：仅通过 DI 注入 + lazy import fallback（如 GPU 加速器）
- 包含：行为检测、事件类型、执行模型、特征定义/数学、组合模型、回放公式、风险规则、信号模型、策略配置、交易模式定义
- **不包含**：Runtime 编排、Infrastructure 实现、Data Pipeline、ML Training
- infrastructure 依赖通过 `domain.logging` 门面隔离

### INFRASTRUCTURE 层
- 无状态原语（I/O、消息、存储）
- 不持有业务状态，不做编排
- **acceleration/**: PyTorch GPU 加速
- **progress/**: 进度追踪
- **state/**: 状态管理基础设施

---

## Domain 瘦身迁移记录

### Phase 8: Domain 收敛 (2026-05-23)

**原则**: Domain 只包含"交易语义和规则"，不包含 Runtime 编排、Infrastructure 实现、Data Pipeline、ML Training。

#### → infrastructure/ (Infrastructure 泄漏)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `domain/acceleration/` | `infrastructure/acceleration/` | PyTorch GPU 加速层 |
| `domain/progress/` | `infrastructure/progress/` | 进度追踪器 |
| `domain/state/` | `infrastructure/state/` | 状态管理器 (Redis 持久化) |

#### → runtime/ (Runtime 编排泄漏)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `domain/observability.py` | `runtime/observability.py` | 运行时指标收集 |
| `domain/timeframe_coordinator.py` | `runtime/timeframe_coordinator.py` | 多周期信号协调 (有状态) |
| `domain/validation_boundary.py` | `runtime/validation_boundary.py` | Research→Runtime 隔离层 |
| `domain/trading_mode/manager.py` | `runtime/trading_mode_manager.py` | 模式状态机+Adapter 管理 |
| `domain/narrative_engine.py` | `runtime/narrative_runtime/narrative_engine.py` | AI 叙事生成 |
| `domain/portfolio_projection.py` | `runtime/portfolio_runtime/portfolio_projection.py` | 持仓持久化 (Redis+ClickHouse) |
| `domain/replay/realism_engine.py` | `runtime/replay_runtime/realism_engine.py` | 回放真实性编排 |
| `domain/replay/engine.py` | `runtime/replay_runtime/domain_engine.py` | 回放引擎入口 |
| `domain/feature/generation_service.py` | `runtime/feature_runtime/generation_service.py` | Application 层 workflow |
| `domain/feature/generation_guard.py` | `runtime/feature_runtime/generation_guard.py` | 特征生成守卫 |
| `domain/feature/realtime_materializer.py` | `runtime/feature_runtime/realtime_materializer.py` | 实时特征物化 |
| `domain/feature/time_discipline.py` | `runtime/feature_runtime/time_discipline.py` | 特征时间纪律 |
| `domain/feature/unified_calculator.py` | `runtime/feature_runtime/unified_calculator.py` | 统一特征计算器 |
| `domain/registry.py` | `application/registry.py` | 配置注册表 |

#### → services/ (Data Pipeline / ML)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `domain/feature/torch_calculator.py` | `services/feature_service/torch_calculator.py` | GPU 特征计算 |
| `domain/feature/materializer/historical_materializer.py` | `services/feature_service/historical_materializer.py` | 历史数据管道 |
| `domain/ml/lstm_dataset_builder.py` | `services/research_service/lstm_dataset_builder.py` | ML 数据集构建 |
| `domain/strategy/lstm_strategy.py` | `services/research_service/lstm_strategy.py` | LSTM 策略 (ML 混合) |
| `domain/portfolio/portfolio_service.py` | `services/portfolio_service/service.py` | 组合服务 (应用服务) |

#### Domain 保留 (纯交易规则)

| 模块 | 内容 |
|------|------|
| `behaviour/` | 市场行为检测器 (absorption, breakout, panic…) |
| `event/` | 领域事件类型定义 |
| `execution/` | 执行域模型、规则、配置 |
| `feature/` | 特征定义、纯数学计算、Feature Matrix |
| `portfolio/` | 组合域模型 (Portfolio, Position, CapitalAllocator, ExposureManager) |
| `replay/` | 回放数学公式 (slippage, fee, funding, latency, partial_fill, liquidation) |
| `risk/` | 风险规则和模型 |
| `signal/` | 信号模型、融合、生命周期 |
| `strategy/` | 策略配置定义 |
| `trading_mode/` | 交易模式定义 |
| `analysis/` | 分析类型定义 |
| `logging.py` | Domain 层日志门面 |

---

## 请求流转

### 查持仓（读）
```
API Router → APPLICATION Query → PortfolioRuntime.get_state() → 返回
```

### 下单（写）
```
API Router → APPLICATION Command → ExecutionService.execute()
                                        ↓ (DI 注入的 event_bus)
                                     RuntimeBus.publish_event()
                                        ↓
                                     ExecutionRuntime.on_event()
```

### 模式切换（系统级）
```
API Router → APPLICATION Command → RuntimeOrchestrator.switch_mode()
                                        ↓
                                     stop all → DependencyGraph → start all
```

### 启动回测（长流程）
```
API Router → APPLICATION Workflow → OptimizationService
                                        ↓
                                     ReplayRuntime (走 Orchestrator 启动)
                                        ↓
                                     StrategyAdapter → SignalRuntime
```

---

## State Ownership Matrix

| 状态 | Owner | 查询路径 |
|---|---|---|
| position | PortfolioRuntime | APPLICATION Query → PortfolioRuntime.get_state() |
| order | ExecutionRuntime | APPLICATION Query → ExecutionRuntime.get_state() |
| signal | SignalRuntime | APPLICATION Query → SignalRuntime.get_state() |
| feature | FeatureRuntime | APPLICATION Query → FeatureRuntime.get_state() |
| replay cursor | ReplayRuntime | APPLICATION Query → ReplayRuntime.get_state() |
| market/risk | RuntimeContext | APPLICATION Query → RuntimeContext.get_state() |
| correlation | CorrelationRuntime | APPLICATION Query → CorrelationRuntime.get_state() |
| projection | ProjectionRuntime | APPLICATION Query → ProjectionRuntime.get_state() |
| regime | RegimeRuntime | APPLICATION Query → RegimeRuntime.get_state() |

RuntimeStateStore 是**只读聚合视图**，通过 provider 注册表从各 Runtime 读取，不持有业务状态。

---

## Time Authority

- **runtime/ 层**: 必须用 `RuntimeClock.now_ms()`，禁止 `datetime.now()` / `datetime.utcnow()`
- **其他层**: 可以用 `datetime.now()`
- **Replay 模式**: RuntimeClock 自动返回回放时间，保证时间一致性

---

## 目录结构

```
backend/
├── api/                        # API 层 (只调 APPLICATION)
│   ├── routers/               # API 路由
│   ├── schemas/               # 请求/响应模型
│   └── services/              # API 服务层
│
├── application/                # APPLICATION 层 (Use Case)
│   ├── commands/              # 写操作 facade
│   │   ├── trading.py         # submit_order, cancel_order
│   │   ├── mode.py            # switch_mode
│   │   ├── backtest.py        # start_backtest, stop_backtest
│   │   ├── bus_commands.py    # RuntimeBus publish 封装
│   │   ├── data_commands.py   # Celery data collectors 封装
│   │   └── runtime_command_bus.py # Runtime 命令总线 (从 runtime 迁入)
│   ├── queries/               # 读操作 facade
│   │   ├── portfolio.py       # get_portfolio_state, get_positions
│   │   ├── execution.py       # get_execution_state, get_orders
│   │   ├── system.py          # get_system_status, get_runtime_info
│   │   ├── correlation.py     # get_correlation_state
│   │   ├── projection.py      # get_projection_state
│   │   ├── feature.py         # get_feature_state
│   │   ├── replay.py          # get_replay_state
│   │   └── regime.py          # get_regime_state
│   ├── optimization_service/  # 参数优化 Workflow
│   └── registry.py            # 领域配置注册表
│
├── runtime/                    # RUNTIME 层
│   ├── orchestrator/          # RuntimeOrchestrator (总控)
│   │   ├── manager.py         # RuntimeOrchestrator
│   │   ├── registry.py        # RuntimeRegistry
│   │   ├── lifecycle.py       # RuntimeLifecycle
│   │   ├── supervisor.py      # RuntimeSupervisor
│   │   ├── timeline.py        # RuntimeTimeline
│   │   └── inspector.py       # RuntimeInspector
│   ├── bus/                   # RuntimeBus (纯 transport)
│   ├── context/               # RuntimeContext
│   ├── state/                 # RuntimeStateStore (只读聚合)
│   ├── dependency/            # DependencyGraph
│   ├── lifecycle/             # StateMachine + HealthSystem
│   ├── shared/                # Runtime 共享组件
│   ├── ingestion_runtime/     # 数据采集运行时
│   ├── feature_runtime/       # 特征运行时 (含生成/守卫/物化)
│   ├── signal_runtime/        # 信号生成运行时
│   ├── execution_runtime/     # 订单执行运行时
│   ├── portfolio_runtime/     # 组合管理运行时 (含 portfolio_projection)
│   ├── projection_runtime/    # CQRS 投影运行时
│   ├── correlation_runtime/   # 相关性分析运行时
│   ├── replay_runtime/        # 回放运行时 (含 realism_engine, domain_engine)
│   ├── regime_runtime/        # 市场状态运行时
│   ├── narrative_runtime/     # 叙事运行时 (含 narrative_engine)
│   ├── feature_matrix_runtime.py # 特征矩阵存储运行时
│   ├── orderbook_runtime.py   # 订单簿运行时
│   ├── isolation/             # 模式隔离 (有状态，合法 Runtime)
│   ├── timeframe_coordinator.py # 多周期信号协调
│   ├── validation_boundary.py # Research→Runtime 隔离
│   └── trading_mode_manager.py # 模式状态机
│
├── services/                   # SERVICES 层 (单领域业务逻辑)
│   ├── data_service/          # 数据采集适配器
│   ├── aggregation_service/   # 数据聚合逻辑
│   ├── execution_service/     # 执行逻辑
│   ├── correlation_service/   # 相关性分析
│   ├── projection_service/    # 投影计算
│   ├── strategy_service/      # 策略逻辑
│   │   └── strategy_registry.py   # 策略注册中心 (从 runtime 迁入)
│   ├── backtest_service/      # 回测逻辑
│   ├── feature_service/       # 特征计算/管道
│   │   ├── torch_calculator.py    # GPU 特征计算
│   │   ├── historical_materializer.py # 历史数据管道
│   │   └── unified_calculator.py  # 统一特征计算器 (从 runtime 迁入)
│   ├── research_service/      # 研究/ML
│   │   ├── lstm_dataset_builder.py # ML 数据集构建
│   │   └── lstm_strategy.py       # LSTM 策略
│   └── portfolio_service/     # 组合服务
│       └── service.py             # 组合应用服务
│
├── domain/                     # DOMAIN 层 (纯交易规则，零外部依赖)
│   ├── behaviour/             # 市场行为检测器
│   ├── event/                 # 领域事件类型
│   ├── execution/             # 执行域 (模型/规则/配置)
│   │   ├── models/            # Order, Position, Enums
│   │   ├── intelligence/      # 滑点预测/冲击模型/流动性估计
│   │   └── quality/           # 智能执行/滑点控制/订单拆分
│   ├── feature/               # 特征定义与纯数学
│   │   ├── orderbook/         # 微结构特征 (imbalance, microprice)
│   │   ├── metadata.py        # FeatureCategory 权威定义
│   │   ├── feature_matrix/    # Feature Matrix 数据结构
│   │   └── materializer/      # schema_registry, feature_aligner, matrix_builder
│   ├── portfolio/             # 组合域 (Portfolio, Position, CapitalAllocator, ExposureManager)
│   ├── replay/                # 回放数学公式 + 数据模型
│   ├── risk/                  # 风险规则和模型
│   ├── signal/                # 信号模型、融合、生命周期
│   ├── strategy/              # 策略配置定义
│   ├── trading_mode/          # 交易模式定义
│   ├── analysis/              # 分析类型定义
│   ├── runtime_commands.py    # Runtime 命令类型定义 (从 runtime 迁入)
│   ├── logging.py             # 日志门面 (隔离 infrastructure.logging)
│
├── infrastructure/             # INFRASTRUCTURE 层 (无状态原语)
│   ├── cache/                 # Redis 缓存
│   ├── database/              # 数据库连接
│   ├── messaging/             # Kafka 消息
│   │   ├── runtime_consumer.py  # Runtime Kafka 消费者 (从 runtime 迁入)
│   │   ├── runtime_publisher.py # Runtime Kafka 发布者 (从 runtime 迁入)
│   │   ├── signal_consumer.py   # Signal Kafka 消费者 (从 runtime 迁入)
│   │   ├── signal_publisher.py  # Signal Kafka 发布者 (从 runtime 迁入)
│   │   └── event_namespace.py  # 事件命名空间 (从 runtime 迁入，mode_provider 注入)
│   ├── storage/               # 数据存储
│   ├── data_lake/             # 数据湖
│   ├── observability/         # 可观测性
│   │   └── runtime_metrics.py # 运行时指标 (从 runtime 迁入)
│   ├── replay/                # 回放数据原语 (dataclass only)
│   ├── pipeline/              # 数据管道原语
│   ├── websocket/             # WebSocket 网关
│   ├── logging/               # 日志基础设施
│   ├── acceleration/          # PyTorch GPU 加速
│   ├── progress/              # 进度追踪
│   ├── state/                 # 状态管理基础设施
│   ├── config/                # 配置管理
│   ├── runtime_clock.py       # 统一时钟
│   ├── priority_queue.py      # 优先级队列
│   ├── circuit_breaker_manager.py # 熔断器
│   ├── degradation.py         # 降级策略
│   ├── subscription_manager.py # 订阅管理
│   ├── runtime/               # re-export 兼容层
│   ├── llm/                   # LLM 客户端 (从 shared 迁入)
│   ├── http/                  # HTTP 客户端 (从 shared 迁入)
│   ├── tdp/                   # 统一数据协议 (从 shared 迁入)
│   ├── idempotency.py         # 幂等性管理 (从 shared 迁入)
│   ├── data_quality.py        # 数据质量检测 (从 shared 迁入)
│   ├── permission.py          # 权限管理 RBAC (从 shared 迁入)
│   └── startup/               # 启动配置 pydantic-settings (从 shared 迁入)
```

### Phase 9: shared 层消亡 (2026-05-23)

**原则**: shared/ 层违反六层架构的依赖方向规则（任何人都能 import shared，shared 也能 import 任何人），必须消亡。所有内容按职责分配到正确的层。

#### → domain/ (纯业务规则)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `shared/contracts/` | `domain/contracts/` | 事件类型、Candle、Exchange 等纯领域契约 |

#### → infrastructure/ (基础设施)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `shared/acceleration/` | `infrastructure/acceleration/` | PyTorch GPU 加速 |
| `shared/progress/` | `infrastructure/progress/` | 进度追踪 |
| `shared/state/` | `infrastructure/state/` | 状态管理 |
| `shared/config/` | `infrastructure/config/` | 配置管理 |
| `shared/llm_client.py` | `infrastructure/llm/client.py` | LLM 客户端 |
| `shared/http_client.py` | `infrastructure/http/client.py` | HTTP 客户端 |
| `shared/tdp/` | `infrastructure/tdp/` | 统一数据协议 |
| `shared/startup/` | `infrastructure/config/startup/` | 启动配置 |
| `shared/idempotency.py` | `infrastructure/idempotency.py` | 幂等性管理 |
| `shared/cache.py` | `infrastructure/cache/memory_cache.py` | 内存缓存 |
| `shared/data_quality.py` | `infrastructure/data_quality.py` | 数据质量检测 |
| `shared/permission.py` | `infrastructure/permission.py` | 权限管理 RBAC |
| `shared/observability.py` | `infrastructure/observability/manager.py` | 可观测性管理 |
| `shared/monitoring_api.py` | `infrastructure/observability/monitoring_api.py` | 监控 API |
| `shared/service_registry.py` | `infrastructure/observability/service_registry.py` | 服务注册 |
| `shared/utils/parquet_reader.py` | `infrastructure/storage/parquet_reader.py` | Parquet 读取 |

#### → runtime/ (运行时)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `shared/replay/` | `runtime/replay_runtime/shared_replay/` | 回放管理器、事件发射器、特征可用性守卫 |

#### → services/ (业务服务)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `shared/auto_repair.py` | `services/repair_service/auto_repair.py` | 自动修复服务 |
| `shared/backtest.py` | `services/backtest_service/signal_backtest.py` | 信号回测 |

---

## 架构演进历史

| Phase | 内容 | 日期 |
|-------|------|------|
| Phase 1-4 | 统一 WS/Redis、Subscription、隔离、Event Sourcing | 2026-05-17 |
| Phase 5 | 删除双 Kernel/Clock/State/Pipeline/Replay，Governor → Orchestrator | 2026-05-22 |
| Phase 6 | State Ownership、Time Authority、Bus 去状态化、Domain 隔离 | 2026-05-22 |
| Phase 7 | APPLICATION CQRS facade、API→Runtime 解耦、循环依赖消除 | 2026-05-22 |
| Phase 8 | Domain 瘦身：Runtime/Infrastructure/DataPipeline/ML 迁出，Domain 只保留纯交易规则 | 2026-05-23 |
| Phase 9 | shared 层消亡：全部迁移至 domain/infrastructure/runtime/services，shared/ 目录已删除 | 2026-05-23 |
| Phase 10 | API 层收敛：API 只调 APPLICATION，删除 domain re-export wrapper，Services/Infrastructure 违规加 TODO | 2026-05-23 |
| Phase 11 | Runtime 层收敛：12 个非 Runtime 文件迁出（Kafka 原语→infrastructure、事件命名空间→infrastructure(mode_provider注入)、纯计算→services、命令总线→application、数据模型→domain），1 个有状态组件保留 | 2026-05-23 |

---

### Phase 11: Runtime 层收敛 (2026-05-23)

**原则**: Runtime 准入标准 — 必须同时满足：有状态 + 有生命周期 + 是 State Owner。不满足的文件必须迁出。

#### → infrastructure/ (Infrastructure 原语)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `runtime/shared/consumer.py` | `infrastructure/messaging/runtime_consumer.py` | Kafka 消费者，I/O 原语 |
| `runtime/shared/publisher.py` | `infrastructure/messaging/runtime_publisher.py` | Kafka 发布者，I/O 原语 |
| `runtime/signal_runtime/publisher.py` | `infrastructure/messaging/signal_publisher.py` | Kafka 发布者，I/O 原语 |
| `runtime/signal_runtime/consumer.py` | `infrastructure/messaging/signal_consumer.py` | Kafka 消费者，I/O 原语 |
| `runtime/observability.py` | `infrastructure/observability/runtime_metrics.py` | 指标收集，非 State Owner |
| `runtime/event/namespace.py` | `infrastructure/messaging/event_namespace.py` | 纯格式化+缓存，mode_provider 注入解耦 |

#### → services/ (纯计算/注册表)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `runtime/strategy_registry.py` | `services/strategy_service/strategy_registry.py` | 纯注册表，无状态 |
| `runtime/feature_runtime/unified_calculator.py` | `services/feature_service/unified_calculator.py` | 纯计算，无状态 |

#### → application/ (命令编排)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `runtime/command/command_bus.py` | `application/commands/runtime_command_bus.py` | 命令编排，属于 APPLICATION 层 |

#### → domain/ (纯数据结构)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `runtime/command/runtime_commands.py` | `domain/runtime_commands.py` | 纯枚举/数据结构，零外部依赖 |
| `runtime/replay_runtime/shared_replay/models.py` | `domain/replay/models.py` | 纯数据模型，零业务逻辑 |

#### 删除

| 原位置 | 理由 |
|--------|------|
| `runtime/replay_runtime/shared_replay/verify_replay_system.py` | 验证脚本，非生产代码 |

#### 保留在 runtime/ (有状态，合法 Runtime)

| 文件 | 保留理由 |
|------|---------|
| `runtime/isolation/namespace.py` | 有状态（channels、event_handlers、isolated_state），是消息路由 State Owner |

---

*文档更新日期: 2026-05-23*
