# Data Service Architecture - 数据服务架构

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
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐
│    Market Data Layer   │  │   Intelligence Layer    │  │  Data Collection Layer │
├────────────────────────┤  ├────────────────────────┤  ├────────────────────────┤
│                        │  │                        │  │                        │
│  ┌──────────────────┐  │  │  ┌──────────────────┐  │  │  ┌──────────────────┐  │
│  │ MarketDataEngine │  │  │  │ SkillAdapterHub  │  │  │  │  Crawlers        │  │
│  │                  │  │  │  │                  │  │  │  │                  │  │
│  │  - Price Feed    │  │  │  │  - Odaily        │  │  │  │  - LLM Scraper   │  │
│  │  - Orderbook     │  │  │  │  - PANews        │  │  │  │  - RSS Feed      │  │
│  │  - ETF Flows    │  │  │  │  - Twitter       │  │  │  │  - News API      │  │
│  │  - On-chain     │  │  │  │  - News Sites   │  │  │  │  │                  │  │
│  └──────────────────┘  │  │  └──────────────────┘  │  │  └──────────────────┘  │
│                        │  │                        │  │                        │
└───────────┬────────────┘  └───────────┬────────────┘  └───────────┬────────────┘
            │                          │                          │
            └──────────────────────────┼──────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Standard Event Protocol                             │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  {                                                                   │ │
│  │    "source": "odaily",           ← 统一来源标识                      │ │
│  │    "event_type": "news",          ← 统一事件类型                     │ │
│  │    "sentiment": "bullish",        ← 统一情绪 (bullish/bearish/neutral)│ │
│  │    "importance": 0.91,           ← 统一重要性 (0-1)                 │ │
│  │    "symbols": ["BTC"],            ← 统一标的                         │ │
│  │    "tags": ["ETF", "BlackRock"],  ← 统一标签                         │ │
│  │    "confidence": 0.95,            ← 置信度                          │ │
│  │  }                                                                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Event Bus                                        │
│                                                                              │
│  StandardEvent ──▶ EventBus ──┬──▶ Strategy Engine                           │
│                               ├──▶ Risk Engine                               │
│                               ├──▶ Intelligence Engine (LLM/Sentiment)       │
│                               ├──▶ Notification                              │
│                               └──▶ Storage (回测/Replay)                     │
│                                                                              │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Intelligence Engine                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────┐ │
│  │ LLM Summariz. │  │ Sentiment Anal │  │ Narrative Det. │  │ Regime     │ │
│  └────────────────┘  └────────────────┘  └────────────────┘  │ Tagging    │ │
│                                                              └────────────┘ │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────┐ │
│  │ Entity Extract │  │ Quality Score  │  │ Context Update │  │ Exposure   │ │
│  └────────────────┘  └────────────────┘  └────────────────┘  │ Generation │ │
│                                                              └────────────┘ │
└──────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    Feature/Factor Engine ──▶ Strategy ──▶ Risk ──▶ Execution │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 📁 目录结构

