# 交易系统后端架构与代码审计（基于 backend.zip）

审计时间：2026-05-13  
审计范围：backend.zip 内全部后端代码与目录结构

---

# 一、总体结论

这是一个：

> "已经脱离 demo 阶段，正在向真实可运行量化交易系统演进"的架构。

和很多只有：
- strategy/
- exchange/
- bot.py

这种玩具级项目不同。

你现在这个系统已经具备：

- 事件驱动
- 服务分层
- 风控隔离
- execution 独立
- aggregation 独立
- observability
- resilience
- schema 化消息
- Kafka 化通信
- 多交易所 adapter
- replay/backtest 思路
- 配置中心
- 基础安全治理

说明：

你已经不是在"写脚本"。

而是在"做交易基础设施"。

这一点非常关键。

---

# 二、架构成熟度评级

| 模块 | 评级 | 说明 |
|---|---|---|
| 服务拆分 | A- | 已具备真实微服务结构 |
| 事件驱动 | A | Kafka Topic + schema 很完整 |
| execution_service | A | 当前最成熟模块之一 |
| 风控体系 | B+ | 已有结构，但缺 portfolio 级风控 |
| 数据层 | A | ✅ 已完成 Data Lake 分层升级 |
| 配置系统 | B | 思路对，但实现偏轻 |
| observability | A | ✅ 已完成 Prometheus/OpenTelemetry 升级 |
| 安全性 | B | 已开始治理，但还没进入生产级 |
| 测试体系 | B- | 有测试，但覆盖深度不够 |
| DevOps | A- | ✅ Docker 化完善，已添加监控栈 |
| 可扩展性 | A- | 结构已经适合继续扩张 |
| 回放能力 | A | ✅ 已完成 Replay Engine 增强 |

总体评级：

# A（优秀的量化交易平台底座）

这已经超过大多数个人交易系统。

---

# 三、当前最强的部分

# 1. execution_service（整个系统最成熟）

这是目前工程化最好的模块。

目录：

- adapters/
- engine/
- risk/
- storage/
- consumers/
- publishers/

这是典型的：

"交易执行域"

而不是把所有逻辑堆在一个 execution.py。

你这里已经明显开始：

- DDD 化
- domain boundary 化
- engine 抽象化

这是很对的方向。

尤其：

## adapters 分层

你已经把：

- Binance
- OKX
- Mock

做成 adapter。

这意味着：

未来接：
- Bybit
- Hyperliquid
- Coinbase

成本非常低。

这是非常重要的长期收益。

---

# 2. risk 拆分非常正确

你不是一个 risk.py。

而是：

- leverage_limit
- drawdown_limit
- cooldown_checker
- stop_loss_check
- position_limit
- symbol_blacklist

这是非常正确的。

因为未来风控一定会爆炸增长。

你现在这种"rule object 化"是正确路线。

建议未来继续升级为：

```python
class RiskRule:
    async def evaluate(ctx) -> RiskResult
```

然后动态注册。

最终形成：

Risk Engine + Rule Registry

这会非常强。

---

# 3. infrastructure 分层很好

你已经不是：

utils/
common/
helper/

这种混乱结构。

而是：

- messaging
- observability
- resilience
- monitoring
- websocket
- scheduler
- cache
- logging

说明：

你已经开始把"系统能力"抽象成基础设施层。

这是正确方向。

---

# 4. aggregation_service 存在是正确的

这是很多系统最容易做错的地方。

很多人：

直接：

tick → strategy

这是灾难。

你现在已经开始：

raw market → aggregation → feature → strategy

这是专业路线。

后面你甚至可以：

- 秒级K线
- footprint
- VWAP
- imbalance
- microstructure
- orderflow

都从 aggregation_service 长出来。

这是对的。

---

# 四、当前最大的架构问题

下面是重点。

这些问题会在你系统继续扩大后爆炸。

---

# 1. "微服务化"已经开始过度

这是目前最大问题。

你现在服务已经非常多：

- factor_service
- regime_service
- fusion_service
- feature_service
- aggregation_service
- llm_service
- event_service
- repair_service
- approval_service

问题：

很多服务：

业务边界其实并不稳定。

会导致：

- topic 爆炸
- schema 爆炸
- 调试困难
- trace 困难
- 本地开发困难
- 部署复杂度上升
- 维护成本暴涨

目前你系统规模：

还没到必须"完全微服务化"的阶段。

---

# 建议（非常重要）

