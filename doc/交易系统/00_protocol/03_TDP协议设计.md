# TDP协议设计文档

# 🧠 1. 协议定位

# 1.1 核心作用

TDP（Trade Data Protocol）是**交易系统的标准数据协议**，用于：
- 统一多源数据格式
- 支持多资产分析
- 标准化模块间通信

# 1.2 设计目标

```
✅ 统一数据结构
✅ 支持多资产
✅ 支持扩展
✅ 可版本化管理
✅ 便于回测和审计
```

# 📦 2. 协议结构

# 2.1 顶层结构

```json
{
  "version": "1.0",
  "timestamp": 1710000000,
  "mode": "LIVE",
  "meta": {...},
  "market": {...},
  "events": [...],
  "signals": {...}
}
```

# 2.2 版本管理

```python
TDP_VERSION = "1.0"

def validate_version(data: dict) -> bool:
    if data.get("version") != TDP_VERSION:
        raise TDPVersionError(f"Version mismatch: expected {TDP_VERSION}")
    return True
```

# 📊 3. Meta字段（元信息）

```json
{
  "meta": {
    "request_id": "req_12345",
    "source": "data_service",
    "destination": "factor_engine",
    "time_generated": 1710000000,
    "time_received": 1710000001,
    "status": "OK",
    "error": null
  }
}
```

# 📈 4. Market字段（市场数据）

# 4.1 完整结构

```json
{
  "market": {
    "crypto": {...},
    "commodities": {...},
    "etf": {...}
  }
}
```

# 4.2 Crypto（加密货币）

```json
{
  "crypto": {
    "BTC": {
      "price": 68000.0,
      "open": 67500.0,
      "high": 68500.0,
      "low": 67000.0,
      "volume": 1234567.89,
      "change_24h": 0.025,
      "change_percent_24h": 2.5,
      "timestamp": 1710000000,
      "timeframe": "5m"
    },
    "ETH": {...}
  }
}
```

# 4.3 Commodities（商品）

```json
{
  "commodities": {
    "gold": {
      "price": 2020.5,
      "change_percent_24h": 0.5,
      "timestamp": 1710000000
    },
    "oil": {
      "price": 78.3,
      "change_percent_24h": -0.3,
      "timestamp": 1710000000
    }
  }
}
```

# 4.4 ETF

```json
{
  "etf": {
    "BTC": {
      "inflow_24h": 150000000,
      "outflow_24h": 80000000,
      "net_flow_24h": 70000000,
      "total_aum": 5000000000,
      "timestamp": 1710000000
    }
  }
}
```

# 4.5 Funding Rate（资金费率）

```json
{
  "funding_rate": {
    "BTC": {
      "current": 0.0001,
      "next": 0.00012,
      "timestamp": 1710000000
    }
  }
}
```

# 📰 5. Events字段（事件数据）

# 5.1 新闻事件

```json
{
  "events": [
    {
      "id": "evt_001",
      "type": "news",
      "subtype": "regulatory",
      "source": "coindesk",
      "title": "SEC approves Bitcoin ETF",
      "content": "...",
      "sentiment": "bullish",
      "sentiment_score": 0.8,
      "impact": "high",
      "timestamp": 1710000000,
      "related_assets": ["BTC", "ETH"]
    }
  ]
}
```

# 5.2 宏观经济事件

```json
{
  "events": [
    {
      "id": "evt_002",
      "type": "macro",
      "subtype": "interest_rate",
      "title": "Fed meeting",
      "impact": "high",
      "timestamp": 1710000000,
      "related_assets": ["gold", "oil", "BTC"]
    }
  ]
}
```

# 5.3 交易所事件

```json
{
  "events": [
    {
      "id": "evt_003",
      "type": "exchange",
      "subtype": "maintenance",
      "source": "binance",
      "title": "Binance maintenance",
      "impact": "medium",
      "timestamp": 1710000000
    }
  ]
}
```

# 🎯 6. Signals字段（信号数据）

# 6.1 因子信号

```json
{
  "signals": {
    "factors": {
      "trend": 0.55,
      "flow": -0.2,
      "sentiment": -0.6,
      "macro": 0.3,
      "behavioral": 0.4,
      "historical": -0.1
    },
    "composite_score": 0.18,
    "regime": "RISK_OFF"
  }
}
```

# 6.2 风险信号

```json
{
  "signals": {
    "risk": {
      "risk_index": 72,
      "risk_level": "HIGH",
      "allow_trading": false,
      "max_position": 0.15,
      "max_leverage": 1
    }
  }
}
```

# 6.3 交易信号

```json
{
  "signals": {
    "trade": {
      "symbol": "BTC",
      "signal": "BUY",
      "confidence": 0.75,
      "action": "OPEN_LONG",
      "position_size": 0.2,
      "leverage": 2,
      "stop_loss": 2.0,
      "take_profit": 4.5
    }
  }
}
```

# 🔄 7. 完整TDP消息示例

# 7.1 数据采集消息

