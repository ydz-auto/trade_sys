# Services 职责映射文档

**更新日期**: 2026-05-14

---

## 概述

本文档明确 `services/` 中每个服务的职责边界，区分**业务逻辑**和**运行时职责**。

---

## 职责定义

### 业务逻辑（保留在 services/）

| 类型 | 说明 |
|---|---|
| factor logic | 因子计算逻辑 |
| signal logic | 信号生成逻辑 |
| fusion logic | 信号融合逻辑 |
| risk rules | 风控规则 |
| proposal generation | 提案生成 |
| strategy logic | 策略决策逻辑 |
| execution logic | 订单执行逻辑 |
| aggregation logic | 数据聚合逻辑 |

### 运行时职责（迁移到 runtime/）

| 类型 | 说明 |
|---|---|
| kafka consumer | Kafka 消费 |
| kafka producer | Kafka 发布 |
| websocket loop | WebSocket 循环 |
| scheduler | 定时调度 |
| retry | 重试机制 |
| metrics | 指标收集 |
| tracing | 链路追踪 |
| healthcheck | 健康检查 |
| lifecycle | 生命周期管理 |

---

## 服务职责分析

### data_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `collectors/` | 业务逻辑（数据采集适配器） | ✅ 保留 |
| `adapters/` | 业务逻辑（外部适配器） | ✅ 保留 |
| `utils/` | 业务逻辑（工具类） | ✅ 保留 |
| `main.py` | 运行时职责（入口） | ⚠️ 迁移到 runtime/ |
| `main_kafka.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |

### aggregation_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `aggregators/` | 业务逻辑（聚合逻辑） | ✅ 保留 |
| `models/` | 业务逻辑（数据模型） | ✅ 保留 |
| `publishers/` | 运行时职责（Kafka/ClickHouse 发布） | ⚠️ 部分迁移 |
| `main.py` | 运行时职责（入口） | ⚠️ 迁移到 runtime/ |

### event_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `understanding/` | 业务逻辑（事件理解） | ✅ 保留 |
| `services/` | 业务逻辑（服务） | ✅ 保留 |
| `main.py` | 运行时职责（入口） | ⚠️ 迁移到 runtime/ |
| `main_kafka.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |

### fusion_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `engine.py` | 业务逻辑（融合引擎） | ✅ 保留 |
| `buffer.py` | 业务逻辑（事件缓冲） | ✅ 保留 |
| `aggregator.py` | 业务逻辑（事件聚合） | ✅ 保留 |
| `scorer.py` | 业务逻辑（评分引擎） | ✅ 保留 |
| `main_kafka.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |

### strategy_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `strategies.py` | 业务逻辑（策略逻辑） | ✅ 保留 |
| `strategy_examples.py` | 业务逻辑（策略示例） | ✅ 保留 |
| `main_kafka.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |

### execution_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `engine/` | 业务逻辑（执行引擎） | ✅ 保留 |
| `risk/` | 业务逻辑（风控规则） | ✅ 保留 |
| `adapters/` | 业务逻辑（交易所适配器） | ✅ 保留 |
| `storage/` | 业务逻辑（存储） | ✅ 保留 |
| `main_kafka.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |

### risk_service/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `risk_engine.py` | 业务逻辑（风控引擎） | ✅ 保留 |
| `main_kafka.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |

### projection_worker/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `projections/` | 业务逻辑（投影逻辑） | ✅ 保留 |
| `main.py` | 运行时职责（入口） | ⚠️ 迁移到 runtime/ |

### correlation_worker/

| 文件/目录 | 职责类型 | 是否保留 |
|---|---|---|
| `strategy_adapter.py` | 业务逻辑（策略适配器） | ✅ 保留 |
| `kafka_consumer.py` | 运行时职责（Kafka 消费） | ⚠️ 迁移到 runtime/ |
| `main.py` | 运行时职责（入口） | ⚠️ 迁移到 runtime/ |

---

## Runtime 与 Services 的调用关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           runtime/                                           │
│                                                                              │
│  ingestion_runtime ──────────────────► data_service/collectors/             │
│                                       aggregation_service/aggregators/       │
│                                                                              │
│  signal_runtime ─────────────────────► fusion_service/engine.py             │
│                                       strategy_service/strategies.py         │
│                                                                              │
│  execution_runtime ──────────────────► execution_service/engine/            │
│                                       risk_service/risk_engine.py            │
│                                                                              │
│  projection_runtime ─────────────────► projection_worker/projections/       │
│                                                                              │
│  correlation_runtime ────────────────► correlation_worker/strategy_adapter  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 迁移计划

### 阶段 1（已完成）

- ✅ 创建 `runtime/` 层
- ✅ 创建 `runtime/shared/` 共享组件
- ✅ 更新 `runtime/` 调用 `services/` 的业务逻辑

### 阶段 2（进行中）

- ⏳ 标记 `services/` 中的运行时职责文件
- ⏳ 逐步废弃 `services/*/main_kafka.py`
- ⏳ 统一使用 `runtime/` 作为入口

### 阶段 3（最终）

- ⏳ `services/` 只保留业务逻辑
- ⏳ `runtime/` 负责所有运行时编排
- ⏳ 清理废弃文件

---

## 关键原则

1. **services/ 保留业务逻辑**
   - 因子、信号、融合、风控、策略、执行等业务逻辑

2. **runtime/ 负责运行时编排**
   - Kafka 消费/发布、重试、指标、健康检查等

3. **runtime 调用 services**
   - runtime 是入口，调用 services 的业务逻辑

4. **不删除 services**
   - 只是把运行时职责迁移到 runtime

---

*文档版本: v1.0*
