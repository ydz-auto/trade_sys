# 前端功能 & 后端 API 功能完整性审计

基于你上传的 `frontend.zip` 与 `backend.zip` 实际代码结构审计。

---

# 总体结论

当前系统已经不是 Demo 级别。

你现在实际上已经具备：

- 多页面交易终端前端
- 分层 API 后端
- Projection / Replay / Correlation / Alpha 生命周期
- 数据源管理
- 多数据源价格聚合
- Execution 接口
- AI/Research 框架雏形
- Runtime 协调层
- Dashboard V2

。

但：

系统目前属于：

```text
“研究型交易平台”
```

而不是：

```text
“可直接实盘全自动交易系统”
```

。

主要问题不是“有没有功能”。

而是：

# 功能闭环完整性

还有一些关键缺口。

---

# 一、前端功能审计

前端页面：

| 页面 | 状态 | 完整度 | 说明 |
|---|---|---|---|
| DashboardPage | ✅ | 85% | 主数据看板完整 |
| TradingPage | ✅ | 80% | 交易终端核心已具备 |
| DecisionPage | ✅ | 75% | 决策展示已成型 |
| PositionsPage | ✅ | 75% | 仓位管理具备 |
| RiskPage | ✅ | 70% | 风险监控有框架 |
| RiskPropagationPage | ✅ | 80% | 风险传播分析不错 |
| FactorAnalyticsPage | ✅ | 85% | 因子分析较完整 |
| AlphaLifecyclePage | ✅ | 90% | 很成熟 |
| ReplayPage | ✅ | 85% | 回放系统较完整 |
| RegimePage | ✅ | 70% | 市场状态可视化 |
| DataConfigPage | ✅ | 85% | 数据源配置完整 |
| WeightConfigPage | ✅ | 75% | 权重调参已具备 |
| ExecutionPage | ⚠️ | 60% | 更偏接口壳 |
| ControlPage | ⚠️ | 65% | Runtime 控制偏初级 |
| SettingsPage | ⚠️ | 60% | 系统配置未完全闭环 |
| SystemMonitorPage | ⚠️ | 65% | 监控能力不足 |

---

# 二、前端真正已经做出来的能力

# 1. Dashboard 已不是简单新闻页

你现在实际上已经有：

- 价格
- regime
- risk
- signal
- factors
- positions
- social
- news
- ETF
- macro
- fear&greed
- traders
- composite score

。

而且：

你已经做了：

```text
分刷新频率
```

：

| 类型 | 刷新 |
|---|---|
| 高频 | 秒级 |
| 中频 | 分钟 |
| 低频 | 5分钟 |

。

这已经是专业系统思路。

---

# 2. Replay 系统完整度 surprisingly 高

你已经有：

- ReplayPage
- ReplaySystem component
- replay API
- timeline history
- projection API

。

这意味着：

你已经开始走：

```text
事件驱动研究平台
```

路线。

这个方向是对的。

---

# 3. Alpha 生命周期模块成熟度很高

你已经有：

- proposals
- snapshots
- factor lineage

。

这其实已经不是普通量化系统了。

很多团队都没有：

```text
alpha governance
```

。

---

# 4. 因子系统是你现在最强的部分之一

你已经有：

- factor analytics
- factor weights
- correlation
- signal weight
- trigger

。

说明：

你现在真正开始做：

```text
多因子决策系统
```

而不是单纯新闻聚合。

---

# 三、前端目前缺失的重要功能

# 1. AI Overlay 没真正完成

虽然有：

- AISummaryBar

。

但：

你现在还没有真正完整：

```text
Raw + AI Overlay
```

架构。

当前缺失：

| 功能 | 状态 |
|---|---|
| 原文折叠 | ❌ |
| AI Summary | ⚠️ 半完成 |
| Narrative tags | ❌ |
| Impact prediction | ❌ |
| Multi-LLM | ❌ |
| Event linking | ❌ |
| Symbol extraction | ❌ |
| Confidence score | ❌ |

。

---

# 2. Execution UI 不完整

目前 execution 更像：

```text
API 调用层
```

而不是：

```text
真正交易终端
```

。

缺：

- 下单确认
- 订单流
- 实时成交
- websocket order updates
- order history
- partial fill
- liquidation warning
- margin monitor
- reduce-only 可视化
- TWAP/VWAP
- OCO
- trigger order

。

---

# 3. 风险系统前端还不够专业

缺：

| 功能 | 状态 |
|---|---|
| portfolio VAR | ❌ |
| exposure heatmap | ❌ |
| factor exposure | ❌ |
| liquidation cascade | ❌ |
| cross-asset risk | ❌ |
| correlation stress | ❌ |
| scenario simulation | ❌ |

。

---

# 4. 监控系统不足

SystemMonitorPage 还不是真正 observability。

缺：

- service metrics
- queue lag
- collector health
- websocket health
- kafka lag
- redis memory
- runtime state graph
- event throughput
- task latency

。

---

# 四、后端 API 审计

当前后端 API 已经很多。

你已经不是：

```text
单 FastAPI 项目
```

