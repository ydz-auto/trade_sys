# 系统架构文档

**更新日期**: 2026-05-24
**架构版本**: Runtime-Oriented Architecture v5.0

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Server                              │
│  FastAPI lifespan: orchestrator.start() / orchestrator.stop()   │
│  Routes: 只调 APPLICATION，不碰 Runtime/Engines/Infrastructure  │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION                              │
│                                                                 │
│  Commands (写)              Queries (读)           Workflows    │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────┐  │
│  │ TradingCommands │   │ PortfolioQueries │   │ Optimization │  │
│  │ ModeCommands    │   │ ExecutionQueries │   │   Service    │  │
│  │ BacktestCommands│   │ SystemQueries    │   │ FeatureGen   │  │
│  │ DataCommands    │   │ AnalyticsQueries │   │              │  │
│  └────────┬────────┘   └────────┬────────┘   └──────┬───────┘  │
│           │  Registry           │                    │          │
└───────────┼──────────────────────┼───────────────────┼──────────┘
            ↓                      ↓                   ↓
┌─────────────────────────────────────────────────────────────────┐
│                     RUNTIME LAYER                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              kernel/ (RuntimeOrchestrator 总控)           │   │
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
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │   │
│  │  │  Authority   │ │   Guards     │ │   Snapshot       │  │   │
│  │  │(时钟/排序/   │ │(守卫系统)   │ │(检查点/恢复)    │  │   │
│  │  │ 可用性/所有权)│ │              │ │                  │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────┘  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              kernel/event/ (RuntimeBus 纯 transport)      │   │
│  │  subscribe / publish / broadcast / route                  │   │
│  │  ⚠️ 不持有业务状态，不做业务路由                           │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  stateful/ (有状态 Runtime — State Owners)               │   │
│  │                                                          │   │
│  │  IngestionRuntime   FeatureRuntime     SignalRuntime     │   │
│  │  ExecutionRuntime   PortfolioRuntime   ReplayRuntime     │   │
│  │                                                          │   │
│  │  每个 Runtime 是自己领域的 State Owner:                   │   │
│  │    position → PortfolioRuntime                           │   │
│  │    order    → ExecutionRuntime                           │   │
│  │    signal   → SignalRuntime                              │   │
│  │    feature  → FeatureRuntime                             │   │
│  │    replay   → ReplayRuntime                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  analytical/ (分析型 Runtime — 只读/投影)                │   │
│  │                                                          │   │
│  │  CorrelationRuntime   ProjectionRuntime                  │   │
│  │  RegimeRuntime        NarrativeRuntime                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  contracts/ (运行时契约)                                 │   │
│  │    canonical_event.py   event_adapter.py                 │   │
│  │    event_factory.py     runtime_protocol.py              │   │
│  │    validation_boundary.py                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  pipeline/ (数据管道)     replay/ (回放工具)              │   │
│  │  jobs/ (Celery 任务)      verification/ (验证工具)        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                        ENGINES                                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  adapters/ (外部适配器)                                  │   │
│  │    data/collectors/   数据采集器 (Binance WS, 新闻, ETF) │   │
│  │    data/feeds/        数据源适配器 (Odaily, QQ, Twitter) │   │
│  │    data/sources/      实时数据源 (QQ, Telegram)          │   │
│  │    exchange/          交易所适配器 (Binance, OKX, Mock)  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  compute/ (业务计算引擎)                                 │   │
│  │    aggregation/       数据聚合 (K线聚合)                 │   │
│  │    correlation/       相关性分析                         │   │
│  │    feature/           特征计算 (GPU, 统一计算器)         │   │
│  │    models/            数据模型 (Candle, OrderBook, Trade)│   │
│  │    risk/              风险计算引擎 (9个检查器)           │   │
│  │    signal/            信号生成 (融合引擎, 评分器)        │   │
│  │    strategy/          策略管理 (注册/发现/符号)          │   │
│  │    scoring/           LLM 评分                           │   │
│  │    schemas/           信号 Schema                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ml/ (机器学习)                                          │   │
│  │    lstm_compute.py        LSTM 计算                      │   │
│  │    lstm_dataset_builder.py ML 数据集构建                 │   │
│  │    lstm_strategy.py       LSTM 策略                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⚠️ 不 import Runtime，通过 DI 接收 Bus/回调                    │
│  ⚠️ 不 import Application                                       │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌──────────────────────┐  ┌───────────────────────────────────────┐
│       DOMAIN         │  │          INFRASTRUCTURE                │
│                      │  │                                       │
│  纯交易规则与语义    │  │  无状态原语                            │
│  零业务层依赖        │  │  persistence/  (缓存/DB/快照/状态)    │
│  计算基础设施:       │  │  messaging/   (Kafka/WS/Schema)       │
│  numpy/pandas/pydant │  │  security/    (API网关/Webhook/RBAC)  │
│  behaviour/          │  │  storage/     (数据湖/Parquet/PIT)    │
│  event/              │  │  observability/(指标/追踪/遥测)       │
│  execution/          │  │  monitoring/  (告警/健康/仪表盘)      │
│  feature/            │  │  config/      (配置管理/版本控制)     │
│  portfolio/          │  │  logging/     (日志基础设施)          │
│  risk/               │  │  metrics/     (Prometheus)            │
│  signal/             │  │  utilities/   (弹性/降级/HTTP/LLM)    │
│  strategy/           │  │  acceleration/(GPU加速)               │
│  trading_mode/       │  │                                       │
│  analysis/           │  │  → DOMAIN (仅类型/枚举)               │
│  contracts/          │  │                                       │
└──────────────────────┘  └───────────────────────────────────────┘
```

---

## 依赖方向规则

```
API ──→ APPLICATION ──┬──→ RUNTIME (Orchestrator + 各 Runtime)
                      ├──→ ENGINES
                      ├──→ DOMAIN
                      └──→ INFRASTRUCTURE

RUNTIME ──→ DOMAIN
RUNTIME ──→ INFRASTRUCTURE
RUNTIME ──→ ENGINES (⚠️ 通过 DI 注入，不 import)

ENGINES ──→ DOMAIN
ENGINES ──→ INFRASTRUCTURE
ENGINES ──✗ RUNTIME     (禁止)
ENGINES ──✗ APPLICATION (禁止)

INFRASTRUCTURE ──→ DOMAIN (仅类型/枚举)
INFRASTRUCTURE ──✗ RUNTIME / ENGINES / APPLICATION (禁止)