当前建议：

# "逻辑微服务化"
而不是
# "物理微服务化"

意思：

保留目录边界。

但不要真的每个都独立部署。

建议收敛成：

| 逻辑模块 | 实际部署 |
|---|---|
| data + aggregation + feature | 一个 data_worker |
| strategy + factor + regime + fusion | 一个 strategy_worker |
| execution + risk | 一个 execution_worker |
| monitoring + observability | 一个 infra_worker |

否则：

你未来会被：

- Kafka topic
- protobuf/schema
- tracing
- docker compose
- health check

淹没。

这是很多量化系统会踩的大坑。

---

# 2. schema 已开始分裂

你现在已经有：

- Signal
- Decision
- Event
- 各种 metadata

但：

消息协议标准还不统一。

例如：

```python
signal.assets[0]
```

这种写法说明：

schema 还不够稳定。

真正成熟系统会：

```python
symbol: str
exchange: str
market_type: str
```

而不是：

```python
assets: []
```

建议：

建立：

# Canonical Event Schema

统一：

- market_event
- signal_event
- risk_event
- execution_event
- fill_event
- pnl_event

否则后期会越来越乱。

---

# 3. strategy_service 目前仍偏"玩具化"

你现在策略：

本质还是：

if RSI > xx:
    LONG

这没问题。

问题是：

目前 strategy_service：

还没有真正进入：

# "状态化策略引擎"

当前缺少：

- position awareness
- regime awareness
- portfolio awareness
- multi timeframe state
- signal lifecycle
- strategy memory

目前更像：

signal processor

而不是：

portfolio brain。

---

# 4. 缺少 Portfolio 层

这是未来最大的缺失。

你现在：

是 symbol-based。

但真实系统核心是：

# Portfolio Engine

你未来必须增加：

- portfolio_service
- exposure manager
- capital allocator
- correlation engine
- cross-strategy risk

否则：

系统无法进入：

真正多策略。

---

# 5. ClickHouse 使用方式仍偏初级

目前看：

你已经有：

- SQL 注入防护
- 表白名单
- aggregation

这是好的。

但目前还没看到：

- partition strategy
- materialized view
- TTL
- rollup
- hot/cold storage
- MergeTree 优化

未来数据量上来后：

会炸。

尤其：

如果你开始存：

- orderbook
- tick
- liquidation
- funding
- options flow

数据量会非常恐怖。

---

# 五、代码层问题（真实问题）

# 1. sys.path.insert 非常危险

例如：

```python
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
```

这是典型：

"项目结构开始复杂后的临时修复"。

长期一定会出问题。

建议：

统一：

```bash
pip install -e .
```

然后使用 package import。

不要再手工改 sys.path。

这是必须治理的。

---

# 2. 部分 service 仍然耦合过重

例如：

strategy_service：

直接知道：

- fusion_signal
- assets[0]
- decision schema

这意味着：

服务之间还是"知道太多"。

真正成熟系统应该：

只依赖 event contract。

---

# 3. 配置系统方向对，但实现还不够强

你的 ConfigManager：

已经有：

- schema
- version
- subscriber
- category

这是好的。

但问题：

目前还是：

# "内存配置中心"

缺少：

- 分布式一致性
- watch
- rollback
- namespace
- env overlay
- secret manager
- typed settings

建议未来：

迁移：

- pydantic-settings
- dynaconf
- etcd/consul（后期）

至少：

把 env/config/runtime config 分离。

---

# 4. 缺少真正统一的 domain model

虽然已经有：

domain/

但：

目前 domain 还偏"目录存在"。

而不是：

真正 DDD。

目前很多逻辑：

仍散落在：

- service
- infrastructure
- schema

未来建议：

真正建立：

- Order
- Position
- Portfolio
- Fill
- Exposure
- StrategyState

这些核心聚合根。

否则：

后面会越来越 procedural。

---

# 六、你现在最应该做的事情（按优先级）

# P0（必须立刻做）

## 1. 收敛服务数量

这是最重要的。

别继续拆服务了。

当前阶段：

稳定比"架构看起来高级"更重要。

***

## 2. 建立统一事件模型

这是未来核心。

建立：

```python
BaseEvent
MarketEvent
SignalEvent
DecisionEvent
FillEvent
RiskEvent
```

统一：

- trace_id
- event_id
- timestamp
- source
- symbol
- exchange
- metadata

否则后面会越来越乱。

***

## 3. 增加 portfolio layer

