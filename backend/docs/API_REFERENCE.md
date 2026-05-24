# TradeAgent API 参考文档

## 📚 **API 文档访问地址

启动服务后，可以通过以下地址访问自动生成的交互式文档：

- **Swagger UI**: `http://localhost:8001/docs`
- **ReDoc**: `http://localhost:8001/redoc`
- **OpenAPI JSON**: `http://localhost:8001/openapi.json`

## 🚀 快速启动

```bash
cd backend
python -m api_server
```

默认端口：`8001`，可通过环境变量 `API_PORT` 修改。

---

## 📋 API 端点列表

### 健康检查

#### `GET /health`

**描述**: 服务健康状态检查

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-13T10:30:00"
}
```

---

### 仪表板

#### `GET /api/v1/trading/dashboard`

**描述**: 获取完整交易仪表板数据

**响应示例**:
```json
{
  "prices": [
    {
      "symbol": "BTC",
      "price": 105000,
      "change_24h": 2.5,
      "volume_24h": 30000000000,
      "exchange": "binance"
    }
  ],
  "compositeScore": 0.65,
  "regime": {
    "state": "TRENDING",
    "confidence": 0.72,
    "trendStrength": 0.75
  },
  "risk": {
    "total": 0.35,
    "level": "low",
    "components": {
      "volatility": 0.3,
      "flow": 0.4,
      "sentiment": 0.35,
      "macro": 0.35
    }
  },
  "signal": {
    "action": "HOLD",
    "confidence": 0.5,
    "riskLevel": "MEDIUM",
    "reason": "等待更多信号"
  },
  "factors": [
    {
      "type": "trend",
      "name": "趋势",
      "weight": 0.3,
      "value": 0.7,
      "confidence": 0.8
    }
  ],
  "positions": [
    {
      "symbol": "BTC",
      "side": "LONG",
      "size": 0.5,
      "pnl": 2.5
    }
  ],
  "weightVersions": [
    {
      "version": "v1.0",
      "createdAt": "2026-01-01T00:00:00Z",
      "factors": {
        "trend": 0.3,
        "flow": 0.25,
        "sentiment": 0.25,
        "macro": 0.2
      }
    }
  ],
  "dataSources": [],
  "traders": [],
  "socialPosts": [],
  "news": []
}
```

---

### 新闻

#### `GET /api/v1/news`

**描述**: 获取最新新闻

**查询参数**:
- `limit` (可选): 返回新闻数量，默认 `20`

**响应示例**:
```json
[
  {
    "id": "1",
    "title": "新闻标题",
    "content": "新闻内容",
    "source": "coindesk",
    "sentiment": "bullish",
    "sentiment_score": 0.75,
    "published": 1715600000
  }
]
```

---

### 价格

#### `GET /api/v1/prices`

**描述**: 获取加密货币价格数据

**查询参数**:
- `symbols` (可选): 逗号分隔的交易对列表，如 `BTC,ETH,SOL,DOGE`

**响应示例**:
```json
[
  {
    "symbol": "BTC",
    "price": 105000,
    "change_24h": 2.5,
    "volume_24h": 30000000000,
    "exchange": "binance"
  }
]
```

---

### ETF 资金流

#### `GET /api/v1/etf`

**描述**: 获取 ETF 资金流数据

**查询参数**:
- `symbol` (可选): 资产符号，默认 `BTC`

**响应示例**:
```json
{
  "symbol": "BTC",
  "net_flow": 250.5,
  "inflow": 400.0,
  "outflow": 149.5,
  "confidence": 0.75
}
```

---

### 因子

#### `GET /api/v1/factors`

**描述**: 获取多因子数据

**响应示例**:
```json
[
  {
    "type": "trend",
    "name": "趋势",
    "weight": 0.3,
    "value": 0.7,
    "confidence": 0.8
  },
  {
    "type": "flow",
    "name": "资金流",
    "weight": 0.25,
    "value": 0.6,
    "confidence": 0.75
  },
  {
    "type": "sentiment",
    "name": "情绪",
    "weight": 0.25,
    "value": 0.65,
    "confidence": 0.7
  },
  {
    "type": "macro",
    "name": "宏观",
    "weight": 0.2,
    "value": 0.55,
    "confidence": 0.6
  }
]
```

---

### 市场状态

#### `GET /api/v1/regime`

**描述**: 获取当前市场状态

**响应示例**:
```json
{
  "state": "TRENDING",
  "confidence": 0.72,
  "trendStrength": 0.75
}
```

---

### 风险

#### `GET /api/v1/risk`

**描述**: 获取风险评估数据

**响应示例**:
```json
{
  "total": 0.35,
  "level": "low",
  "components": {
    "volatility": 0.3,
    "flow": 0.4,
    "sentiment": 0.35,
    "macro": 0.35
  }
}
```

---

### 信号

#### `GET /api/v1/signal`

**描述**: 获取交易信号

**响应示例**:
```json
{
  "action": "HOLD",
  "confidence": 0.5,
  "riskLevel": "MEDIUM",
  "reason": "等待更多信号"
}
```

**动作类型**:
- `LONG`: 做多
- `SHORT`: 做空
- `HOLD`: 持有
- `CLOSE`: 平仓

---

### 持仓

#### `GET /api/v1/positions`

**描述**: 获取当前持仓

**响应示例**:
```json
[
  {
    "symbol": "BTC",
    "side": "LONG",
    "size": 0.5,
    "pnl": 2.5
  },
  {
    "symbol": "ETH",
    "side": "NONE",
    "size": 0,
    "pnl": 0
  }
]
```

---

### 因子权重版本

#### `GET /api/v1/weights/versions`

**描述**: 获取因子权重版本历史

**响应示例**:
```json
[
  {
    "version": "v1.0",
    "createdAt": "2026-01-01T00:00:00Z",
    "factors": {
      "trend": 0.3,
      "flow": 0.25,
      "sentiment": 0.25,
      "macro": 0.2
    }
  }
]
```

---

## 📊 数据模型

### HealthResponse

```python
{
  status: str
  timestamp: datetime
}
```

### DashboardResponse

```python
{
  prices: List[dict]
  compositeScore: float
  regime: dict
  risk: dict
  signal: dict
  factors: List[dict]
  positions: List[dict]
  weightVersions: List[dict]
  dataSources: List[dict]
  traders: List[dict]
  socialPosts: List[dict]
  news: List[dict]
}
```

### NewsItem

```python
{
  id: str
  title: str
  content: str
  source: str
  sentiment: str
  sentiment_score: float
  published: int
}
```

### PriceItem

```python
{
  symbol: str
  price: float
  change_24h: float
  volume_24h: float
  exchange: str
}
```

---

## 🔌 CORS 配置

API 已启用了完整的 CORS 支持，允许所有来源、方法和头部。

---

## 📝 使用示例

### JavaScript

```javascript
// 获取价格
fetch('http://localhost:8001/api/v1/prices')
  .then(response => response.json())
  .then(data => console.log(data));

// 获取仪表板
fetch('http://localhost:8001/api/v1/trading/dashboard')
  .then(response => response.json())
  .then(data => console.log(data));
```

### Python

```python
import requests

# 获取价格
response = requests.get('http://localhost:8001/api/v1/prices')
prices = response.json()

# 获取新闻
response = requests.get('http://localhost:8001/api/v1/news?limit=10')
news = response.json()
```

### cURL

```bash
# 健康检查
curl http://localhost:8001/health

# 获取价格
curl "http://localhost:8001/api/v1/prices?symbols=BTC,ETH"

# 获取仪表板
curl http://localhost:8001/api/v1/trading/dashboard
```

---

## 🏗️ API 架构

API 服务器文件位于: [api_server.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/api_server.py)

数据 API 实现位于: [infrastructure/data_api/api.py](file:///Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/infrastructure/data_api/api.py)

---

## 🎯 下一步

1. 启动 API 服务器: `python -m api_server`
2. 访问交互式文档: `http://localhost:8001/docs`
3. 在 Swagger UI 中直接测试所有 API 端点

---

*最后更新: 2026-05-13*