DOMAIN ──✗ 任何其他业务层 (零业务层依赖)
DOMAIN ──→ 计算基础设施 (numpy, pandas, pydantic) — 视同标准库
DOMAIN ──→ INFRASTRUCTURE (仅通过 DI 注入 + lazy import fallback)
```

### 依赖规则速查表

| 层 | 可依赖 | 不可依赖 |
|---|---|---|
| **API** | APPLICATION | RUNTIME, ENGINES, INFRA, DOMAIN |
| **APPLICATION** | ENGINES, RUNTIME, DOMAIN, INFRA | — |
| **RUNTIME** | DOMAIN, INFRA, ENGINES(通过DI) | API, APPLICATION |
| **ENGINES** | DOMAIN, INFRA | RUNTIME, API, APPLICATION |
| **DOMAIN** | 标准库 + 计算基础设施(numpy/pandas/pydantic) | API, RUNTIME, ENGINES, APPLICATION |
| **INFRASTRUCTURE** | DOMAIN(仅类型/枚举) | RUNTIME, ENGINES, API, APPLICATION |

---

## 各层职责

### API 层
- HTTP 路由、请求校验、序列化
- WebSocket 端点
- **只调 APPLICATION**，不直接碰 Runtime/Engines/Infrastructure

### APPLICATION 层
- **Commands**: 写操作，编排跨 Engine/Runtime 的写流程
- **Queries**: 读操作，聚合多个 Runtime 的状态给 API 用
- **Workflows**: 长流程，跨多步骤的用例（如 OptimizationService、FeatureGeneration）
- **Registry**: 领域配置注册表

### RUNTIME 层
- **kernel/**: RuntimeOrchestrator（系统级生命周期管理）、RuntimeBus（纯 transport）、Authority（时钟/排序/可用性/所有权）、Guards（守卫系统）、Snapshot（检查点/恢复）
- **stateful/**: 有状态 Runtime，每个是自己领域的 State Owner
- **analytical/**: 分析型 Runtime（只读/投影），如 CorrelationRuntime、ProjectionRuntime、RegimeRuntime、NarrativeRuntime
- **contracts/**: 运行时契约（事件适配、验证边界、协议定义）
- **pipeline/**: 数据管道（ReadHub、实时推送、统一管道）
- **replay/**: 回放工具（确定性回放、时间旅行、策略回退）
- **verification/**: 验证工具（一致性、确定性、回放-实盘对比）
- **jobs/**: Celery 异步任务

### ENGINES 层
- **adapters/**: 外部系统适配器
  - `data/collectors/`: 数据采集器（Binance WebSocket、新闻、ETF、宏观、社交媒体）
  - `data/feeds/`: 数据源适配器（Odaily、QQ、Twitter、CryptoPanic、WhaleAlert）
  - `data/sources/`: 实时数据源（QQ、Telegram）
  - `exchange/`: 交易所适配器（Binance、Binance Futures、OKX、Mock、Paper Trading）
- **compute/**: 业务计算引擎
  - `aggregation/`: K线聚合
  - `correlation/`: 相关性分析
  - `feature/`: 特征计算（GPU 加速、统一计算器、历史物化器）
  - `models/`: 数据模型（Candle、OrderBook、Trade）
  - `risk/`: 风险计算引擎（9个检查器：黑名单、冷却、日损失、回撤、杠杆、订单大小、仓位、止损）
  - `signal/`: 信号生成（融合引擎、缓冲区、评分器）
  - `strategy/`: 策略管理（注册、发现、符号注册）
  - `scoring/`: LLM 评分
- **ml/**: 机器学习（LSTM 计算、数据集构建、策略）
- 通过 DI 接收 Bus/回调，不 import Runtime

### DOMAIN 层
- **纯交易规则与语义**，零业务层依赖
- 允许**计算基础设施**：numpy（数学计算）、pandas（数据结构）、pydantic（模型验证）— 视同标准库
- 允许 **INFRASTRUCTURE** 依赖：仅通过 DI 注入 + lazy import fallback（如 GPU 加速器）
- 包含：行为检测、事件类型、执行模型、特征定义/数学、组合模型、风险规则、信号模型、策略配置、交易模式定义、分析类型、领域契约
- **不包含**：Runtime 编排、Infrastructure 实现、Data Pipeline、ML Training
- infrastructure 依赖通过 `domain.logging` 门面隔离

### INFRASTRUCTURE 层
- 无状态原语（I/O、消息、存储）
- 不持有业务状态，不做编排
- **persistence/**: 持久化（缓存管理、数据库连接池、快照、状态管理）
- **messaging/**: 消息传递（Kafka 消费者/发布者、WebSocket 网关、Schema 注册、聚合发布器）
- **security/**: 安全（API 网关中间件、Webhook 接收器、RBAC 权限）
- **storage/**: 存储（数据湖、Parquet 读取、PIT Store、特征矩阵存储、数据质量）
- **observability/**: 可观测性（事件丢失检测、延迟监控、服务注册、遥测、追踪）
- **monitoring/**: 监控（告警通道、健康检查、仪表盘）
- **config/**: 配置管理（业务/基础设施默认值、域配置、启动设置、版本控制）
- **logging/**: 日志基础设施（格式化、处理器、敏感过滤）
- **metrics/**: Prometheus 指标
- **utilities/**: 工具（弹性/重试/降级、HTTP 客户端、LLM 客户端、优先级队列、进度追踪、运行时时钟、调度器、时间权威）

---

## 请求流转

### 查持仓（读）
```
API Router → APPLICATION Query → PortfolioRuntime.get_state() → 返回
```

### 下单（写）
```
API Router → APPLICATION Command → Engines.compute.risk + ExecutionRuntime
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
│   ├── routers/               # API 路由 (22 个路由模块)
│   │   ├── alpha.py           # Alpha 生命周期
│   │   ├── backtest.py        # 回测
│   │   ├── config.py          # 配置
│   │   ├── correlation.py     # 相关性
│   │   ├── dashboard_v2.py    # 仪表盘 V2
│   │   ├── data.py            # 数据管理
│   │   ├── execution.py       # 执行
│   │   ├── factors.py         # 因子
│   │   ├── feature.py         # 特征
│   │   ├── feature_generation.py # 特征生成
│   │   ├── feature_matrix.py  # 特征矩阵
│   │   ├── health.py          # 健康检查
│   │   ├── optimization.py    # 参数优化
│   │   ├── prices.py          # 价格
│   │   ├── projection.py      # 投影
│   │   ├── refresh.py         # 刷新
│   │   ├── replay.py          # 回放
│   │   ├── strategy.py        # 策略
│   │   ├── trading.py         # 交易
│   │   ├── trading_mode.py    # 交易模式
│   │   └── websocket.py       # WebSocket
│   └── schemas/               # 请求/响应模型
│
├── application/                # APPLICATION 层 (Use Case)
│   ├── commands/              # 写操作 facade
│   │   ├── trading.py         # submit_order, cancel_order
│   │   ├── mode.py            # switch_mode
│   │   ├── backtest.py        # start_backtest, stop_backtest
│   │   ├── bus_commands.py    # RuntimeBus publish 封装
│   │   ├── data_commands.py   # Celery data collectors 封装
│   │   └── runtime_command_bus.py # Runtime 命令总线
│   ├── queries/               # 读操作 facade
│   │   ├── portfolio.py       # 组合状态查询
│   │   ├── execution.py       # 执行状态查询
│   │   ├── system.py          # 系统状态查询
│   │   ├── correlation.py     # 相关性查询
│   │   ├── projection.py      # 投影查询
│   │   ├── feature.py         # 特征查询
│   │   ├── replay.py          # 回放查询
│   │   ├── regime.py          # 市场状态查询
│   │   ├── strategy.py        # 策略查询
│   │   ├── analytics_queries.py # 分析查询
│   │   ├── config_queries.py  # 配置查询
│   │   ├── domain_queries.py  # 领域查询
│   │   ├── infrastructure_queries.py # 基础设施查询
│   │   └── service_queries.py # 服务查询
│   ├── optimization_service/  # 参数优化 Workflow
│   │   ├── engine.py          # 优化引擎
│   │   ├── service.py         # 优化服务
│   │   ├── models.py          # 优化模型
│   │   ├── metrics_collector.py # 指标收集
│   │   └── strategy_adapter.py # 策略适配器
│   ├── workflows/             # 长流程 Workflow
│   │   └── feature_generation.py # 特征生成工作流
│   └── registry.py            # 领域配置注册表
│
├── runtime/                    # RUNTIME 层
│   ├── kernel/                 # 运行时内核 (总控)
│   │   ├── orchestrator/      # RuntimeOrchestrator
│   │   │   ├── manager.py     # RuntimeOrchestrator
│   │   │   ├── registry.py    # RuntimeRegistry
│   │   │   ├── lifecycle.py   # RuntimeLifecycle
│   │   │   ├── supervisor.py  # RuntimeSupervisor
│   │   │   ├── timeline.py    # RuntimeTimeline
│   │   │   ├── inspector.py   # RuntimeInspector
│   │   │   └── dependency_graph.py # 依赖图
│   │   ├── authority/         # 权威系统
│   │   │   ├── authority_system.py # 权威系统
│   │   │   ├── clock_authority.py  # 时钟权威
│   │   │   ├── ordering_authority.py # 排序权威
│   │   │   ├── availability_authority.py # 可用性权威
│   │   │   └── ownership_registry.py # 所有权注册
│   │   ├── context/           # 运行时上下文
│   │   │   ├── runtime_context.py # RuntimeContext
│   │   │   └── session.py     # 会话管理
│   │   ├── event/             # 事件总线
│   │   │   ├── runtime_bus.py # RuntimeBus (纯 transport)
│   │   │   └── router.py      # 事件路由
│   │   ├── guards/            # 守卫系统
│   │   │   ├── guard_system.py # 守卫系统
│   │   │   ├── base_guard.py  # 基础守卫
│   │   │   ├── clock_guard.py # 时钟守卫
│   │   │   ├── duplicate_guard.py # 去重守卫
│   │   │   ├── ordering_guard.py # 排序守卫
│   │   │   ├── availability_guard.py # 可用性守卫
│   │   │   ├── mutation_guard.py # 变异守卫
│   │   │   ├── import_guard.py # 导入守卫
│   │   │   ├── partial_candle_guard.py # 部分 K 线守卫
│   │   │   └── failure_injector.py # 故障注入
│   │   ├── lifecycle/         # 生命周期
│   │   │   ├── state_machine.py # 状态机
│   │   │   └── runtime_health.py # 运行时健康
│   │   ├── namespace/         # 模式隔离 (有状态，合法 Runtime)
│   │   │   └── namespace.py   # 命名空间隔离
│   │   ├── replay/            # 回放内核
│   │   │   ├── replay_engine.py # 回放引擎
│   │   │   ├── event_log.py   # 事件日志
│   │   │   ├── state_capture.py # 状态捕获
│   │   │   └── validator.py   # 回放验证
│   │   ├── shared/            # 运行时共享组件
│   │   │   ├── healthcheck.py # 健康检查
│   │   │   ├── lifecycle.py   # 生命周期
│   │   │   └── metrics.py     # 指标
│   │   ├── snapshot/          # 检查点/恢复
│   │   │   ├── checkpoint.py  # 检查点
│   │   │   ├── recovery_manager.py # 恢复管理
│   │   │   ├── recovery_coordinator.py # 恢复协调
│   │   │   └── state_hash.py  # 状态哈希
│   │   ├── state/             # 运行时状态
│   │   │   ├── runtime_state.py # 运行时状态
│   │   │   └── store.py       # 状态存储 (只读聚合)
│   │   ├── base.py            # Runtime 基类
│   │   ├── core.py            # 核心运行时
│   │   └── trading_mode_manager.py # 模式状态机
│   │
│   ├── stateful/              # 有状态 Runtime (State Owners)
│   │   ├── ingestion_runtime/ # 数据采集运行时
│   │   │   ├── runtime.py     # 主运行时
│   │   │   ├── source_manager.py # 数据源管理
│   │   │   ├── orderbook_runtime.py # 订单簿运行时
│   │   │   ├── consumers/     # Kafka 消费者
│   │   │   │   ├── raw_data_consumer.py # 原始数据
│   │   │   │   └── odaily_consumer.py # Odaily 新闻
│   │   │   └── __main__.py    # 入口
│   │   ├── feature_runtime/   # 特征运行时
│   │   │   ├── feature_matrix_runtime.py # 特征矩阵
│   │   │   ├── generation_guard.py # 特征可用性守卫
│   │   │   ├── realtime_materializer.py # 实时特征物化
│   │   │   ├── time_discipline.py # 特征时间纪律
│   │   │   └── __main__.py    # 入口
│   │   ├── signal_runtime/    # 信号生成运行时
│   │   │   ├── runtime.py     # 主运行时
│   │   │   ├── lifecycle.py   # 信号生命周期
│   │   │   ├── metrics.py     # 信号指标
│   │   │   ├── timeframe_coordinator.py # 多周期协调
│   │   │   └── __main__.py    # 入口
│   │   ├── execution_runtime/ # 订单执行运行时
│   │   │   ├── runtime.py     # 主运行时
│   │   │   ├── fill_sync.py   # 成交同步
│   │   │   ├── consumers/     # Kafka 消费者
│   │   │   │   └── signal_consumer.py # 信号消费
│   │   │   ├── engine/        # 执行引擎
│   │   │   │   ├── execution_engine.py # 执行引擎
│   │   │   │   ├── order_manager.py # 订单管理
│   │   │   │   └── position_manager.py # 仓位管理
│   │   │   ├── publishers/    # Kafka 发布者
│   │   │   │   └── order_publisher.py # 订单发布
│   │   │   ├── state_machine/ # 执行状态机
│   │   │   │   ├── execution_engine.py # 执行引擎状态机
│   │   │   │   ├── order_state_machine.py # 订单状态机
│   │   │   │   └── reconciliation.py # 对账
│   │   │   ├── storage/       # 执行存储
│   │   │   │   ├── order_repository.py # 订单仓库
│   │   │   │   ├── position_repository.py # 仓位仓库
│   │   │   │   ├── orm_order_repository.py # ORM 订单仓库
│   │   │   │   ├── orm_position_repository.py # ORM 仓位仓库
│   │   │   │   ├── postgres_fill_repository.py # PostgreSQL 成交仓库
│   │   │   │   ├── postgres_order_repository.py # PostgreSQL 订单仓库
│   │   │   │   └── postgres_position_repository.py # PostgreSQL 仓位仓库
│   │   │   └── __main__.py    # 入口
│   │   ├── portfolio_runtime/ # 组合管理运行时
│   │   │   ├── portfolio_projection.py # 持仓投影
│   │   │   ├── consumers/     # Kafka 消费者
│   │   │   │   └── order_filled_consumer.py # 成交消费
│   │   │   └── __main__.py    # 入口
│   │   └── replay_runtime/    # 回放运行时
│   │       ├── runtime.py     # 主运行时
│   │       ├── domain_engine.py # 回放引擎入口
│   │       ├── realism_engine.py # 回放真实性引擎
│   │       ├── backtest_engine.py # 回测引擎
│   │       ├── journal_replayer.py # 日志回放
│   │       ├── models/        # 回放数据模型
│   │       │   ├── models.py  # 通用模型
│   │       │   ├── fee_model.py # 手续费模型
│   │       │   ├── funding.py # 资金费率
│   │       │   ├── latency.py # 延迟模型
│   │       │   ├── liquidation.py # 清算模型
│   │       │   ├── partial_fill.py # 部分成交
│   │       │   ├── slippage.py # 滑点模型
│   │       │   └── repair_models/ # 修复模型
│   │       ├── shared_replay/ # 共享回放组件
│   │       │   ├── event_store.py # 事件存储
│   │       │   ├── feature_availability_guard.py # 特征可用性守卫
│   │       │   ├── market_event_emitter.py # 市场事件发射
│   │       │   ├── orchestrator.py # 回放编排
│   │       │   ├── rebuild_manager.py # 重建管理
│   │       │   └── replay_manager.py # 回放管理
│   │       ├── detectors/     # 回放检测器
│   │       │   └── gap_detector.py # 缺口检测
│   │       ├── historical/    # 历史回放
│   │       │   ├── historical_feature_extractor.py # 历史特征提取
│   │       │   └── replay_runner.py # 回放运行器
│   │       └── __main__.py    # 入口
│   │
│   ├── analytical/            # 分析型 Runtime (只读/投影)
│   │   ├── correlation_runtime/ # 相关性分析运行时
│   │   │   ├── runtime.py     # 主运行时
│   │   │   └── __main__.py    # 入口
│   │   ├── projection_runtime/ # CQRS 投影运行时
│   │   │   ├── runtime.py     # 主运行时
│   │   │   ├── state_keys.py  # 状态键定义
│   │   │   ├── projections/   # 投影实现
│   │   │   │   ├── base.py    # 投影基类
│   │   │   │   ├── dashboard_projection.py # 仪表盘投影
│   │   │   │   ├── decision_projection.py # 决策投影
│   │   │   │   ├── event_timeline_projection.py # 事件时间线投影
│   │   │   │   ├── position_projection.py # 仓位投影
│   │   │   │   └── risk_projection.py # 风险投影
│   │   │   └── __main__.py    # 入口
│   │   ├── regime_runtime/    # 市场状态运行时
│   │   │   └── __main__.py    # 入口
│   │   └── narrative_runtime/ # 叙事运行时
│   │       ├── runtime.py     # 主运行时
│   │       ├── narrative_engine.py # AI 叙事引擎
│   │       └── __main__.py    # 入口
│   │
│   ├── contracts/             # 运行时契约
│   │   ├── canonical_event.py # 规范事件
│   │   ├── event_adapter.py   # 事件适配器
│   │   ├── event_factory.py   # 事件工厂
│   │   ├── runtime_protocol.py # 运行时协议
│   │   └── validation_boundary.py # Research→Runtime 隔离
│   │
│   ├── pipeline/              # 数据管道
│   │   ├── unified_pipeline.py # 统一管道
│   │   ├── readhub_pipeline.py # ReadHub 管道
│   │   ├── realtime_push.py   # 实时推送
│   │   └── scheduler.py       # 调度器
│   │
│   ├── replay/                # 回放工具
│   │   ├── deterministic.py   # 确定性回放
│   │   ├── engine.py          # 回放引擎
│   │   ├── pipeline_replay.py # 管道回放
│   │   ├── strategy_rewind.py # 策略回退
│   │   └── time_travel.py     # 时间旅行
│   │
│   ├── verification/          # 验证工具
│   │   ├── consistency.py     # 一致性验证
│   │   ├── determinism.py     # 确定性验证
│   │   └── replay_live_verifier.py # 回放-实盘对比
│   │
│   └── jobs/                  # Celery 异步任务
│       └── celery_tasks.py    # 任务定义
│
├── engines/                    # ENGINES 层 (业务计算引擎 + 外部适配器)
│   ├── adapters/              # 外部系统适配器
│   │   ├── data/              # 数据适配器
│   │   │   ├── collectors/    # 数据采集器
│   │   │   │   ├── base_collector.py       # 采集器基类
│   │   │   │   ├── binance_websocket.py    # Binance WebSocket
│   │   │   │   ├── exchange_collector.py   # 交易所采集
│   │   │   │   ├── etf_collector.py        # ETF 采集
│   │   │   │   ├── macro_collector.py      # 宏观数据采集
│   │   │   │   ├── news_collector.py       # 新闻采集
│   │   │   │   ├── news_hub.py             # 新闻中心
│   │   │   │   ├── social_media_collector.py # 社交媒体采集
│   │   │   │   ├── twitter_collector.py    # Twitter 采集
│   │   │   │   ├── telegram_adapter.py     # Telegram 适配
│   │   │   │   ├── llm_scraper.py          # LLM 爬虫
│   │   │   │   ├── multi_source.py         # 多源采集
│   │   │   │   └── ...                     # 其他采集器
│   │   │   ├── feeds/         # 数据源适配器
│   │   │   │   ├── base.py                # 适配器基类
│   │   │   │   ├── odaily_adapter.py      # Odaily
│   │   │   │   ├── qq_adapter.py          # QQ
│   │   │   │   ├── twitter_adapter.py     # Twitter
│   │   │   │   ├── cryptopanic_adapter.py # CryptoPanic
│   │   │   │   ├── skill_adapter.py       # Skill
│   │   │   │   └── whale_alert_adapter.py # WhaleAlert
│   │   │   └── sources/       # 实时数据源
│   │   │       ├── base.py                # 数据源基类
│   │   │       ├── qq_realtime.py         # QQ 实时
│   │   │       └── telegram_realtime.py   # Telegram 实时
│   │   ├── exchange/          # 交易所适配器
│   │   │   ├── base_adapter.py           # 适配器基类
│   │   │   ├── binance_adapter.py        # Binance 现货
│   │   │   ├── binance_futures_adapter.py # Binance 合约
│   │   │   ├── okx_adapter.py            # OKX
│   │   │   ├── mock_adapter.py           # Mock
│   │   │   ├── paper_trading_adapter.py  # Paper Trading
│   │   │   └── multi_exchange.py         # 多交易所
│   │   └── contracts.py       # 适配器契约
│   │
│   ├── compute/               # 业务计算引擎
│   │   ├── aggregation/       # K线聚合
│   │   │   ├── aggregator.py  # 聚合器
│   │   │   └── compute.py     # 聚合计算
│   │   ├── correlation/       # 相关性分析
│   │   │   ├── compute.py     # 相关性计算
│   │   │   └── service/       # 相关性服务
│   │   │       └── strategy_adapter.py # 策略适配器
│   │   ├── feature/           # 特征计算
│   │   │   ├── feature_matrix.py       # 特征矩阵
│   │   │   ├── torch_calculator.py     # GPU 特征计算
│   │   │   ├── unified_calculator.py   # 统一特征计算器
│   │   │   └── historical_materializer.py # 历史数据物化
│   │   ├── models/            # 数据模型
│   │   │   ├── candle_model.py         # K线模型
│   │   │   ├── orderbook_model.py      # 订单簿模型
│   │   │   └── trade_model.py          # 交易模型
│   │   ├── risk/              # 风险计算引擎
│   │   │   ├── engine.py      # 风险引擎
│   │   │   ├── compute.py     # 风险计算
│   │   │   └── checkers/      # 风险检查器
│   │   │       ├── blacklist.py    # 黑名单
│   │   │       ├── cooldown.py     # 冷却期
│   │   │       ├── daily_loss.py   # 日损失
│   │   │       ├── drawdown.py     # 回撤
│   │   │       ├── leverage.py     # 杠杆
│   │   │       ├── order_size.py   # 订单大小
│   │   │       ├── position.py     # 仓位
│   │   │       └── stop_loss.py    # 止损
│   │   ├── signal/            # 信号生成
│   │   │   ├── fusion_engine.py      # 信号融合引擎
│   │   │   ├── fusion_handlers.py    # 融合处理器
│   │   │   ├── buffer.py             # 信号缓冲
│   │   │   └── scorer.py             # 信号评分
│   │   ├── strategy/          # 策略管理
│   │   │   ├── registry.py    # 策略注册
│   │   │   ├── discovery.py   # 策略发现
│   │   │   ├── strategies.py  # 策略实现
│   │   │   └── symbol_registry.py # 符号注册
│   │   ├── scoring/           # LLM 评分
│   │   │   └── llm_scorer.py  # LLM 评分器
│   │   └── schemas/           # 信号 Schema
│   │       └── signal_schema.py # 信号 Schema
│   │
│   └── ml/                    # 机器学习
│       ├── lstm_compute.py    # LSTM 计算
│       ├── lstm_dataset_builder.py # ML 数据集构建
│       └── lstm_strategy.py   # LSTM 策略
│
├── domain/                     # DOMAIN 层 (纯交易规则，零外部依赖)
│   ├── analysis/              # 分析类型定义
│   │   ├── types.py           # 分析类型
│   │   ├── correlation/       # 相关性定义
│   │   └── tdp/               # TDP 协议 (客户端/格式化/类型/验证)
│   ├── contracts/             # 领域契约
│   ├── event/                 # 领域事件类型
│   │   ├── base_event.py      # 事件基类
│   │   ├── direction.py       # 方向枚举
│   │   ├── event_category.py  # 事件分类
│   │   ├── event_type.py      # 事件类型
│   │   ├── mapping.py         # 事件映射
│   │   ├── market_event.py    # 市场事件
│   │   ├── signal_event.py    # 信号事件
│   │   ├── protocol.py        # 事件协议
│   │   └── infrastructure/    # 事件基础设施
│   │       ├── event_ordering.py # 事件排序
│   │       ├── event_time.py  # 事件时间
│   │       ├── unified_schema.py # 统一 Schema
│   │       ├── unified_event_processor.py # 统一事件处理器
│   │       └── cross_symbol_semantics.py # 跨符号语义
│   ├── execution/             # 执行域 (模型/规则/配置)
│   │   ├── models/            # Order, Position, Enums, Events
│   │   ├── schemas/           # 审计/集合/数据湖/执行/系统/时序/交易/用户
│   │   ├── config.py          # 执行配置
│   │   ├── constraints.py     # 执行约束
│   │   ├── fee_model.py       # 手续费模型
│   │   ├── order_rules.py     # 订单规则
│   │   ├── position_reader.py # 仓位读取
│   │   ├── slippage.py        # 滑点模型
│   │   ├── trading_mode.py    # 交易模式
│   │   └── utils.py           # 工具函数
│   ├── feature/               # 特征定义与纯数学
│   │   ├── feature_matrix/    # Feature Matrix 数据结构
│   │   ├── indicators/        # 市场行为指标
│   │   │   ├── absorption.py  # 吸收
│   │   │   ├── breakout.py    # 突破
│   │   │   ├── detector.py    # 检测器
│   │   │   ├── liquidation_cascade.py # 清算级联
│   │   │   ├── mean_reversion.py # 均值回归
│   │   │   ├── panic.py       # 恐慌
│   │   │   └── trend_exhaustion.py # 趋势耗尽
│   │   ├── infrastructure/    # 特征基础设施
│   │   │   ├── feature_lineage.py # 特征血缘
│   │   │   ├── partial_candle_handler.py # 部分 K 线处理
│   │   │   └── warmup_determinism.py # 预热确定性
│   │   ├── liquidation/       # 清算特征
│   │   ├── microstructure/    # 微结构特征
│   │   ├── orderbook/         # 订单簿微结构特征
│   │   │   ├── analyzer.py    # 分析器
│   │   │   ├── depth_pressure.py # 深度压力
│   │   │   ├── imbalance.py   # 不平衡
│   │   │   ├── liquidity_shift.py # 流动性偏移
│   │   │   ├── microprice.py  # 微价格
│   │   │   ├── spoof_detection.py # 虚假检测
│   │   │   ├── sweep_detection.py # 扫荡检测
│   │   │   └── wall_detection.py # 墙检测
│   │   ├── oi/                # OI/资金费率相关性
│   │   ├── trade/             # 交易特征
│   │   ├── materializer/      # schema_registry, feature_aligner, matrix_builder
│   │   ├── availability.py    # 特征可用性
│   │   ├── label_isolation.py # 标签隔离
│   │   └── metadata.py        # FeatureCategory 权威定义
│   ├── portfolio/             # 组合域 (Exposure, Leverage, PnL)
│   ├── risk/                  # 风险规则和模型
│   │   ├── infrastructure/    # 风险基础设施
│   │   ├── exposure.py        # 暴露度
│   │   ├── limit_manager.py   # 限额管理
│   │   ├── market_risk.py     # 市场风险
│   │   ├── portfolio_risk.py  # 组合风险
│   │   ├── position_risk.py   # 仓位风险
│   │   └── risk_monitor.py    # 风险监控
│   ├── signal/                # 信号模型、融合、生命周期、注册
│   ├── strategy/              # 策略配置定义
│   │   ├── models/strategy_params.py # 策略参数
│   │   └── symbol_config.py   # 符号配置
│   ├── trading_mode/          # 交易模式定义
│   └── logging.py             # 日志门面 (隔离 infrastructure.logging)
│
├── infrastructure/             # INFRASTRUCTURE 层 (无状态原语)
│   ├── persistence/           # 持久化
│   │   ├── cache/             # 缓存管理
│   │   │   ├── cache_manager.py  # 缓存管理器
│   │   │   ├── circuit_breaker.py # 熔断器
│   │   │   ├── config.py      # 缓存配置
│   │   │   ├── keys.py        # 缓存键
│   │   │   ├── memory_cache.py # 内存缓存
│   │   │   └── redis_client.py # Redis 客户端
│   │   ├── database/          # 数据库
│   │   │   ├── clickhouse.py  # ClickHouse
│   │   │   ├── postgresql.py  # PostgreSQL
│   │   │   ├── connection_pool.py # 连接池
│   │   │   ├── data_lake.py   # 数据湖
│   │   │   ├── session.py     # 会话管理
│   │   │   ├── sqlalchemy_base.py # SQLAlchemy 基类
│   │   │   ├── configs.py     # 数据库配置
│   │   │   └── enums.py       # 数据库枚举
│   │   ├── snapshot/          # 快照管理
│   │   │   └── manager.py     # 快照管理器
│   │   ├── state/             # 状态管理
│   │   │   ├── manager.py     # 状态管理器
│   │   │   ├── strategy_param_repository.py # 策略参数仓库
│   │   │   ├── strategy_param_store.py # 策略参数存储
│   │   │   └── types.py       # 状态类型
│   │   └── idempotency.py     # 幂等性管理
│   ├── messaging/             # 消息传递
│   │   ├── aggregation_publisher/ # 聚合发布器
│   │   │   ├── clickhouse_writer.py # ClickHouse 写入
│   │   │   ├── kafka_publisher.py # Kafka 发布
│   │   │   └── parquet_writer.py # Parquet 写入
│   │   ├── schema/            # 消息 Schema
│   │   │   ├── base.py        # Schema 基类
│   │   │   ├── base_event.py  # 事件基类
│   │   │   ├── canonical.py   # 规范事件
│   │   │   ├── decision.py    # 决策事件
│   │   │   ├── event.py       # 事件
│   │   │   ├── raw_data.py    # 原始数据
│   │   │   └── signal.py      # 信号事件
│   │   ├── websocket/         # WebSocket 网关
│   │   │   ├── gateway.py     # 网关
│   │   │   ├── manager.py     # 连接管理
│   │   │   └── server.py      # 服务器
│   │   ├── broker.py          # 消息代理
│   │   ├── consumer.py        # 消费者
│   │   ├── event_journal.py   # 事件日志
│   │   ├── event_namespace.py # 事件命名空间
│   │   ├── event_registry.py  # 事件注册
│   │   ├── kafka_broker.py    # Kafka 代理
│   │   ├── kafka_config.py    # Kafka 配置
│   │   ├── kafka_producer.py  # Kafka 生产者
│   │   ├── runtime_consumer.py # Runtime Kafka 消费者
│   │   ├── runtime_publisher.py # Runtime Kafka 发布者
│   │   ├── schema_registry.py # Schema 注册
│   │   ├── serializer.py      # 序列化
│   │   ├── signal_consumer.py # Signal Kafka 消费者
│   │   ├── signal_publisher.py # Signal Kafka 发布者
│   │   ├── subscription_manager.py # 订阅管理
│   │   └── topics.py          # Kafka Topic 定义
│   ├── security/              # 安全
│   │   ├── api_gateway/       # API 网关
│   │   │   ├── config.py      # 网关配置
│   │   │   ├── exceptions.py  # 网关异常
│   │   │   ├── middleware.py  # 网关中间件
│   │   │   ├── response.py    # 网关响应
│   │   │   ├── router.py      # 网关路由
│   │   │   └── security.py    # 网关安全
│   │   ├── webhook/           # Webhook
│   │   │   └── receiver.py    # Webhook 接收器
│   │   └── permission.py      # RBAC 权限管理
│   ├── storage/               # 存储
│   │   ├── data_lake/         # 数据湖
│   │   │   ├── layer.py       # 数据层
│   │   │   ├── manager.py     # 数据湖管理
│   │   │   ├── path_utils.py  # 路径工具
│   │   │   └── schemas.py     # 数据湖 Schema
│   │   ├── data_quality.py    # 数据质量检测
│   │   ├── feature_matrix_storage.py # 特征矩阵存储
│   │   ├── immutable_snapshot.py # 不可变快照
│   │   ├── parquet_reader.py  # Parquet 读取
│   │   └── point_in_time_store.py # PIT Store
│   ├── observability/         # 可观测性
│   │   ├── event_loss.py      # 事件丢失检测
│   │   ├── lag_monitor.py     # 延迟监控
│   │   ├── manager.py         # 可观测性管理
│   │   ├── service_registry.py # 服务注册
│   │   ├── telemetry.py       # 遥测
│   │   └── tracing.py         # 链路追踪
│   ├── monitoring/            # 监控
│   │   ├── alerting/          # 告警
│   │   │   ├── channels.py    # 告警通道
│   │   │   ├── config.py      # 告警配置
│   │   │   ├── rules.py       # 告警规则
│   │   │   └── sender.py      # 告警发送
│   │   ├── config.py          # 监控配置
│   │   ├── dashboard.py       # 监控仪表盘
│   │   └── health.py          # 健康检查
│   ├── config/                # 配置管理
│   │   ├── defaults/          # 默认配置
│   │   │   ├── business/      # 业务默认值 (审批/关联/数据源/市场/新闻/通知/风险/策略/交易)
│   │   │   ├── infrastructure/ # 基础设施默认值 (告警/网关/缓存/数据库/日志/中间件/监控)
│   │   │   ├── core.py        # 核心配置
│   │   │   └── index.py       # 配置索引
│   │   ├── domain/            # 域配置
│   │   │   ├── data_config.py # 数据配置
│   │   │   ├── risk_config.py # 风险配置
│   │   │   └── strategy_config.py # 策略配置
│   │   ├── startup/           # 启动配置 (pydantic-settings)
│   │   │   └── settings.py    # 启动设置
│   │   ├── enums.py           # 配置枚举
│   │   ├── factory.py         # 配置工厂
│   │   ├── manager.py         # 配置管理器
│   │   ├── schemas.py         # 配置 Schema
│   │   ├── unified.py         # 统一配置
│   │   └── versioning.py      # 配置版本控制
│   ├── logging/               # 日志基础设施
│   │   ├── config.py          # 日志配置
│   │   ├── context.py         # 日志上下文
│   │   ├── formatters.py      # 日志格式化
│   │   ├── handlers.py        # 日志处理器
│   │   ├── logger.py          # 日志器
│   │   └── sensitive_filter.py # 敏感信息过滤
│   ├── metrics/               # Prometheus 指标
│   │   ├── collector.py       # 指标收集
│   │   ├── prometheus.py      # Prometheus 集成
│   │   ├── prometheus_server.py # Prometheus 服务器
│   │   └── runtime_metrics.py # 运行时指标
│   ├── utilities/             # 工具集
│   │   ├── resilience/        # 弹性
│   │   │   ├── circuit_breaker.py # 熔断器
│   │   │   ├── data_fallback.py # 数据降级
│   │   │   ├── fallback.py    # 通用降级
│   │   │   └── retry.py       # 重试
│   │   ├── degradation.py     # 降级策略
│   │   ├── http_client.py     # HTTP 客户端
│   │   ├── llm.py             # LLM 客户端
│   │   ├── priority_queue.py  # 优先级队列
│   │   ├── progress.py        # 进度追踪
│   │   ├── runtime_clock.py   # 运行时时钟
│   │   ├── scheduler.py       # 调度器
│   │   └── time_authority.py  # 时间权威
│   └── acceleration/          # PyTorch GPU 加速
│
├── config/                     # 配置治理 (YAML 配置文件)
│   ├── environments/          # 环境配置 (dev/prod/replay)
│   ├── feature_flags/         # 功能开关
│   ├── infra/                 # 基础设施配置
│   ├── runtime/               # 运行时配置 (execution/ingestion/projection/signal)
│   ├── strategy/              # 策略配置
│   │   └── symbols/           # 符号配置 (BTC/ETH/SOL)
│   ├── data_lake.yaml         # 数据湖配置
│   ├── llm_pools.yaml         # LLM 池配置
│   ├── manager.py             # 配置管理器
│   ├── schemas.py             # 配置 Schema
│   ├── validator.py           # 配置验证器
│   └── watcher.py             # 配置监听器
│
├── research/                   # 研究层 (回测/研究工具)
│   ├── leakage_audit/         # 数据泄漏审计
│   │   ├── audit.py           # 审计器
│   │   └── timeline.py        # 时间线
│   ├── protocol/              # 研究协议
│   │   ├── core.py            # 核心协议
│   │   ├── builder.py         # 构建器
│   │   └── adapters.py        # 适配器
│   ├── reality_engine/        # 真实性引擎
│   │   ├── layer.py           # 真实性层
│   │   └── models.py          # 真实性模型
│   ├── stability/             # 稳定性分析
│   │   └── analyzer.py        # 稳定性分析器
│   └── walk_forward/          # Walk-Forward 分析
│       ├── engine.py          # WF 引擎
│       ├── context.py         # WF 上下文
│       ├── splitters.py       # 数据分割
│       ├── strategy.py        # WF 策略
│       └── window.py          # WF 窗口
│
├── storage/                    # 存储层
│   └── feature_store/         # 特征存储
│       └── store.py           # 特征存储器
│
├── deploy/                     # 部署治理
│   ├── clickhouse/            # ClickHouse 配置
│   ├── grafana/               # Grafana 配置
│   ├── prometheus/            # Prometheus 配置
│   ├── tempo/                 # Tempo 配置
│   └── docker-compose.yml     # 生产 Docker Compose
│
├── docker/                     # Docker 构建
│   ├── Dockerfile             # 主 Dockerfile
│   ├── Dockerfile.gpu         # GPU Dockerfile
│   ├── Dockerfile.services    # 服务 Dockerfile
│   ├── docker-compose.yml     # 开发 Docker Compose
│   └── docker-compose.gpu.yml # GPU Docker Compose
│
├── docs/                       # 文档
├── api_server.py              # API 服务器入口
├── api_config.py              # API 配置
├── dev.sh                     # 开发脚本
├── Makefile                   # 构建脚本
└── requirements.txt           # Python 依赖
```

---

## 架构演进历史

| Phase | 内容 | 日期 |
|-------|------|------|
| Phase 1-4 | 统一 WS/Redis、Subscription、隔离、Event Sourcing | 2026-05-17 |
| Phase 5 | 删除双 Kernel/Clock/State/Pipeline/Replay，Governor → Orchestrator | 2026-05-22 |
| Phase 6 | State Ownership、Time Authority、Bus 去状态化、Domain 隔离 | 2026-05-22 |
| Phase 7 | APPLICATION CQRS facade、API→Runtime 解耦、循环依赖消除 | 2026-05-22 |
| Phase 8 | Domain 瘦身：Runtime/Infrastructure/DataPipeline/ML 迁出，Domain 只保留纯交易规则 | 2026-05-23 |
| Phase 9 | shared 层消亡：全部迁移至 domain/infrastructure/runtime/engines，shared/ 目录已删除 | 2026-05-23 |
| Phase 10 | API 层收敛：API 只调 APPLICATION，删除 domain re-export wrapper | 2026-05-23 |
| Phase 11 | Runtime 层收敛：非 Runtime 文件迁出 | 2026-05-23 |
| Phase 12 | services → engines 重构：services/ 目录整合为 engines/（adapters + compute + ml），Runtime 重组为 kernel/stateful/analytical/contracts/pipeline/replay/verification，Infrastructure 扩展 persistence/security/storage/utilities | 2026-05-24 |

---

### Phase 12: services → engines 重构 + Runtime 重组 (2026-05-24)

**原则**: 将分散的 services/ 目录整合为职责更清晰的 engines/ 层，同时重组 Runtime 目录结构。

#### services/ → engines/ (业务逻辑整合)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `services/data_service/` | `engines/adapters/data/` | 数据采集适配器 |
| `services/execution_service/` | `engines/adapters/exchange/` + `engines/compute/risk/` | 执行逻辑拆分到适配器和计算引擎 |
| `services/correlation_service/` | `engines/compute/correlation/` | 相关性计算 |
| `services/projection_service/` | `runtime/analytical/projection_runtime/` | 投影是运行时职责 |
| `services/strategy_service/` | `engines/compute/strategy/` | 策略计算 |
| `services/backtest_service/` | `runtime/stateful/replay_runtime/` | 回测是运行时职责 |
| `services/feature_service/` | `engines/compute/feature/` | 特征计算 |
| `services/research_service/` | `engines/ml/` | ML 研究 |
| `services/portfolio_service/` | `engines/compute/` + `runtime/stateful/portfolio_runtime/` | 组合逻辑和运行时分离 |
| `services/aggregation_service/` | `engines/compute/aggregation/` | 聚合计算 |
| `services/repair_service/` | `runtime/stateful/replay_runtime/` | 修复是回放运行时职责 |

#### Runtime 重组 (扁平 → 分层)

| 原位置 | 新位置 | 理由 |
|--------|--------|------|
| `runtime/orchestrator/` | `runtime/kernel/orchestrator/` | 内核总控 |
| `runtime/bus/` | `runtime/kernel/event/` | 事件总线是内核组件 |
| `runtime/context/` | `runtime/kernel/context/` | 上下文是内核组件 |
| `runtime/state/` | `runtime/kernel/state/` | 状态存储是内核组件 |
| `runtime/dependency/` | `runtime/kernel/orchestrator/dependency_graph.py` | 依赖图是编排组件 |
| `runtime/lifecycle/` | `runtime/kernel/lifecycle/` | 生命周期是内核组件 |
| `runtime/shared/` | `runtime/kernel/shared/` | 共享组件是内核组件 |
| `runtime/ingestion_runtime/` | `runtime/stateful/ingestion_runtime/` | 有状态运行时 |
| `runtime/feature_runtime/` | `runtime/stateful/feature_runtime/` | 有状态运行时 |
| `runtime/signal_runtime/` | `runtime/stateful/signal_runtime/` | 有状态运行时 |
| `runtime/execution_runtime/` | `runtime/stateful/execution_runtime/` | 有状态运行时 |
| `runtime/portfolio_runtime/` | `runtime/stateful/portfolio_runtime/` | 有状态运行时 |
| `runtime/replay_runtime/` | `runtime/stateful/replay_runtime/` | 有状态运行时 |
| `runtime/correlation_runtime/` | `runtime/analytical/correlation_runtime/` | 分析型运行时 |
| `runtime/projection_runtime/` | `runtime/analytical/projection_runtime/` | 分析型运行时 |
| `runtime/regime_runtime/` | `runtime/analytical/regime_runtime/` | 分析型运行时 |
| `runtime/narrative_runtime/` | `runtime/analytical/narrative_runtime/` | 分析型运行时 |
| `runtime/isolation/` | `runtime/kernel/namespace/` | 命名空间隔离是内核组件 |
| `runtime/timeframe_coordinator.py` | `runtime/stateful/signal_runtime/timeframe_coordinator.py` | 多周期协调属于信号运行时 |
| `runtime/validation_boundary.py` | `runtime/contracts/validation_boundary.py` | 验证边界是运行时契约 |
| `runtime/trading_mode_manager.py` | `runtime/kernel/trading_mode_manager.py` | 模式管理是内核组件 |

#### Infrastructure 扩展

| 新增目录 | 内容 | 理由 |
|----------|------|------|
| `infrastructure/persistence/` | cache, database, snapshot, state, idempotency | 持久化原语集中管理 |
| `infrastructure/security/` | api_gateway, webhook, permission | 安全原语集中管理 |
| `infrastructure/storage/` | data_lake, data_quality, feature_matrix_storage, parquet_reader, point_in_time_store | 存储原语集中管理 |
| `infrastructure/utilities/` | resilience, degradation, http_client, llm, priority_queue, progress, runtime_clock, scheduler, time_authority | 工具原语集中管理 |
| `infrastructure/messaging/aggregation_publisher/` | clickhouse_writer, kafka_publisher, parquet_writer | 聚合发布器 |

---

*文档更新日期: 2026-05-24*
