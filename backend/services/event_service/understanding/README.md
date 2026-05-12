# Event Understanding Layer - 事件理解层

## 📊 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Data Service (事实层)                                  │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬───────────┤ │
│  │  Exchange   │    ETF/     │   Twitter   │  Telegram   │  Website  │ │
│  │    API     │   Macro     │     /X      │             │   Crawl   │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┴───────────┘ │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ raw.*
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Event Service (理解层) ⭐                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┬─────────────────┬─────────────────────────────────┐ │
│  │     Skills     │      LLM        │         Parser                  │ │
│  │ (World         │   (Anthropic/   │    (News/Twitter/Telegram/     │ │
│  │  Interpreter)  │    OpenAI)      │     ETF/OnChain)               │ │
│  │                │                 │                                 │ │
│  │  • Odaily     │  • Event        │  • Symbol Extraction           │ │
│  │  • Twitter     │    Extraction   │  • Entity Extraction           │ │
│  │  • Macro      │  • Sentiment    │  • Content Normalization      │ │
│  │  • ETF        │    Analysis     │                                 │ │
│  └────────┬────────┘────────┬────────┘────────────────┬────────────────┘ │
│           │                │                       │                  │
│           ▼                ▼                       ▼                  │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │                      Classifier (分类器)                            ││
│  │                                                                     ││
│  │  • Sentiment (bullish/bearish/neutral)                            ││
│  │  • Narrative (ETF/DeFi/Institutional/Hack)                        ││
│  │  • Regime (bull/bear/neutral/volatile)                           ││
│  │  • Risk (low/medium/high/critical)                                ││
│  └────────────────────────────────────────────────────────────────────┘│
│                                 │                                      │
│                                 ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │                    Understanding Engine                            ││
│  │                                                                     ││
│  │  • 协调 Parser/Classifier/Extractor 工作                         ││
│  │  • 管理市场上下文                                                  ││
│  │  • 追踪 Narrative 和 Regime 变化                                  ││
│  └────────────────────────────────────────────────────────────────────┘│
│                                 │                                      │
│                                 ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │                    Understanding Hub                               ││
│  │                                                                     ││
│  │  • 整合所有组件                                                    ││
│  │  • 生成情报报告                                                    ││
│  │  • 生成交易上下文                                                  ││
│  └────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ events.*
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Fusion Service (共识层)                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
event_service/
├── understanding/
│   ├── __init__.py                 # 模块导出
│   │
│   ├── skills/                     # Skill 适配器（World Interpreter）
│   │   ├── __init__.py
│   │   ├── odaily/                 # Odaily Skill
│   │   │   ├── __init__.py
│   │   │   └── collector.py        # Odaily 采集器
│   │   ├── twitter/                # Twitter Skill
│   │   ├── macro/                  # Macro Skill
│   │   └── etf/                    # ETF Skill
│   │
│   ├── parser/                     # 原始数据解析器
│   │   ├── __init__.py
│   │   └── parser.py               # 统一解析器
│   │
│   ├── llm/                        # LLM 客户端
│   │   ├── __init__.py
│   │   └── client.py               # LLM 客户端封装
│   │
│   ├── extractor/                  # 事件提取器
│   │   ├── __init__.py
│   │   └── extractor.py            # LLM 驱动的事件提取
│   │
│   ├── classifier/                 # 事件分类器
│   │   ├── __init__.py
│   │   └── classifier.py           # 分类器实现
│   │
│   ├── engine/                    # 理解引擎
│   │   ├── __init__.py
│   │   └── engine.py               # 协调各组件
│   │
│   └── hub/                       # 理解中心
│       ├── __init__.py
│       └── hub.py                 # 统一接口
│
├── consumers/                     # Kafka 消费者
├── producers/                     # Kafka 生产者
├── schemas/                       # 数据模型
└── main.py                        # 主入口
```

---

## 🎯 核心职责

### Understanding Layer 负责：

| 职责 | 说明 |
|------|------|
| **Skill 适配** | 接入 Odaily/Twitter/Macro/ETF 等 Skill |
| **数据解析** | 将原始数据解析为统一格式 |
| **LLM 提取** | 使用 LLM 从非结构化数据中提取结构化事件 |
| **事件分类** | Sentiment、Narrative、Regime、Risk 分类 |
| **上下文管理** | 管理市场上下文，追踪 Regime 变化 |
| **情报报告** | 生成可用的情报报告 |

### Understanding Layer 不负责：

| ❌ 不负责 | 原因 |
|----------|------|
| 数据采集 | 属于 data_service |
| 数据存储 | 属于基础设施层 |
| 信号交易 | 属于 fusion_service |
| 订单执行 | 属于 execution_service |

---

## 🔧 核心模块

### 1. Skills - 世界解释器

Skills 是 "World Interpreter"，负责理解外部世界：

```python
from event_service.understanding.skills.odaily import get_odaily_collector

collector = get_odaily_collector()

# M1: 今日必关注
events = await collector.get_must_watch_events()

