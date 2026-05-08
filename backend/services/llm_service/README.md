# LLM Service

独立LLM微服务，提供情绪分析、结构化数据提取、策略解释等功能。

## 架构

```
collectors (data_service)
        │
        ├── llm_client.chat() ──────────┐
        ├── llm_client.sentiment() ─────┼──→ HTTP → llm_service (:8001)
        └── llm_client.news_analysis() ──┘                    │
                                                          └── OpenAI / Anthropic / MiniMax
```

## 启动

```bash
cd backend/services/llm_service
pip install -r requirements.txt
python main.py
```

## 环境变量

```bash
# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MINIMAX_API_KEY=...

# Redis (可选，用于缓存)
REDIS_URL=redis://localhost:6379/0

# 日志
LOG_LEVEL=INFO

# 端口
LLM_SERVICE_PORT=8001
```

## API 接口

### Chat (通用对话)

```bash
POST /api/v1/chat
Content-Type: application/json

{
  "messages": [
    {"role": "system", "content": "你是..."},
    {"role": "user", "content": "用户问题"}
  ],
  "model": "gpt-4o-mini",      # 可选，默认 gpt-4o-mini
  "temperature": 0.7,           # 可选
  "max_tokens": 2000,           # 可选
  "stream": false                # 可选，是否流式
}
```

流式响应示例：
```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

### 情绪分析

```bash
POST /api/v1/sentiment
Content-Type: application/json

{
  "text": "BTC暴涨突破10万美元！牛市来了！",
  "model": "gpt-4o-mini"
}

# 返回
{
  "sentiment": "bullish",
  "confidence": 0.95,
  "score": 0.8
}
```

### 结构化提取

```bash
POST /api/v1/extract
Content-Type: application/json

{
  "content": "页面HTML内容...",
  "prompt": "从页面提取ETF净流入数据",
  "schema": {"type": "object", "properties": {...}},
  "model": "gpt-4o-mini"
}

# 返回
{
  "net_flow": 150000000,
  "inflow": 150000000,
  "outflow": 0
}
```

### 新闻分析

```bash
POST /api/v1/news/analyze
Content-Type: application/json

{
  "title": "SEC批准比特币ETF",
  "content": "美国证券交易委员会今天批准了..."
}

# 返回
{
  "sentiment": "bullish",
  "confidence": 0.9,
  "score": 0.7,
  "event_type": "regulatory",
  "black_swan_score": 0.6,
  "urgency": "urgent",
  "affected_markets": ["BTC", "ETH"],
  "affected_symbols": ["IBIT", "FBTC"]
}
```

### 社交媒体分析

```bash
POST /api/v1/social/analyze
Content-Type: application/json

{
  "content": "CZ推文内容...",
  "platform": "twitter"
}

# 返回
{
  "观点": "BTC还会继续涨",
  "情绪": "bullish",
  "情绪置信度": 0.85,
  "资产": ["BTC"],
  "时间预期": "medium",
  "论据": ["机构持续买入", "ETF净流入增加"],
  "影响力评分": 0.9
}
```

## 健康检查

```bash
GET /health
# 返回 {"status": "healthy", "service": "llm_service"}

GET /ready
# 返回 {"status": "ready", "models": ["openai", "anthropic", "minimax"]}
```

## 支持的模型

| Provider | 模型 | 说明 |
|----------|------|------|
| OpenAI | gpt-4o-mini, gpt-4o | 默认 |
| Anthropic | claude-3-5-haiku | |
| MiniMax | MiniMax-Text-01 | |

## 缓存

- 默认使用内存缓存
- 可配置 Redis 缓存（设置 `REDIS_URL`）
- 情绪分析缓存 1 小时
- 提取结果缓存 1 小时

## 目录结构

```
llm_service/
├── main.py                 # FastAPI 主程序
├── config.py               # 配置
├── llm/                    # LLM 客户端
│   ├── openai_client.py
│   ├── anthropic_client.py
│   └── minimax_client.py
├── services/               # 分析服务
│   ├── sentiment_analyzer.py
│   ├── news_extractor.py
│   └── social_analyzer.py
└── cache/                  # 缓存
    └── response_cache.py
```
