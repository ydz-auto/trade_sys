# 新闻数据架构文档

## 📋 概述

本文档描述新闻数据从采集到前端展示的完整数据流，以及各层如何使用这些数据。

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          前端展示层 (Frontend)                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  DashboardPage                                               │   │
│  │  - AISummaryBar (AI摘要)                                      │   │
│  │  - NewsCard (新闻卡片)                                        │   │
│  │  - DataSourceMonitor (数据源监控)                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ REST API
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                          API 层 (Backend API)                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  GET /news                                                     │   │
│  │  └─ ProjectionReader.get_news()                               │   │
│  │     └─ DashboardState["news"]                                 │   │
│  │                                                              │   │
│  │  返回格式：NewsItem[]                                         │   │
│  │  {                                                           │   │
│  │    id, title, title_zh, content_zh,                         │   │
│  │    source, sentiment, importance, symbols, narratives,       │   │
│  │    published, url                                            │   │
│  │  }                                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ Kafka Consumer
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                      理解层 (EventService)                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  OdailyConsumer                                              │   │
│  │  └─ LLMEnhance + Scoring + Translation                       │   │
│  │     ├─ title_zh: 中文标题                                     │   │
│  │     ├─ content_zh: 中文摘要                                   │   │
│  │     ├─ sentiment: bullish/neutral/bearish                    │   │
│  │     ├─ importance: 0.0-1.0                                  │   │
│  │     ├─ symbols: [BTC, ETH]                                  │   │
│  │     └─ narratives: [ETF, Bitcoin]                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ Kafka Producer
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                      采集层 (DataService)                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ReadHubPipeline                                             │   │
│  │  ├─ 多源采集 (RSS, Skill, API)                              │   │
│  │  ├─ 去重 (SimHash)                                           │   │
│  │  ├─ 质量打分                                                 │   │
│  │  └─ 人工审核 (可选)                                          │   │
│  │                                                              │   │
│  │  OdailySkillAdapter                                          │   │
│  │  └─ ClawHub Skill (M1-M5)                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ HTTP/RSS/Skill API
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                        外部数据源 (External)                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │ Odaily    │ │ Twitter   │ │  RSS      │ │ ClawHub   │       │
│  │ (Skill)   │ │ (API)     │ │ (Crawl)   │ │ (Skill)   │       │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 数据表结构

### ClickHouse: `news` 表

```sql
CREATE TABLE news (
    id String,
    timestamp DateTime,
    source String,
    
    -- 原始数据（英文）
    title String,
    content String,
    url String,
    
    -- LLM 翻译（中文）
    title_zh String,
    content_zh String,
    
    -- LLM 增强
    sentiment String,           -- bullish/neutral/bearish
    sentiment_score Float64,
    importance Float64,          -- 0.0-1.0
    relevance Float64,          -- 0.0-1.0
    confidence Float64,         -- 0.0-1.0
    
    -- 提取信息
    symbols String,             -- 逗号分隔: BTC,ETH
    narratives String,          -- 逗号分隔: ETF,DeFi
    actionable Bool,             -- 是否可操作
    
    -- 质量打分
    source_quality Float64,
    content_quality Float64,
    timeliness Float64,
    
    -- 特殊标记
    is_black_swan Bool,
    reasoning String,
    scored_by String,           -- 'llm' or 'keyword'
    
    -- 元数据
    ingest_time DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (source, timestamp)
TTL timestamp + INTERVAL 90 DAY
```

---

## 🎨 前端展示

### 1. 数据类型定义

```typescript
// frontend/src/types/index.ts

interface NewsItem {
  id: string
  title: string           // 英文标题（原始）
  title_zh: string        // 中文标题（LLM翻译）
  content: string          // 英文内容
  content_zh: string       // 中文摘要（LLM翻译）
  source: string          // 数据源
  sentiment: string        // bullish/neutral/bearish
  sentiment_score: number  // 0.0-1.0
  importance: number       // 0.0-1.0 (新增)
  symbols: string[]       // 相关币种 (新增)
  narratives: string[]    // 叙事标签 (新增)
  published: number        // 时间戳
  url?: string
}
```

