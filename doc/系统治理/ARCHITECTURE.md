# 系统架构文档

**更新日期**: 2026-05-16  
**架构版本**: Runtime-Oriented Architecture

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
│