# M2: 市场分析
analysis = await collector.get_market_analysis()
print(f"Regime: {analysis.regime}")

# M3: 明日事件
tomorrow = await collector.get_tomorrow_events()

# M4: 巨鲸信号
whales = await collector.get_whale_alerts()
```

### 2. Parser - 数据解析器

Parser 将不同来源的原始数据解析为统一格式：

```python
from event_service.understanding.parser import get_data_parser

parser = get_data_parser()

# 解析新闻
news_parsed = parser.parse(raw_news_data, source_type="news")

# 解析 Twitter
twitter_parsed = parser.parse(raw_twitter_data, source_type="twitter")

# 解析 ETF
etf_parsed = parser.parse(raw_etf_data, source_type="etf")
```

### 3. Classifier - 事件分类器

Classifier 负责对事件进行分类：

```python
from event_service.understanding.classifier import get_event_classifier

classifier = get_event_classifier()

result = classifier.classify(
    title="BTC ETF 获批引发市场大涨",
    content="BlackRock BTC ETF 获批...",
    importance=0.9
)

print(f"Sentiment: {result.sentiment}")        # bullish
print(f"Narratives: {result.narratives}")      # ['ETF', 'Institutional']
print(f"Regime: {result.regime}")              # bull
print(f"Risk Level: {result.risk_level}")      # low
```

### 4. Extractor - 事件提取器

Extractor 使用 LLM 从原始数据中提取结构化事件：

```python
from event_service.understanding.extractor import get_event_extractor

extractor = get_event_extractor()

extraction = await extractor.extract(parsed_content)

print(f"Event Type: {extraction['event_type']}")
print(f"Direction: {extraction['direction']}")
print(f"Strength: {extraction['strength']}")
print(f"Confidence: {extraction['confidence']}")
```

### 5. Engine - 理解引擎

Engine 协调各组件工作：

```python
from event_service.understanding.engine import get_understanding_engine

engine = await get_understanding_engine()

# 理解单条数据
enriched = await engine.understand(raw_data, source_type="news")

# 批量理解
batch = await engine.understand_batch(raw_datas, source_type="news")

# 获取当前市场上下文
context = engine.get_context()
print(f"Regime: {context.regime}")
print(f"Narratives: {context.narratives}")
```

### 6. Hub - 理解中心

Hub 提供统一的理解接口：

```python
from event_service.understanding.hub import get_understanding_hub

hub = await get_understanding_hub()

# 获取完整情报报告
report = await hub.get_intelligence_report()

print(f"Regime: {report.market_context.regime}")
print(f"Narratives: {report.market_context.narratives}")
print(f"Risk Level: {report.market_context.risk_level}")

# 生成交易上下文（用于 LLM 决策）
context = await hub.generate_trading_context()
print(f"Recommended Exposure: {context['recommended_exposure']}")
print(f"Top Events: {context['top_events']}")
```

---

## 📈 数据流

```
Raw Data (from data_service)
    │
    ├── skills/ → 理解外部世界（Odaily/Twitter/Macro/ETF）
    │
    ├── parser/ → 解析原始数据为统一格式
    │
    ├── extractor/ → 使用 LLM 提取结构化事件
    │
    ├── classifier/ → 分类（Sentiment/Narrative/Regime/Risk）
    │
    ├── engine/ → 协调各组件，管理上下文
    │
    └── hub/ → 提供统一接口，生成报告
         │
         ▼
Structured Events
    │
    ▼
events.* (Kafka)
```

---

## 🎯 Odaily Skill 最适合做什么

### ✅ 非常适合

| 功能 | 推荐原因 |
|------|----------|
| 新闻摘要 | 结构化输出，减少 LLM 调用 |
| 市场事件抽取 | 已有成熟的 prompt 模板 |
| Sentiment 分析 | 基于市场叙事判断 |
| Narrative 识别 | 识别主流叙事（ETF/DeFi/NFT） |
| 热点检测 | 识别市场热点 |
| Event 标签 | 结构化标签 |
| Entity extraction | 提取代币、人物、机构 |

### ⚠️ 慎用

| 功能 | 原因 |
|------|------|
| 直接交易信号 | Hallucination 风险 |
| 仓位管理 | 数据不稳定 |
| Execution | 风险极高 |

---

## 🔌 集成到 Event Service

```python
from services.event_service.main import get_event_service

service = await get_event_service()

# 处理原始消息
event = await service.process_raw_message(raw_message)

# 获取情报报告
report = await service.get_intelligence_report()

# 生成交易上下文
context = await service.generate_trading_context()

# 查看统计
print(service.stats)
```

---

## 📚 相关文档

- [data_service/README.md](../data_service/README.md) - 数据服务文档
- [Topic System](../../infrastructure/messaging/topics.py) - 分层 Topic 体系
- [Domain Event](../../domain/event/) - 事件类型定义
- [Shared Contracts](../../shared/contracts/) - 统一数据模型
