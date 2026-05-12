# Intelligence Layer - 情报层架构

## 📊 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Raw Data Layer                                   │
├─────────────┬─────────────┬─────────────┬─────────────┬───────────────┤
│   Exchange  │  ETF/Macro  │   Twitter   │   Telegram  │   Website     │
│     API     │             │      /X     │             │    Crawl      │
└─────────────┴─────────────┴─────────────┴─────────────┴───────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Semantic Intelligence Layer                            │
├─────────────────┬─────────────────┬───────────────────────────────────┤
│   Odaily Skill  │  News Collector │       Intelligence Hub             │
│   (M1-M5)       │                 │                                    │
│                 │                 │  • LLM Summarize                   │
│  • 今日必关注    │  • RSS Feed    │  • Event Extraction               │
│  • 市场分析     │  • Quality      │  • Regime Tagging                 │
│  • 明日事件     │    Scoring     │  • Sentiment                      │
│  • 巨鲸追踪     │  • Dedup       │  • Narrative Clustering            │
│  • API 原始数据  │                 │  • Risk Event Detection            │
└─────────────────┴─────────────────┴───────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Factor Engine                                     │
├─────────────────┬─────────────────┬─────────────────────────────────────┤
│   Event Factor  │   Regime Factor │      Sentiment Factor              │
│                 │                 │                                    │
│  • News Impact  │  • Bull/Bear    │  • Twitter Sentiment              │
│  • Whale Flow    │    Regime       │  • Fear & Greed                   │
│  • Prediction    │  • Volatility  │  • Narrative Strength              │
│    Markets       │    Regime       │                                    │
└─────────────────┴─────────────────┴─────────────────────────────────────┘
```

## 🎯 Odaily Skill (ClawHub) 定位

### 集成方式

| 方式 | 描述 | 配置 |
|------|------|------|
| **Mock** | 模拟数据（默认） | `integration_type="mock"` |
| **ClawHub** | 通过 `clawhub run` 命令调用 | `integration_type="clawhub"` |
| **HTTP API** | 通过 HTTP API 调用 | `integration_type="http"` |

### 模块说明

| 模块 | 功能 | TradeAgent 用途 |
|------|------|----------------|
| **M1: 今日必关注** | 重要事件列表 | Event Factor |
| **M2: 市场分析** | Regime/Narrative | Regime Factor |
| **M3: 明日事件** | 预期事件 | Event Calendar |
| **M4: 巨鲸追踪** | Whale/Polymarket | Whale Factor |
| **M5: API 原始数据** | 结构化 JSON | 直接消费 |

### 1. ClawHub 集成

#### 安装 ClawHub

```bash
# 安装 clawhub CLI
npm install -g clawhub@latest --registry https://registry.npmmirror.com

# 搜索 crypto 相关技能
clawhub search crypto

# 安装 Odaily 技能（假设技能名是 odaily-crypto）
clawhub install odaily-crypto
```

#### 使用 ClawHub

```python
from services.data_service.intelligence import OdailySkillCollector

collector = OdailySkillCollector(
    integration_type="clawhub",  # 使用 ClawHub
    skill_name="odaily-crypto",  # 技能名称
    use_mock=False
)

report = await collector.get_daily_intelligence()
```

### 2. HTTP API 集成

```python
from services.data_service.intelligence import OdailySkillCollector

collector = OdailySkillCollector(
    integration_type="http",          # 使用 HTTP API
    api_url="https://api.odaily.com",  # API 地址
    api_key="your_api_key",           # API Key（可选）
    use_mock=False
)

report = await collector.get_daily_intelligence()
```

### 3. Mock 数据（默认）

```python
from services.data_service.intelligence import OdailySkillCollector

collector = OdailySkillCollector(
    integration_type="mock",  # 使用 Mock 数据
    use_mock=True
)

report = await collector.get_daily_intelligence()
```

### 使用场景

```python
from services.data_service.intelligence import get_odaily_collector

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