```
data_service/
│
├── 【核心协议】
├── standard_event.py              # 标准事件协议 - 所有数据源统一格式
│
├── 【适配器层 - Intelligence Layer】
├── adapters/
│   ├── __init__.py
│   └── skill_adapter.py          # Skill 适配器基类 + 注册表
│       ├── SkillAdapter          # 抽象基类
│       ├── OdailySkillAdapter    # Odaily Skill 适配器
│       ├── TwitterAdapter        # Twitter 适配器
│       ├── NewsAdapter           # 新闻网站适配器
│       └── get_adapter_registry() # 适配器注册表
│
├── 【事件总线】
├── event_bus/
│   ├── __init__.py
│   └── event_bus.py             # 事件发布/订阅 + 回放
│       ├── EventBus
│       ├── publish_event()
│       ├── get_history()        # 获取历史事件
│       └── replay()             # 回测重放
│
├── 【Market Data Layer - 市场数据层】
├── market/
│   ├── __init__.py
│   └── market_data.py           # 市场数据引擎
│       ├── MarketDataEngine
│       ├── PriceCollector
│       ├── OrderbookCollector
│       ├── ETFCollector
│       └── OnChainCollector
│
├── 【Intelligence Layer - 情报层】
├── intelligence/
│   ├── __init__.py
│   ├── odaily_skill.py          # Odaily Skill 集成 (ClawHub)
│   ├── intelligence_engine.py   # 情报处理引擎
│   │   ├── IntelligenceEngine
│   │   ├── enrich_event()       # LLM 增强
│   │   ├── update_context()     # 更新市场上下文
│   │   └── get_current_context() # 获取当前上下文
│   └── intelligence_hub.py       # 情报中心 Hub
│
├── 【Data Collection Layer - 数据采集层】
├── collectors/
│   ├── __init__.py
│   ├── base_collector.py         # 基础采集器 (熔断/重试/降级)
│   ├── news_collector.py         # 新闻采集器
│   ├── news_feed_collector.py    # RSS Feed 采集器
│   ├── news_api_collector.py     # News API 采集器
│   ├── llm_scraper.py           # LLM 爬虫
│   ├── twitter_collector.py     # Twitter 采集器
│   ├── etf_collector.py         # ETF 数据采集
│   ├── exchange_collector.py     # 交易所数据采集
│   ├── macro_collector.py       # 宏观数据采集
│   ├── crypto_stock_collector.py # 加密股票采集
│   ├── social_media_collector.py # 社交媒体采集
│   ├── trader_collector.py      # 交易员数据采集
│   ├── multi_source.py         # 多源聚合采集
│   ├── news_hub.py             # 新闻中心
│   │
│   ├── examples/               # 使用示例
│   │   ├── using_base_collector.py
│   │   ├── using_news_hub.py
│   │   └── test_resilience.py
│   │
│   └── tests/                  # 测试
│       ├── test_news.py
│       ├── test_etf.py
│       ├── test_exchange.py
│       └── test_trader.py
│
├── 【Quality Layer - 质量处理层】
├── quality/
│   ├── __init__.py
│   ├── quality_scorer.py        # 质量评分
│   ├── content_dedup.py        # 内容去重
│   ├── source_tracking.py      # 来源追踪
│   └── human_review.py         # 人工审核 (可选)
│
├── 【Pipeline Layer - 流水线层】
├── pipeline/
│   ├── __init__.py
│   ├── readhub_pipeline.py     # ReadHub 风格流水线
│   ├── realtime_push.py       # 实时推送
│   ├── scheduler.py           # 调度器
│   └── example_usage.py       # 使用示例
│
├── 【Utils Layer - 工具层】
├── utils/
│   ├── __init__.py
│   ├── http_client.py          # HTTP 客户端 (带熔断)
│   ├── rss_parser.py          # RSS 解析器
│   ├── html_parser.py         # HTML 解析器
│   ├── data_cleaner.py        # 数据清洗
│   ├── date_parser.py         # 日期解析
│   ├── symbol_extractor.py     # 标的提取
│   └── README.md
│
├── 【其他】
├── cache.py                   # 缓存
├── storage.py                 # 存储
├── main.py                   # 主入口
├── main_kafka.py             # Kafka 版本
├── kafka_producer/           # Kafka 生产者
├── websocket/                # WebSocket
│
└── requirements.txt
```

## 🎯 核心概念

### 1. Market Data Layer vs Intelligence Layer

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Market Data Layer                               │
├─────────────────────────────────────────────────────────────────────┤
│  用途: 结构化市场数据                                               │
│  数据: 价格、订单簿、ETF 净流量、链上数据、K线                       │
│  特点: 高频、实时、结构化、确定性                                     │
│  示例: Binance API, ETF Flow API, On-chain API                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     Intelligence Layer                              │
├─────────────────────────────────────────────────────────────────────┤
│  用途: 非结构化情报                                                 │
│  数据: 新闻、Narrative、社交媒体、分析师观点、AI 分析                 │
│  特点: 低频、异步、非结构化、需 LLM 处理                            │
│  示例: Odaily Skill, PANews, Twitter, News API                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. StandardEvent - 统一事件协议

所有数据源统一转换为 StandardEvent：