```json
{
  "version": "1.0",
  "timestamp": 1710000000,
  "mode": "LIVE",
  "meta": {
    "request_id": "data_001",
    "source": "data_service",
    "status": "OK"
  },
  "market": {
    "crypto": {
      "BTC": {
        "price": 68000.0,
        "open": 67500.0,
        "high": 68500.0,
        "low": 67000.0,
        "volume": 1234567.89,
        "change_24h": 0.025
      }
    },
    "commodities": {
      "gold": {"price": 2020.5, "change_percent_24h": 0.5},
      "oil": {"price": 78.3, "change_percent_24h": -0.3}
    },
    "etf": {
      "BTC": {
        "inflow_24h": 150000000,
        "outflow_24h": 80000000,
        "net_flow_24h": 70000000
      }
    }
  },
  "events": [
    {
      "id": "evt_001",
      "type": "news",
      "title": "BTC ETF approval",
      "sentiment": "bullish",
      "sentiment_score": 0.8
    }
  ]
}
```

# 7.2 因子计算消息

```json
{
  "version": "1.0",
  "timestamp": 1710000000,
  "mode": "LIVE",
  "meta": {
    "request_id": "factor_001",
    "source": "factor_service",
    "status": "OK"
  },
  "signals": {
    "factors": {
      "trend": 0.55,
      "flow": -0.2,
      "sentiment": -0.6,
      "macro": 0.3
    },
    "composite_score": 0.18,
    "regime": "RISK_OFF"
  }
}
```

# 🔧 8. TDP服务实现

# 8.1 TDP Server

```python
class TDPServer:
    def __init__(self):
        self.handlers = {}

    def register_handler(self, msg_type: str, handler: callable):
        self.handlers[msg_type] = handler

    def process_message(self, message: dict):
        validated = self.validate_message(message)
        handler = self.handlers.get(validated["type"])
        if handler:
            return handler(validated)
        raise TDPHandlerNotFoundError(f"No handler for {validated['type']}")

    def validate_message(self, message: dict) -> dict:
        if "version" not in message:
            raise TDPValidationError("Missing version")
        if message["version"] != TDP_VERSION:
            raise TDPVersionError("Version mismatch")
        return message
```

# 8.2 TDP Client

```python
class TDPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = requests.Session()

    def send_message(self, message: dict) -> dict:
        message["version"] = TDP_VERSION
        response = self.session.post(
            f"{self.server_url}/tdp/message",
            json=message,
            timeout=30
        )
        return response.json()

    def request_market_data(self, symbols: list, timeframe: str) -> dict:
        return self.send_message({
            "type": "market_data_request",
            "symbols": symbols,
            "timeframe": timeframe
        })

    def request_signal(self, signal_type: str) -> dict:
        return self.send_message({
            "type": "signal_request",
            "signal_type": signal_type
        })
```

# 📝 9. 消息类型定义

# 9.1 请求消息类型

```python
MESSAGE_TYPES_REQUEST = {
    "market_data_request": "请求市场数据",
    "factor_request": "请求因子计算",
    "risk_request": "请求风险计算",
    "signal_request": "请求交易信号",
    "position_request": "请求仓位查询",
    "execution_request": "请求订单执行",
    "config_request": "请求配置查询",
    "state_request": "请求状态查询"
}
```

# 9.2 响应消息类型

```python
MESSAGE_TYPES_RESPONSE = {
    "market_data_response": "市场数据响应",
    "factor_response": "因子计算响应",
    "risk_response": "风险计算响应",
    "signal_response": "交易信号响应",
    "position_response": "仓位查询响应",
    "execution_response": "订单执行响应",
    "config_response": "配置查询响应",
    "state_response": "状态查询响应"
}
```

# 9.3 事件消息类型

```python
MESSAGE_TYPES_EVENT = {
    "market_data_event": "市场数据事件",
    "signal_event": "信号生成事件",
    "order_event": "订单状态事件",
    "risk_alert_event": "风险告警事件",
    "system_event": "系统事件"
}
```

# ✅ 10. 验证规则

# 10.1 必填字段

```python
REQUIRED_FIELDS = {
    "market_data": ["version", "timestamp", "market"],
    "factor_request": ["version", "timestamp", "symbols"],
    "execution_request": ["version", "timestamp", "order"]
}
```

# 10.2 数据类型校验

```python
FIELD_TYPES = {
    "price": float,
    "volume": float,
    "timestamp": int,
    "sentiment_score": float,
    "change_percent": float
}
```

# 10.3 范围校验

```python
FIELD_RANGES = {
    "sentiment_score": (-1, 1),
    "change_percent": (-1, 1),
    "leverage": (1, 125),
    "position_size": (0, 1)
}
```

# 🗄️ 11. 存储设计

# 11.1 TDP消息日志表

```sql
CREATE TABLE tdp_messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    message_id VARCHAR(100) NOT NULL UNIQUE,
    message_type VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_message_type (message_type),
    INDEX idx_created_at (created_at)
);
```

# 🔐 12. 安全设计

# 12.1 消息签名

```python
import hmac
import hashlib

def sign_message(message: dict, secret: str) -> str:
    payload = json.dumps(message, sort_keys=True)
    signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def verify_signature(message: dict, signature: str, secret: str) -> bool:
    expected = sign_message(message, secret)
    return hmac.compare_digest(expected, signature)
```

# 12.2 加密传输

```python
from cryptography.fernet import Fernet

class TDPEncryption:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)

    def encrypt(self, message: dict) -> bytes:
        return self.cipher.encrypt(json.dumps(message).encode())

    def decrypt(self, encrypted: bytes) -> dict:
        return json.loads(self.cipher.decrypt(encrypted).decode())
```

# 🚀 13. 扩展方向

- 支持WebSocket实时推送
- 支持消息压缩
- 支持批量消息
- 支持消息路由
- 支持消息追踪