了。

而是：

```text
模块化服务架构
```

。

---

# 已实现 API 模块

| 模块 | 状态 | 完整度 |
|---|---|---|
| dashboard_v2 | ✅ | 90% |
| trading | ✅ | 75% |
| replay | ✅ | 80% |
| projection | ✅ | 85% |
| correlation | ✅ | 85% |
| alpha | ✅ | 90% |
| factors | ✅ | 80% |
| config | ✅ | 90% |
| refresh | ✅ | 85% |
| data | ✅ | 80% |
| prices | ⚠️ | 65% |
| websocket | ⚠️ | 30% |
| health | ✅ | 70% |
| backtest | ⚠️ | 65% |

---

# 五、后端 API 实际能力分析

# 1. Dashboard API 设计很好

你已经做了：

```text
Dashboard V2 拆分 API
```

：

- /prices
- /regime
- /risk
- /signal
- /positions
- /news
- /social
- /factors
- /traders
- /macro
- /fear-greed
- /etf

。

这是正确方向。

因为：

不同模块刷新频率不同。

你这里已经有：

```text
实时系统思维
```

了。

---

# 2. Projection API 是高级玩法

你已经有：

- decision history
- timeline
- risk state
- pnl
- metrics

。

这个实际上已经是：

```text
状态时间序列系统
```

。

这个价值很高。

---

# 3. Correlation API 很不错

有：

- summary
- signals
- detail
- trigger
- weight

。

说明你已经开始：

```text
动态因子权重
```

体系。

---

# 4. Config API 非常完整

你已经有：

- news sources
- api keys
- llm config
- data sources
- exchange configs

。

这个成熟度其实很高。

---

# 5. Replay API 合格

你已经支持：

- create replay
- query replay
- delete replay

。

但缺：

- streaming replay
- event seek
- speed control backend
- deterministic replay
- snapshot restore

。

---

# 六、后端最大的缺口

# 1. websocket 基本没真正完成

这是现在最大的问题之一。

虽然有：

```text
api/routers/websocket.py
```

。

但完整性明显不足。

你现在大量数据仍是：

```text
HTTP polling
```

。

问题：

前端会越来越重。

后面会出现：

- refresh storm
- duplicated requests
- latency
- state inconsistency

。

---

# 2. Execution Service 还不是真实交易引擎

你现在更像：

```text
Broker Adapter
```

。

而不是：

```text
Execution Engine
```

。

缺：

| 功能 | 状态 |
|---|---|
| order routing | ❌ |
| smart execution | ❌ |
| retry engine | ❌ |
| idempotency | ❌ |
| execution journal | ❌ |
| order state machine | ❌ |
| slippage tracking | ❌ |
| exchange reconciliation | ❌ |
| failover exchange | ❌ |

。

---

# 3. AI Pipeline 还没真正接入生产链路

虽然：

你已经有：

- ai_framework.py
- llm config

。

但：

当前：

```text
AI 还没成为主链路 runtime
```

。

也就是说：

现在 AI 更像：

```text
research helper
```

。

而不是：

```text
实时 intelligence layer
```

。

---

# 4. 数据标准化层不够完整

现在很多 API response schema：

还比较松散。

例如：

- change24h
- change_24h

前端还在兼容映射。

这说明：

```text
domain schema 还没完全统一
```

。

后面会越来越痛苦。

---

# 七、现在系统真正处于哪个阶段？

你现在不是：

```text
刚开始
```

。

实际上已经到：

# “中期架构演化阶段”

。

特点：

你已经有：

- 多模块
- 多 runtime
- projection
- replay
- correlation
- governance
- config center
- dashboard v2

。

接下来真正要做的是：

# 从“功能集合”变成“统一事件系统”

。

---

# 八、当前最应该优先补的 7 件事

# P0

| 项目 | 原因 |
|---|---|
| websocket runtime | 核心基础设施 |
| event bus | 系统统一核心 |
| schema normalization | 防止后期失控 |
| execution state machine | 实盘必要 |
| AI overlay pipeline | intelligence 核心 |
| observability | 后期排障必须 |
| persistence layer cleanup | replay/research 基础 |

。

---

# 九、我对当前工程成熟度评分

| 维度 | 评分 |
|---|---|
| 前端 UI | 8/10 |
| 前端架构 | 8/10 |
| API 设计 | 8.5/10 |
| 数据架构 | 7/10 |
| Runtime | 6/10 |
| AI integration | 5/10 |
| Execution | 5.5/10 |
| Research framework | 8.5/10 |
| Replay/Projection | 8.5/10 |
| 可扩展性 | 8/10 |
| 实盘 readiness | 5/10 |

。

---

# 十、一句话总结

你现在这个项目：

已经不是：

```text
“做个交易机器人”
```

。

而是正在演化成：

# “事件驱动 AI 量化研究与交易平台”

。

当前真正缺的不是页面。

而是：

```text
统一 runtime + event-driven core
```

。

一旦 websocket/eventbus/execution state machine 补完。

整个系统会直接进入：

```text
真正专业交易平台架构
```

阶段。

