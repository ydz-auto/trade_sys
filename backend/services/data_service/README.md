# Data Service Architecture - 数据服务架构

## ⚠️ 架构变更说明

**重要更新**：Intelligence Layer 已迁移到 `event_service/understanding/`

根据系统边界划分原则：
- **data_service**：只负责事实（collect, normalize, publish, cache, retry, healthcheck）
- **event_service**：负责理解世界（LLM, skills, parser, extractor, classifier）

详细迁移信息请参考 [event_service/understanding/README.md](../event_service/understanding/README.md)

---

## 🏗️ 整体架构：AI Native Trading System

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           External Sources                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Exchange API │  │  ETF/Macro   │  │  Twitter/X   │  │  Telegram    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  On-chain    │  │ Odaily Skill │  │   PANews     │  │  金十 Skill  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Data Service (事实层)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Collectors  │  │  Normalizer  │  │  Publisher  │  │    Cache     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                              │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼ raw.*
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Event Service (理解层) ⭐                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │    Skills    │  │    Parser    │  │  Extractor  │  │  Classifier  │   │
│  │  (World      │  │  (解析原始   │  │  (LLM 事件   │  │  (Sentiment, │   │
│  │  Interpreter)│  │   数据)      │  │   提取)      │  │   Narrative, │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  │   Regime)    │   │
│                                                        └──────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Understanding Hub                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼ events.*
┌──────────────────────────────────────────────────────────────────────────────┐
│                       Fusion Service (共识层)                                │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼ signals.*
┌──────────────────────────────────────────────────────────────────────────────┐
│                      Strategy → Risk → Execution                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
data_service/
│
├── 【核心协议】
├── standard_event.py              # 标准事件协议 - 所有数据源统一格式
│
├── 【适配器层 - Adapter Layer】
├── adapters/
│   ├── __init__.py
│   ├── skill_adapter.py          # Skill 适配器基类 + 注册表
│   ├── odaily_adapter.py        # Odaily 适配器
│   ├── twitter_adapter.py       # Twitter 适配器
│   ├── cryptopanic_adapter.py   # Cryptopanic 适配器
│   ├── whale_alert_adapter.py   # Whale Alert 适配器
│   └── qq_adapter.py            # QQ 适配器
│
├── 【事件总线】
├── event_bus/
│   ├── __init__.py
│   └── event_bus.py             # 事件发布/订阅 + 回放
│
├── 【Market Data Layer - 市场数据层】
├── market/
│   ├── __init__.py
│   └── market_data.py           # 市场数据引擎
│
├── 【Data Collection Layer - 数据采集层】
├── collectors/
│   ├── __init__.py
│   ├── base_collector.py         # 基础采集器 (熔断/重试/降级)
│   ├── news_collector.py         # 新闻采集器
│   ├── news_feed_collector.py    # RSS Feed 采集器
│   ├── twitter_collector.py     # Twitter 采集器
│   ├── etf_collector.py         # ETF 数据采集
│   ├── exchange_collector.py     # 交易所数据采集
│   ├── macro_collector.py       # 宏观数据采集
│   ├── multi_source.py          # 多源聚合采集
│   └── binance_websocket.py     # Binance WebSocket
│
├── 【Quality Layer - 质量处理层】
├── quality/
│   ├── quality_scorer.py        # 质量评分
│   ├── content_dedup.py        # 内容去重
│   ├── source_tracking.py      # 来源追踪
│   └── human_review.py         # 人工审核
│
├── 【Pipeline Layer - 流水线层】
├── pipeline/
│   ├── readhub_pipeline.py     # ReadHub 风格流水线
│   ├── realtime_push.py       # 实时推送
│   └── scheduler.py           # 调度器
│
├── 【Utils Layer - 工具层】
├── utils/
│   ├── http_client.py          # HTTP 客户端
│   ├── rss_parser.py          # RSS 解析器
│   ├── html_parser.py         # HTML 解析器
│   ├── data_cleaner.py        # 数据清洗
│   ├── date_parser.py         # 日期解析
│   └── symbol_extractor.py    # 标的提取
│
├── 【Sources - 实时数据源】
├── sources/
│   ├── base.py                # 数据源基类
│   ├── qq_realtime.py         # QQ 实时源
│   └── telegram_realtime.py   # Telegram 实时源
│
└── requirements.txt
```

---

## 🎯 核心职责

### Data Service 只负责：

| 职责 | 说明 |
|------|------|
| **Collect** | 从外部源采集原始数据 |
| **Normalize** | 数据格式标准化 |
| **Publish** | 发布到 Kafka `raw.*` topic |
| **Cache** | 本地缓存 |
| **Retry** | 失败重试 |
| **Healthcheck** | 健康检查 |

### Data Service 不负责：

| ❌ 不负责 | 原因 |
|----------|------|
| LLM 调用 | 属于 event_service |
| 事件提取 | 属于 event_service |
| 情绪分析 | 属于 event_service |
| Narrative 检测 | 属于 event_service |
| Regime 标记 | 属于 event_service |

---

## 🔌 数据流

```
External Sources
    ↓
Data Service (collect, normalize)
    ↓ raw.*
Event Service (parse, extract, classify)
    ↓ events.*
Fusion Service (consensus)
    ↓ signals.*
Strategy/Risk/Execution
```

---

## 💡 使用示例

### 1. 采集新闻数据

```python
from services.data_service.collectors import NewsCollector

collector = NewsCollector()
result = await collector.collect()

for item in result.data:
    print(f"[{item['source']}] {item['title']}")
```

### 2. 发布原始数据

```python
from infrastructure.messaging import KafkaProducer

producer = KafkaProducer()
await producer.publish(
    topic="raw.news.odaily",
    data=news_event.to_dict()
)
```

---

## 📚 相关文档

- [event_service/understanding/README.md](../event_service/understanding/README.md) - 理解层完整文档
- [Topic System](../infrastructure/messaging/topics.py) - 分层 Topic 体系
