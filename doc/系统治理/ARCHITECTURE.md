# 系统架构文档

**更新日期**: 2026-05-17  
**架构版本**: Runtime-Oriented Architecture v2.0

---

## 架构演进历史

### Phase 1-4 重构完成 (2026-05-17)

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 统一 WebSocket 和 Redis Pub/Sub | ✅ 完成 |
| Phase 2 | Subscription Runtime 和 Backpressure | ✅ 完成 |
| Phase 3 | Runtime 隔离和 Event Sourcing | ✅ 完成 |
| Phase 4 | Full Event Sourcing 和分布式治理 | ✅ 完成 |

---

## 核心原则

### 职责分离

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           services/                                          │
│                                                                              │
│  只保留业务逻辑：                                                              │
│  - factor logic         (因子计算)                                           │
│  - signal logic         (信号生成)                                           │
│  - fusion logic         (信号融合)                                           │
│  - risk rules           (风控规则)                                           │
│  - strategy logic       (策略决策)                                           │
│  - execution logic      (订单执行)                                           │
│  - aggregation logic    (数据聚合)                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                │ 被调用
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           runtime/                                           │
│                                                                              │
│  只负责运行时编排：                                                            │
│  - kafka consumer       (Kafka 消费)                                         │
│  - kafka producer       (Kafka 发布)                                         │
│  - retry                (重试机制)                                           │
│  - metrics              (指标收集)                                           │
│  - tracing              (链路追踪)                                           │
│  - healthcheck          (健康检查)                                           │
│  - lifecycle            (生命周期管理)                                        │
│  - backpressure         (背压控制)                                           │
│  - subscription         (订阅管理)                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                │ 使用
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     infrastructure/runtime/                                  │
│                                                                              │
│  运行时基础设施：                                                              │
│  - governor             (运行时治理器)                                        │
│  - priority_queue       (优先级队列)                                         │
│  - subscription_manager (订阅管理器)                                         │
│  - degradation          (降级策略)                                           │
│  - circuit_breaker      (熔断器管理)                                         │
│  - recovery             (运行时恢复)                                         │
│  - distributed_governance (分布式治理)                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
backend/
├── api/                        # FastAPI / WS Gateway
│   ├── routers/               # API 路由
│   ├── schemas/               # 请求/响应模型
│   └── services/              # API 服务层
│
├── services/                   # ⭐ 业务逻辑层 (15个服务)
│   ├── data_service/          # 数据采集适配器
│   ├── aggregation_service/   # 数据聚合逻辑
│   ├── event_service/         # 事件理解逻辑
│   ├── fusion_service/        # 信号融合逻辑
│   ├── execution_service/     # 执行逻辑
│   ├── risk_service/          # 风控规则
│   ├── strategy_service/      # 策略逻辑
│   ├── approval_service/      # 审批逻辑
│   ├── backtest_service/      # 回测逻辑
│   ├── repair_service/        # 修复逻辑
│   ├── llm_service/           # LLM 服务
│   ├── projection_worker/     # CQRS 投影
│   ├── correlation_worker/    # 相关性分析
│   └── monitoring/            # 监控
│
├── application/                # ⭐ 业务用例层
│   └── services/              # 业务服务编排
│
├── runtime/                    # ⭐ 运行时层 (9个运行时)
│   ├── base.py                # Runtime Contract
│   ├── shared/                # 共享组件
│   ├── ingestion_runtime/     # 数据采集运行时
│   ├── signal_runtime/        # 信号生成运行时
│   ├── execution_runtime/     # 订单执行运行时
│   ├── projection_runtime/    # CQRS 投影运行时
│   ├── correlation_runtime/   # 相关性分析运行时
│   ├── replay_runtime/        # 回放运行时
│   ├── narrative_runtime/     # AI 叙事运行时
│   ├── monitoring_runtime/    # 监控运行时
│   └── scheduler_runtime/     # 调度运行时
│
├── domain/                     # 领域模型层
│   ├── execution/             # 执行领域模型
│   ├── portfolio/             # 投资组合模型
│   └── risk/                  # 风控配置
│
├── infrastructure/             # 基础设施层
│   ├── cache/                 # Redis 缓存
│   ├── database/              # 数据库连接
│   ├── messaging/             # Kafka 消息
│   ├── data_lake/             # 数据湖
│   ├── observability/         # 可观测性
│   ├── replay/                # 回放引擎
│   ├── runtime/               # ⭐ 运行时基础设施 (Phase 2-4)
│   │   ├── governor.py        # 运行时治理器
│   │   ├── priority_queue.py  # 优先级队列
│   │   ├── subscription_manager.py # 订阅管理器
│   │   ├── degradation.py     # 降级策略
│   │   ├── circuit_breaker_manager.py # 熔断器
│   │   ├── recovery.py        # 运行时恢复 (Phase 4)
│   │   └── distributed_governance.py # 分布式治理 (Phase 4)
│   ├── snapshot/              # 快照系统
│   ├── verification/          # 验证系统
│   └── websocket/             # WebSocket 网关 (Phase 1)
│       └── gateway.py         # 统一 WS Gateway
│
├── config/                     # 配置治理
│   ├── environments/          # 环境配置 (dev/prod/replay)
│   ├── infra/                 # 基础设施配置
│   ├── runtime/               # 运行时配置
│   ├── strategy/              # 策略配置
│   └── feature_flags/         # 功能开关
│
├── deploy/                     # 部署治理
│   ├── docker-compose.yml     # 统一部署配置
│   ├── grafana/               # Grafana 监控配置
│   ├── prometheus/            # Prometheus 监控配置
│   └── tempo/                 # Tempo 链路追踪配置
│
├── research/                   # 研究层
│   ├── backtest/              # 回测框架
│   ├── correlation/           # 相关性分析
│   ├── factor/                # 因子研究
│   ├── pipeline/              # 特征流水线
│   ├── experiment/            # 实验追踪
│   └── strategy/              # 策略研究
│
└── scripts/                    # 脚本工具
```

---

## Runtime 与 Services 的对应关系

| Runtime | 调用的 Services | 说明 |
|---|---|---|
| `ingestion_runtime` | `data_service/`, `aggregation_service/` | 数据采集 + 聚合 |
| `signal_runtime` | `fusion_service/`, `strategy_service/`, `event_service/` | 信号融合 + 策略决策 |
| `execution_runtime` | `execution_service/`, `risk_service/`, `approval_service/` | 订单执行 + 风控 |
| `projection_runtime` | `projection_worker/` | CQRS 投影 |
| `correlation_runtime` | `correlation_worker/` | 相关性分析 |
| `replay_runtime` | `repair_service/`, `backtest_service/` | 回放 + 回测 |
| `narrative_runtime` | `llm_service/` | AI 叙事 |
| `monitoring_runtime` | `monitoring/` | 监控 |
| `scheduler_runtime` | 多个定时任务 | 调度 |

---

## 核心功能模块

### 1. 交易系统 (Trading System)

| 功能 | 说明 |
|---|---|
| **交易所支持** | Binance, OKX |
| **市场类型** | 现货 (spot), USDT合约 (usdt_futures), 币本位合约 (coin_futures) |
| **杠杆交易** | 1-125x 杠杆设置 |
| **止盈止损** | 支持百分比和价格两种方式 |
| **仓位模式** | 逐仓 (isolated), 全仓 (cross) |

### 2. 回测系统 (Backtest System)

| 功能 | 说明 |
|---|---|
| **数据源** | Redis 存储的历史数据 |
| **信号源** | 真实生成的交易信号 |
| **因子分析** | 多因子权重优化 |
| **结果展示** | 收益率、夏普比率、最大回撤 |

### 3. 风控引擎 (Risk Engine)

| 风控类型 | 说明 |
|---|---|
| **止损检查** | 自动止损触发 |
| **每日亏损限制** | 日亏损上限 |
| **杠杆限制** | 最大杠杆控制 |
| **仓位限制** | 单品种仓位上限 |
| **冷却期** | 交易冷却时间 |
| **黑名单** | 禁止交易品种 |

### 4. 数据采集 (Data Collection)

| 数据类型 | 采集器 | 数据源 |
|---|---|---|
| **价格数据** | ExchangeCollector | Binance, OKX, CoinGecko |
| **ETF资金流** | ETFCollector | SoSoValue |
| **新闻资讯** | NewsCollector | 多新闻源 |
| **宏观数据** | MacroCollector | 多数据源 |
| **Twitter 推送** | TwitterPushCollector | Chrome Extension |
| **Telegram 消息** | TelegramAdapter | Telegram 频道 |

### 5. 数据采集运行时 (Ingestion Runtime)

| 组件 | 说明 |
|---|---|
| **WebSocket 价格采集** | Binance 实时价格、成交、强平 |
| **Twitter Push 服务器** | WebSocket 服务器，接收 Chrome Extension 推送 |
| **Twitter Cookie Monitor** | Cookie API 采集，云服务器友好的降级方案 |
| **Telegram 监听器** | 监听新闻频道、KOL 群消息 |
| **新闻采集** | 定时采集多源新闻 |
| **Odaily 采集** | Odaily 星球日报数据采集 |

### 6. Twitter 采集架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Twitter 数据采集架构                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  主链路（推荐）          降级方案                                             │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │ Twitter Cookie  │    │ Chrome Extension│                                 │
│  │ Monitor         │    │ Push            │                                 │
│  │                 │    │                 │                                 │
│  │ - Cookie API    │    │ - WebSocket     │                                 │
│  │ - 轮询 P0 账号  │    │ - 实时推送      │                                 │
│  │ - 云服务器友好  │    │ - 需要本地浏览器│                                 │
│  │ - 轻量级        │    │ - GUI 依赖      │                                 │
│  └────────┬────────┘    └────────┬────────┘                                 │
│           │                      │                                           │
│           └──────────┬───────────┘                                           │
│                      │                                                       │
│                      ▼                                                       │
│           ┌─────────────────────┐                                            │
│           │ TwitterPushCollector│                                            │
│           │ (业务逻辑层)         │                                            │
│           │                     │                                            │
│           │ - P0 账号过滤       │                                            │
│           │ - 币种关键词提取    │                                            │
│           │ - 事件标准化        │                                            │
│           └──────────┬──────────┘                                            │
│                      │                                                       │
│                      ▼                                                       │
│           ┌─────────────────────┐                                            │
│           │ Kafka / EventBus    │                                            │
│           └─────────────────────┘                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 方案 | Cookie Monitor | Chrome Extension |
|------|----------------|------------------|
| **方式** | Cookie + GraphQL API | WebSocket 推送 |
| **GUI** | 不需要 | 需要浏览器 |
| **云服务器** | 非常适合 | 麻烦 |
| **资源占用** | 极低 | 高 |
| **实时性** | 中高（轮询） | 高 |
| **稳定性** | 中（Cookie 可能过期） | 中 |
| **部署** | 简单 | 麻烦 |

**配置环境变量：**
```bash
# Twitter Cookie Monitor
TWITTER_AUTH_TOKEN=xxx    # auth_token cookie
TWITTER_CT0=xxx           # ct0 cookie
TWITTER_BEARER_TOKEN=xxx  # Bearer token (可选)
```

---

## 配置治理

### 五层配置结构

```
config/
├── environments/    # 环境配置 (dev/prod/replay)
├── infra/           # 基础设施配置
├── runtime/         # 运行时配置
├── strategy/        # 策略配置
└── feature_flags/   # 功能开关
```

---

## 前端架构

### 技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 5.x | 构建工具 |
| Ant Design | 5.x | UI 组件库 |
| TailwindCSS | 3.x | 样式框架 |
| Zustand | 4.x | 状态管理 |

---

## 关键原则

1. **services/ 保留业务逻辑** - 因子、信号、融合、风控、策略、执行等业务逻辑
2. **runtime/ 负责运行时编排** - Kafka 消费/发布、重试、指标、健康检查等
3. **runtime 调用 services** - runtime 是入口，调用 services 的业务逻辑
4. **不删除 services** - 只是把运行时职责迁移到 runtime

---

## Phase 1-4 新增组件

### Phase 1: 统一 WebSocket 和 Redis Pub/Sub

| 组件 | 位置 | 说明 |
|------|------|------|
| `WSGateway` | `infrastructure/websocket/gateway.py` | 统一 WebSocket 网关，支持节流、重连 |
| `ThrottleConfig` | `infrastructure/websocket/gateway.py` | 节流配置 |
| Redis Pub/Sub | `services/projection_service/projections/base.py` | 跨进程消息推送 |

### Phase 2: Subscription Runtime 和 Backpressure

| 组件 | 位置 | 说明 |
|------|------|------|
| `SubscriptionManager` | `infrastructure/runtime/subscription_manager.py` | 订阅管理器 |
| `PriorityQueue` | `infrastructure/runtime/priority_queue.py` | 优先级队列 |
| `DegradationStrategy` | `infrastructure/runtime/degradation.py` | 降级策略 |
| `CircuitBreakerManager` | `infrastructure/runtime/circuit_breaker_manager.py` | 熔断器管理 |
| `RuntimeGovernor` | `infrastructure/runtime/governor.py` | 运行时治理器 |

### Phase 3: Runtime 隔离和 Event Sourcing

| 组件 | 位置 | 说明 |
|------|------|------|
| `ReplayRuntime` | `runtime/replay_runtime/` | 回放运行时，支持回测和修复 |
| `ExecutionStateMachine` | `services/execution_service/state_machine/` | 执行状态机 |

### Phase 4: Full Event Sourcing 和分布式治理

| 组件 | 位置 | 说明 |
|------|------|------|
| `RuntimeRecovery` | `infrastructure/runtime/recovery.py` | 运行时恢复，支持检查点和状态恢复 |
| `DistributedRuntimeGovernance` | `infrastructure/runtime/distributed_governance.py` | 分布式治理，支持主节点选举和故障转移 |

---

## 数据流架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                                   │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │  WebSocket  │◄───│  Zustand    │◄───│  Components │                      │
│  │  Client     │    │  Store      │    │             │                      │
│  └──────┬──────┘    └─────────────┘    └─────────────┘                      │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │
          │ WebSocket Connection
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     WSGateway (infrastructure/websocket/)                    │
│                                                                              │
│  - 连接管理、节流控制、重连逻辑                                                 │
│  - 订阅管理 (SubscriptionManager)                                            │
│  - Redis Pub/Sub 订阅                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │ Redis Pub/Sub
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Runtime Layer (runtime/)                                 │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ ingestion_runtime│  │ signal_runtime  │  │execution_runtime│              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                        │
│           └────────────────────┼────────────────────┘                        │
│                                │                                             │
│                                ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │              RuntimeGovernor (infrastructure/runtime/)           │        │
│  │                                                                  │        │
│  │  - 优先级队列 (PriorityQueue)                                    │        │
│  │  - 背压控制 (Backpressure)                                       │        │
│  │  - 降级策略 (DegradationStrategy)                                │        │
│  │  - 熔断器 (CircuitBreakerManager)                                │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │ 调用
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Services Layer (services/)                               │
│                                                                              │
│  业务逻辑：因子计算、信号生成、风控规则、执行逻辑等                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 相关文档

- [AUDIT_SUMMARY.md](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/doc/系统治理/AUDIT_SUMMARY.md) - 审计总结报告
- [SERVICES_RESPONSIBILITY_MAPPING.md](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/doc/系统治理/SERVICES_RESPONSIBILITY_MAPPING.md) - 服务职责映射
- [01_Schema统一规范.md](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/doc/系统治理/01_Schema统一规范.md) - Schema 统一规范

---

*文档更新日期: 2026-05-17*