# M5: 原始数据
report = await collector.get_daily_intelligence()
```

## 🧠 Intelligence Hub 功能

### 1. 市场上下文

```python
hub = get_intelligence_hub()

# 获取完整情报报告
report = await hub.get_intelligence_report()

print(f"Regime: {report.market_context.regime}")
print(f"Narratives: {report.market_context.narratives}")
print(f"Risk Level: {report.market_context.risk_level}")
```

### 2. 增强新闻

```python
# 获取增强后的新闻
for news in report.enriched_news:
    print(f"标题: {news.title}")
    print(f"情绪: {news.sentiment}")
    print(f"重要性: {news.importance}")
    print(f"Regime 相关性: {news.regime_relevance}")
    print(f"事件类型: {news.event_type}")
```

### 3. 交易上下文（用于 LLM）

```python
# 生成 LLM 友好的交易上下文
context = await hub.generate_trading_context()

print(f"市场状态: {context['market_regime']}")
print(f"叙事: {context['dominant_narratives']}")
print(f"建议仓位: {context['recommended_exposure']}")
print(f"可操作洞察: {context['actionable_insights']}")
```

## 📈 数据流

### 1. 新闻采集流程

```
RSS/API/Webhook
    ↓
Quality Scorer (来源白名单 + 内容质量)
    ↓
Deduplicator (SimHash + MinHash)
    ↓
Symbol Extractor (提取 BTC/ETH/SOL)
    ↓
Intelligence Hub (增强 + 上下文)
    ↓
LLM Factor Engine
```

### 2. 事件信号流程

```
Odaily Skill (M1-M4)
    ↓
Event Signals Extraction
    ↓
Regime Classification (Bull/Bear/Neutral)
    ↓
Risk Assessment
    ↓
Alert Generation
```

## ⚠️ 重要说明

### 适合 ✅

- 新闻分析
- AI Agent
- 研究环境
- 因子生成
- Narrative tracking
- Event-driven signals

### 不适合 ❌

- 高频交易主链路
- 低延迟 execution
- 核心风控依赖
- 唯一数据源

### 设计原则

1. **作为 Intelligence Layer，不是 Execution Layer**
2. **提供 context，不是 signal**
3. **Human-in-the-loop for critical decisions**
4. **多层验证，不依赖单一数据源**

## 🔧 集成到 TradeAgent

### 1. 在交易决策中使用

```python
from services.data_service.intelligence import get_intelligence_hub

async def trading_decision():
    hub = get_intelligence_hub()
    context = await hub.generate_trading_context()
    
    # 根据 Regime 调整策略
    if context["market_regime"] == "bull":
        bias = "long"
    elif context["market_regime"] == "bear":
        bias = "short"
    else:
        bias = "neutral"
    
    # 根据叙事调整仓位
    narratives = context["dominant_narratives"]
    if "ETF" in narratives:
        btc_weight = 0.6
    else:
        btc_weight = 0.4
    
    return {"bias": bias, "btc_weight": btc_weight, "context": context}
```

### 2. 在风控中使用

```python
async def risk_check():
    hub = get_intelligence_hub()
    report = await hub.get_intelligence_report()
    
    # 检查风险告警
    if report.risk_alerts:
        for alert in report.risk_alerts:
            logger.warning(f"Risk Alert: {alert}")
    
    # 检查 Regime 变化
    if report.regime_changes:
        for change in report.regime_changes:
            logger.warning(f"Regime Change: {change}")
    
    # 根据风险等级调整仓位
    if report.market_context.risk_level == "high":
        reduce_exposure()
```

## 📁 模块结构

```
data_service/intelligence/
├── __init__.py
├── odaily_skill.py      # Odaily Skill 采集器
└── intelligence_hub.py   # 情报中心
```

## 🚀 下一步

1. [ ] 接入真实的 Odaily Skill API
2. [ ] 扩展更多情报源
3. [ ] 添加 LLM 总结功能
4. [ ] 完善 Regime 检测算法
5. [ ] 添加历史回测功能