```python
from standard_event import StandardEvent

event = StandardEvent(
    id="evt_20260512_001",
    source="odaily",                    # 数据源: odaily/panews/twitter/binance
    event_type="news",                  # 事件类型: news/etf/price/narrative
    timestamp=1715500000,              # Unix 时间戳
    title="BTC ETF 获批引发市场热议",
    summary="BlackRock BTC ETF 获批...",
    content="...",
    sentiment="bullish",               # bullish/bearish/neutral
    importance=0.91,                   # 0-1 重要性
    symbols=["BTC", "ETH"],            # 相关标的
    tags=["ETF", "BlackRock", "机构"], # 标签
    narratives=["ETF 叙事", "机构入场"], # Narrative
    confidence=0.95,                   # 置信度
    quality_score=0.88,               # 质量评分
    original_data={}                   # 原始数据
)
```

### 3. SkillAdapter - 适配器模式

```python
from adapters import SkillAdapter, AdapterConfig

class OdailySkillAdapter(SkillAdapter):
    def __init__(self):
        super().__init__(
            name="odaily",
            config=AdapterConfig(
                source_type="skill",
                enabled=True,
                priority=Priority.HIGH
            )
        )

    async def fetch_raw_data(self):
        # 从 ClawHub/Odaily API 获取
        return await self.clawhub_client.fetch_news()

    def normalize(self, raw_data) -> List[StandardEvent]:
        # 转换为 StandardEvent
        return [
            StandardEvent(
                source="odaily",
                event_type="news",
                title=item["title"],
                sentiment=self._analyze_sentiment(item["content"]),
                importance=self._calculate_importance(item),
                ...
            )
            for item in raw_data
        ]
```

### 4. EventBus - 事件总线

```python
from event_bus import get_event_bus, publish_event

bus = get_event_bus()

# 订阅
bus.subscribe(
    name="my_strategy",
    callback=on_news_event,
    filter=lambda e: e.event_type == "news"
)

# 发布事件
await publish_event(event)

# 回测: 重放历史事件
bus.replay(historical_events)
```

## 🔄 数据流

### Intelligence 数据流

```
Odaily Skill / PANews / Twitter / News API
        │
        ▼
    SkillAdapter
        │
        ▼
   StandardEvent
        │
        ▼
    EventBus
        │
        ├──▶ IntelligenceEngine
        │       │
        │       ├── LLM Summarization
        │       ├── Sentiment Analysis
        │       ├── Narrative Detection
        │       └── Regime Tagging
        │       │
        │       ▼
        │    EnrichedContext
        │
        ├──▶ Strategy Engine
        ├──▶ Risk Engine
        └──▶ Notification
```

### Market 数据流

```
Exchange API / ETF API / On-chain API
        │
        ▼
   MarketDataEngine
        │
        ▼
   StandardEvent
        │
        ▼
    EventBus
        │
        └──▶ Strategy/Risk Engine
```

## 💡 架构优势

1. **统一格式**
   - 所有数据源 → StandardEvent
   - 策略/风控只需理解一种格式

2. **分层清晰**
   - Market Data Layer: 结构化、高频
   - Intelligence Layer: 非结构化、低频、需 LLM

3. **可扩展**
   - 新数据源: 只需实现 SkillAdapter
   - 新消费者: 只需订阅 EventBus

4. **可回测**
   - EventBus 保存完整事件历史
   - `bus.replay()` 支持回测重放

5. **多消费者**
   - 一个事件可被多个消费者并行处理

## 🔧 使用示例

### 1. 使用 SkillAdapter

```python
from adapters import get_adapter_registry
from event_bus import publish_event

registry = get_adapter_registry()

# 采集所有 Skill 数据
events = await registry.collect_all()

# 发布到事件总线
for event in events:
    await publish_event(event)
```

### 2. 订阅事件

```python
from event_bus import get_event_bus

bus = get_event_bus()

async def on_news(event):
    if event.sentiment == "bullish" and event.importance > 0.8:
        print(f"重要利好: {event.title}")

bus.subscribe("trader", on_news, filter=lambda e: e.event_type == "news")
```

### 3. 获取市场上下文