### 2. API 调用

```typescript
// frontend/src/services/api/tradingApi.ts

export async function fetchNews(limit: number = 20): Promise<NewsItem[]> {
  return await fetchReal<NewsItem[]>(`/news?limit=${limit}`)
}
```

### 3. 显示组件

```typescript
// frontend/src/pages/DashboardPage.tsx

// 新闻列表显示
{news.slice(0, 10).map((item) => (
  <div key={item.id} className="news-item">
    {/* 中文标题 */}
    <h3>{item.title_zh || item.title}</h3>
    
    {/* 中文摘要 */}
    <p>{item.content_zh}</p>
    
    {/* 元信息 */}
    <div className="meta">
      <span>{item.source}</span>
      <span>{item.sentiment}</span>
      <span>{formatTimeAgo(item.published)}</span>
    </div>
    
    {/* 相关币种标签 */}
    <div className="tags">
      {item.symbols?.map(s => <Tag key={s}>{s}</Tag>)}
      {item.narratives?.map(n => <Tag key={n}>{n}</Tag>)}
    </div>
  </div>
))}
```

---

## ⚙️ 后端各层职责

### 1. 采集层 (DataService)

**职责：**
- 多源数据采集（RSS、API、Skill）
- 数据去重和质量打分
- 原始数据存储

**核心组件：**
```python
# services/data_service/pipeline/readhub_pipeline.py
class ReadHubPipeline:
    async def run(self):
        # 1. 多源采集
        raw_data = await self.collectors.collect()
        
        # 2. 去重
        deduplicated = self.deduplicator.deduplicate(raw_data)
        
        # 3. 质量打分
        scored = self.quality_scorer.score(deduplicated)
        
        # 4. 发布到 Kafka
        await self.publisher.publish(scored)
```

**输出：** `StandardEvent` (原始数据，未翻译)

### 2. 理解层 (EventService)

**职责：**
- LLM 增强（翻译 + 分析）
- 智能打分（分层策略）
- 叙事和符号提取

**核心组件：**
```python
# services/event_service/scoring/llm_scorer.py
class LLMScoringEngine:
    """分层 LLM 增强引擎"""
    
    async def analyze(self, event):
        priority = self.get_priority(event['source'])
        
        if priority == P0_FULL:
            return await self._full_llm_analysis(event)  # 完整 LLM
        elif priority == P1_LIGHT:
            return await self._light_llm_analysis(event)  # 轻量 LLM
        else:
            return self._keyword_fallback(event)  # 关键词规则
```

**分层策略：**
| 优先级 | 数据源 | LLM | Token消耗 | 功能 |
|--------|--------|-----|----------|------|
| P0 | Odaily, ETF, Macro | 完整 | ~300-500 | 翻译+分析+打分 |
| P1 | Twitter, Telegram | 轻量 | ~100-200 | 翻译+简单分析 |
| P2 | RSS, Whale | 关键词 | 0 | 基础打分 |

**输出：**
```python
{
    "title_zh": "中文标题",
    "content_zh": "中文摘要（100字）",
    "sentiment": "bullish",
    "importance": 0.85,
    "symbols": ["BTC", "ETH"],
    "narratives": ["ETF"],
    "confidence": 0.95,
    "scored_by": "llm"
}
```

### 3. 存储层 (Database)

**职责：**
- 持久化存储增强后的数据
- 提供查询接口

**核心组件：**
```python
# services/data_service/storage/news_storage.py
class NewsStorage:
    async def store_news(self, news: dict):
        """存储新闻（含LLM增强数据）"""
        await self._manager.insert("news", [news])
    
    async def query_news(
        self,
        source=None,
        sentiment=None,
        min_importance=0.0,
        symbols=None,
        narratives=None,
        limit=100
    ):
        """查询新闻（支持多维度过滤）"""
        # 构建查询条件
        # ...
```