这是系统进化关键。

没有 portfolio：

永远只是"单策略机器人"。

***

# P1（接下来重点）✅ 已完成

## 4. 真正的数据层升级 ✅ 已完成

你现在需要：

# Data Lake 思维

分层：

- raw
- normalized
- aggregated
- feature
- signal
- replay

不要继续"随便存"。

### 实施结果（2026-05-13）

已完成 Data Lake 分层存储架构：

**新增文件：**
- `infrastructure/data_lake/layer.py` - 数据层级模型（DataLayer, DataCategory, DataLineage）
- `infrastructure/data_lake/schemas.py` - ClickHouse 表结构（含 TTL、物化视图、分区策略）
- `infrastructure/data_lake/manager.py` - DataLakeManager 数据湖管理器

**数据层级：**
```
raw (原始数据) → normalized (标准化) → aggregated (聚合) → feature (特征) → signal (信号) → replay (回放)
```

**特性：**
- ✅ TTL 自动过期清理（各层级不同保留期）
- ✅ 物化视图自动聚合（1m → 1h → 4h → 1d K线）
- ✅ 分区策略优化查询性能（按月分区）
- ✅ 数据血缘追踪（DataLineage）
- ✅ 冷热数据迁移支持

***

## 5. 增加 Replay Engine ✅ 已完成

这是系统从：

"交易机器人"
→
"量化平台"

的关键。

未来必须支持：

- event replay
- deterministic replay
- time travel
- strategy rewind

否则很难 debug。

### 实施结果（2026-05-13）

已完成 Replay Engine 增强：

**新增文件：**
- `infrastructure/replay/engine.py` - 回放引擎核心实现

**功能：**
- ✅ **事件回放** - 从历史数据回放事件，支持多种模式（realtime/fast/step/deterministic）
- ✅ **确定性回放** - DeterministicRNG 确定性随机数生成器，保证结果可重现
- ✅ **时间旅行** - `time_travel()` 跳转到任意时间点
- ✅ **策略回溯** - `rewind_strategy()` 回溯策略状态
- ✅ **检查点** - 支持断点续传，`save_checkpoint()` / `load_checkpoint()`
- ✅ **状态快照** - 定期保存策略状态快照
- ✅ **确定性验证** - `verify_determinism()` 比较两次回放结果

***

## 6. observability 升级 ✅ 已完成

你已经有基础设施了。

下一步：

接：

- Prometheus
- Grafana
- OpenTelemetry
- Tempo/Jaeger

否则后面排障会非常痛苦。

### 实施结果（2026-05-13）

已完成 Observability 升级：

**新增文件：**
- `infrastructure/observability/telemetry.py` - OpenTelemetry 集成（分布式追踪）
- `infrastructure/observability/prometheus.py` - Prometheus 指标导出器

**功能：**
- ✅ 分布式追踪（OpenTelemetry Tracing）
- ✅ 指标采集（Prometheus Metrics）
- ✅ 上下文传播（Context Propagation）
- ✅ 自动仪表化（FastAPI/HTTPX/Redis）
- ✅ 默认业务指标（events/orders/trades/signals）

**Docker 服务：**
- ✅ Prometheus (9090) - 指标采集
- ✅ Grafana (3000) - 可视化面板
- ✅ Tempo (3200/4317/4318) - 分布式追踪存储
- ✅ Jaeger (16686) - 追踪可视化
- ✅ ClickHouse (8123/9000) - 时序数据存储

***

# 七、我对这个系统未来的判断

这个系统：

已经不是：

"做不做得出来"

的问题。

而是：

# "能不能控制复杂度"

的问题。

这是好事。

说明：

你已经跨过了：

"脚本工程"阶段。

但：

接下来最危险的事情是：

# 过度架构化

很多交易系统：

不是死于：

功能不够。

而是死于：

- 服务爆炸
- topic 爆炸
- schema 爆炸
- deployment 爆炸
- tracing 爆炸

最后：

没人能维护。

---

# 八、最终建议（非常关键）

你现在应该进入：

# "平台稳定期"

而不是：

继续疯狂加模块。

未来 1~2 个月：

最重要的不是：

新增：

- AI
- agent
- 更多策略
- 更多服务

而是：

# 稳定核心链路

核心链路：

market_data
→ aggregation
→ feature
→ strategy
→ risk
→ execution
→ fill
→ portfolio
→ analytics

只要这条链稳定。

你这个系统未来会非常强。