```python
from intelligence import get_intelligence_engine

engine = get_intelligence_engine()
context = engine.get_current_context()

print(f"市场状态: {context.regime}")
print(f"风险等级: {context.risk_level}")
print(f"建议仓位: {context.recommended_exposure}")
```

### 4. 回测

```python
from event_bus import get_event_bus

bus = get_event_bus()

# 获取历史事件
events = bus.get_history(
    event_type="news",
    source="odaily",
    start_time=1714500000,
    end_time=1715500000,
    limit=1000
)

# 重放进行回测
bus.replay(events, playback_speed=10)
```

## 🔌 ClawHub Odaily Skill 集成

### 概述

Odaily Skill (ClawHub) 是专业的加密市场智能助手，提供五大核心模块：

| 模块 | 名称 | 工具调用 | 说明 |
|------|------|---------|------|
| M1 | 今日必关注 | `get_today_watch` | 每日最值得关注的核心事件 |
| M2 | 加密市场分析 | `get_crypto_market_analysis` | BTC/ETH 行情、宏观分析 |
| M3 | 明日关注 | `get_tomorrow_watch` | 近期重大事件预告 |
| M4 | 巨鲸尾盘追踪 | `scan_whale_tail_trades` | Polymarket 高确信押注 |
| M5 | API原始数据 | `get_api_module` | 完整文章和快讯数据 |

### 安装

```bash
openclaw skills install odaily-skill
```

### 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ClawHub Odaily Skill                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   run.py ──▶ get_today_watch ──────────┐                          │
│   run.py ──▶ get_crypto_market_analysis ┼──▶ JSON Output          │
│   run.py ──▶ get_tomorrow_watch ────────┤                          │
│   run.py ──▶ scan_whale_tail_trades ────┤                          │
│   run.py ──▶ get_api_module ────────────┘                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  OdailySkillAdapter                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ClawHubRunner.call_module()                                       │
│         │                                                           │
│         ├── _normalize_m1() ──▶ StandardEvent (News)              │
│         ├── _normalize_m2() ──▶ StandardEvent (Market Regime)     │
│         ├── _normalize_m3() ──▶ StandardEvent (Calendar)          │
│         ├── _normalize_m4() ──▶ StandardEvent (Whale)             │
│         └── _normalize_m5() ──▶ StandardEvent (Raw Data)          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                              StandardEvent
                                     │
                                     ▼
                               EventBus
```

### 使用

```python
from adapters import OdailySkillAdapter

# 完整模块 (M1-M5)
adapter = OdailySkillAdapter()

# 指定模块
adapter = OdailySkillAdapter(modules=["M1", "M4"])

# 采集数据
events = await adapter.collect()

for event in events:
    print(f"[{event.source}] {event.title}")
    print(f"  Sentiment: {event.sentiment}, Importance: {event.importance}")
```

### 手动调用

```bash
# 查找 Skill 目录
SKILL_DIR=$(find ~/.openclaw ~/.claude -name "run.py" -path "*odai*" 2>/dev/null | head -1 | xargs dirname)

# M1: 今日必关注
cd "$SKILL_DIR" && python3 run.py get_today_watch '{"limit": 10}'

# M2: 市场分析
cd "$SKILL_DIR" && python3 run.py get_crypto_market_analysis '{"focus": "overview"}'

# M3: 明日关注
cd "$SKILL_DIR" && python3 run.py get_tomorrow_watch '{}'

# M4: 巨鲸追踪
cd "$SKILL_DIR" && python3 run.py scan_whale_tail_trades '{"min_size": 10000, "min_price": 0.95}'

# M5: API原始数据
cd "$SKILL_DIR" && python3 run.py get_api_module '{}'
```

## 📈 Roadmap

- [x] StandardEvent 协议定义
- [x] SkillAdapter 适配器基类
- [x] EventBus 事件总线
- [x] Market Data Layer
- [x] Intelligence Layer
- [x] ClawHub Odaily Skill 真实 API 集成 (M1-M5)
- [ ] PANews 适配器
- [ ] LLM 增强功能
- [ ] 完整回测功能
- [ ] 监控告警