### 4. API 层

**职责：**
- 提供 REST API 给前端
- 封装数据查询逻辑

**核心组件：**
```python
# api/services/projection_reader.py
class ProjectionReader:
    async def get_news(self, limit: int = 20):
        """获取新闻"""
        state = await self.get_dashboard_state()
        return state.get("news", [])[:limit]

# api/routers/dashboard.py
@router.get("/news")
async def get_news(limit: int = 20):
    reader = await get_projection_reader()
    return await reader.get_news(limit)
```

---

## 🔄 数据流示例

### 完整流程

```
1. 原始数据采集
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据源: CoinDesk RSS
标题: "BlackRock Bitcoin ETF Approved by SEC"
内容: "BlackRock's iShares Bitcoin Trust has officially received SEC approval..."


2. 采集层处理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ReadHubPipeline:
├─ 去重检查: 通过
├─ 质量打分: 0.85 (高质量)
└─ 发布到 Kafka: tradeagent.raw.news


3. 理解层增强
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLMScoringEngine (P0 完整 LLM):
├─ 标题翻译: "BlackRock 比特币 ETF 获 SEC 批准"
├─ 内容摘要: "资管巨头 BlackRock 的比特币信托基金正式获得 SEC 批准..."
├─ 情绪分析: bullish (看涨)
├─ 重要性: 0.95 (极高)
├─ 相关符号: [BTC]
├─ 叙事标签: [ETF, Institutional]
└─ 可操作性: true


4. 存储层
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ClickHouse news 表:
{
    id: "news_123",
    title: "BlackRock Bitcoin ETF Approved by SEC",
    title_zh: "BlackRock 比特币 ETF 获 SEC 批准",
    content_zh: "资管巨头 BlackRock 的比特币信托基金正式获得 SEC 批准...",
    sentiment: "bullish",
    importance: 0.95,
    symbols: "BTC",
    narratives: "ETF,Institutional",
    actionable: true,
    scored_by: "llm"
}


5. 前端展示
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DashboardPage:
┌─────────────────────────────────────┐
│ 🔵 BlackRock 比特币 ETF 获 SEC 批准  │
│                                     │
│ 资管巨头 BlackRock 的比特币信托基金   │
│ 正式获得 SEC 批准，机构资金将持续流入  │
│                                     │
│ 📊 bullish | 📈 0.95 | 🔗 BTC     │
│ 🏷️ ETF, Institutional               │
│                                     │
│ 🕐 5分钟前 | 📰 CoinDesk           │
└─────────────────────────────────────┘
```

---

## 📈 数据使用场景

### 1. 仪表板展示
- 新闻列表（按时间排序）
- 情绪指示器
- 重要性筛选

### 2. 交易决策
- 符号关联查询（BTC、ETH 相关新闻）
- 叙事分析（当前市场叙事）
- 可操作性评估

### 3. 风控系统
- 黑天鹅事件检测
- 市场情绪监控
- 来源质量追踪

### 4. 数据分析
- 新闻情绪 vs 价格走势
- 叙事热度趋势
- 来源可靠性评估

---

## 🔧 配置说明

### LLM 打分配置

```yaml
# config/environments/dev.yaml
llm_scorer:
  enabled: true
  priority_map:
    odaily: P0_FULL
    etf: P0_FULL
    macro: P0_FULL
    twitter: P1_LIGHT
    telegram: P1_LIGHT
    rss: P2_KEYWORD
    whale: P2_KEYWORD
  
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout: 60
  
  retry:
    max_attempts: 2
    initial_delay: 1.0
```

### 数据库配置

```yaml
# config/environments/dev.yaml
clickhouse:
  host: localhost
  port: 8123
  database: tradeagent
  news_table: news
  ttl_days: 90
```

---

## 📝 更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2024-01-01 | 1.0 | 初始版本 |
| 2024-05-16 | 2.0 | 新增 LLM 增强、翻译、评分功能 |