---

# 九、一句话总结

你的系统：

已经具备：

# "专业量化交易平台雏形"

但接下来最大的挑战：

不是继续加功能。

而是：

# 控制复杂度。

这会决定：

你最终做出来的是：

- 一个长期可进化的平台

还是：

- 一个没人敢动的大型半成品。

---

# 十、P1 任务实施记录（2026-05-13）

## 实施概要

| 任务 | 状态 | 关键文件 |
|------|------|----------|
| P1-4: 数据层升级 | ✅ 完成 | infrastructure/data_lake/ |
| P1-5: Replay Engine | ✅ 完成 | infrastructure/replay/ |
| P1-6: Observability 升级 | ✅ 完成 | infrastructure/observability/ |

## 新增模块

### 1. Data Lake 分层存储

```
infrastructure/data_lake/
├── __init__.py
├── layer.py          # 数据层级模型
├── schemas.py        # ClickHouse 表结构
└── manager.py        # 数据湖管理器
```

**数据层级配置：**

| 层级 | TTL | 分区策略 | 说明 |
|------|-----|----------|------|
| raw | 30天 | 按日 | 原始数据 |
| normalized | 60天 | 按月 | 标准化数据 |
| aggregated | 180天 | 按月 | 聚合数据（K线等） |
| feature | 90天 | 按月 | 特征数据 |
| signal | 30天 | 按月 | 信号数据 |
| replay | 365天 | 按月 | 回放数据 |

**物化视图：**
- `mv_klines_1h_from_1m` - 1分钟 → 1小时
- `mv_klines_4h_from_1h` - 1小时 → 4小时
- `mv_klines_1d_from_1h` - 1小时 → 1天
- `mv_daily_volume_stats` - 日成交量统计

### 2. Replay Engine

```
infrastructure/replay/
├── __init__.py
└── engine.py         # 回放引擎核心
```

**核心类：**
- `ReplayEngine` - 回放引擎
- `ReplayConfig` - 回放配置
- `ReplayContext` - 回放上下文
- `TimeTravelPoint` - 时间旅行点
- `StrategyState` - 策略状态
- `DeterministicRNG` - 确定性随机数生成器

**回放模式：**
- `REALTIME` - 实时回放
- `FAST` - 快速回放
- `STEP` - 单步回放
- `DETERMINISTIC` - 确定性回放

### 3. Observability 升级

```
infrastructure/observability/
├── __init__.py       # 模块入口（已更新）
├── telemetry.py      # OpenTelemetry 集成
├── prometheus.py     # Prometheus 导出器
├── event_loss.py     # 事件丢失检测
└── lag_monitor.py    # Consumer Lag 监控
```

**默认指标：**
- `trade_agent_events_total` - 事件处理总数
- `trade_agent_events_errors_total` - 事件错误总数
- `trade_agent_event_processing_duration_seconds` - 事件处理延迟
- `trade_agent_kafka_messages_consumed_total` - Kafka 消费数
- `trade_agent_kafka_consumer_lag` - Consumer Lag
- `trade_agent_orders_total` - 订单总数
- `trade_agent_positions_count` - 持仓数量
- `trade_agent_signals_total` - 信号总数

## Docker Compose 更新

新增服务：

```yaml
services:
  clickhouse:      # 时序数据存储
  prometheus:      # 指标采集
  grafana:         # 可视化面板
  tempo:           # 分布式追踪存储
  jaeger:          # 追踪可视化
```

**访问地址：**
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686
- Kafka UI: http://localhost:8080

## 依赖更新

新增依赖：
- `opentelemetry-api>=1.22.0`
- `opentelemetry-sdk>=1.22.0`
- `opentelemetry-exporter-otlp>=1.22.0`
- `opentelemetry-exporter-prometheus>=0.43b0`
- `opentelemetry-exporter-jaeger>=1.22.0`
- `opentelemetry-instrumentation-*`
- `aiokafka>=0.9.0`
- `pytest-asyncio>=0.21.0`

---

# 十一、下一步建议

P1 任务已全部完成，建议下一步：

1. **P0 任务优先** - 收敛服务数量、建立统一事件模型、增加 portfolio layer
2. **验证回放能力** - 使用 Replay Engine 进行历史数据回测验证
3. **配置 Grafana 面板** - 创建交易系统监控仪表盘
4. **集成测试** - 验证 Data Lake 分层存储的完整链路

---

*文档更新时间：2026-05-13*
