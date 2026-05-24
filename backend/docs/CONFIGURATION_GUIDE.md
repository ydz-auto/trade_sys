# 配置系统规范

## 配置系统架构

项目采用**三层配置架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                    配置系统架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ConfigService (动态配置 - Redis)                     │   │
│  │ - 需要前端修改的配置                                  │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ • API URL (交易所、LLM、新闻源)                       │   │
│  │ • API Key (加密存储)                                 │   │
│  │ • 策略参数 (权重配置)                                │   │
│  │ • LLM Provider 配置                                  │   │
│  │ • 交易所配置                                         │   │
│  │ • 新闻源配置                                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ConfigManager (静态配置 - YAML)                      │   │
│  │ - 不需要前端修改的配置                                │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ • Kafka/Redis/DB 连接配置                            │   │
│  │ • 功能开关                                           │   │
│  │ • Runtime 配置                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 环境变量 (.env)                                      │   │
│  │ - 敏感信息，不提交版本控制                            │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ • 数据库密码                                         │   │
│  │ • JWT 密钥                                           │   │
│  │ • 加密密钥                                           │   │
│  │ • API Key (作为 ConfigService 的回退)                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 配置项归属划分

### 1. ConfigService (动态配置)

**适用场景**：需要前端动态修改，运行时生效

| 类别 | Redis Key | 说明 |
|------|-----------|------|
| **API Keys** | `config:api_keys` | 加密存储的 API 密钥 |
| **API URL** | `config:api_urls` | 交易所、LLM、新闻源 API 地址 |
| **策略参数** | `config:strategy` | 策略权重配置 |
| **LLM 配置** | `config:llm` | LLM Provider 配置 |
| **交易所配置** | `config:exchanges` | 交易所 API Key + 设置 |
| **新闻源** | `config:news_sources` | 新闻源配置 |
| **数据源** | `config:data_sources` | 数据源配置 |

**存储位置**：Redis

**访问方式**：
```python
from shared.config import get_config, get_exchange_credentials, get_llm_credentials

# 获取交易所配置
config = await get_exchange_credentials("binance")
# {'api_key': 'xxx', 'secret': 'xxx', 'api_url': 'https://api.binance.com', 'testnet': false}

# 获取 LLM 配置
config = await get_llm_credentials("openai")
# {'api_key': 'sk-xxx', 'model': 'gpt-4', 'api_url': 'https://api.openai.com/v1'}

# 获取策略参数
weight = await get_config("strategy.momentum_weight")
```

---

### 2. ConfigManager (静态配置)

**适用场景**：应用启动时确定，运行期间不需要修改

| 类别 | 配置项 | 说明 |
|------|--------|------|
| **基础设施** | `kafka.*` | Kafka 连接配置 |
| | `redis.*` | Redis 连接配置 |
| | `clickhouse.*` | ClickHouse 连接配置 |
| | `postgresql.*` | PostgreSQL 连接配置 |
| **功能开关** | `features.*` | 功能开关配置 |
| **运行时** | `runtime.*` | Runtime 配置 |

**存储位置**：
- `config/environments/{env}.yaml` - 环境配置
- `config/infra/infra.yaml` - 基础设施配置

**访问方式**：
```python
from shared.config import get_config_manager

config = get_config_manager()
kafka_servers = config.get("kafka.bootstrap_servers")
```

---

### 3. 环境变量 (敏感信息)

**适用场景**：敏感信息，不提交到版本控制

| 类别 | 环境变量 | 说明 |
|------|----------|------|
| **数据库密码** | `POSTGRES_PASSWORD` | PostgreSQL 密码 |
| | `CLICKHOUSE_PASSWORD` | ClickHouse 密码 |
| | `REDIS_PASSWORD` | Redis 密码 |
| **安全密钥** | `JWT_SECRET_KEY` | JWT 签名密钥 |
| | `CONFIG_ENCRYPTION_KEY` | 配置加密密钥 |
| **API Keys (回退)** | `BINANCE_API_KEY` | Binance API Key |
| | `OPENAI_API_KEY` | OpenAI API Key |

**存储位置**：`.env` 文件（不提交）

**优先级**：ConfigService > 环境变量 > 默认值

---

## 配置获取优先级

```
┌─────────────────────────────────────────────────────────────┐
│                    配置获取优先级                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. ConfigService (Redis)                                   │
│     └─ 用户在前端配置的值                                    │
│                                                             │
│  2. 环境变量 (.env)                                          │
│     └─ 系统管理员配置的环境变量                              │
│                                                             │
│  3. 代码默认值                                               │
│     └─ shared/config/defaults/ 中的默认值                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 示例：获取 Binance API URL

```python
async def get_binance_api_url():
    # 1. ConfigService (用户自定义)
    service = get_config_service()
    config = await service.get_exchange_config("binance")
    if config and config.get("api_url"):
        return config["api_url"]
    
    # 2. 环境变量
    url = os.environ.get("BINANCE_SPOT_API_URL")
    if url:
        return url
    
    # 3. 默认值
    from shared.config.defaults.infrastructure.external_apis import BINANCE_REST_API
    return BINANCE_REST_API  # "https://api.binance.com"
```

---

## 配置使用规范

### 1. 选择正确的配置系统

```
需要前端修改？ ──是──> ConfigService (Redis)
     │
     否
     │
     ▼
是敏感信息？ ──是──> 环境变量 (.env)
     │
     否
     │
     ▼
ConfigManager (YAML)
```

### 2. 敏感信息处理

**✅ 正确做法**：
```python
# API Key 存储到 ConfigService（加密）
await service.create_api_key({
    "provider": "binance",
    "api_key": "xxx",
    "secret": "xxx"
})

# 服务使用时获取解密后的值
config = await get_exchange_credentials("binance")
```

**❌ 错误做法**：
```python
# 不要硬编码 API Key
api_key = "sk-xxxx"

# 不要明文存储到 Redis
await redis.set("binance_key", "xxx")
```

---

## 前端配置 API

### API Keys 管理

```http
# 创建 API Key
POST /api/v1/config/api-keys
{
    "name": "Binance Main",
    "provider": "binance",
    "type": "exchange",
    "api_key": "your-api-key",
    "secret": "your-secret"
}

# 获取 API Key 列表
GET /api/v1/config/api-keys

# 删除 API Key
DELETE /api/v1/config/api-keys/{key_id}
```

### LLM 配置

```http
# 获取 LLM 配置
GET /api/v1/config/llm-config

# 更新 LLM 配置
PUT /api/v1/config/llm-config
{
    "default_provider": "openai",
    "providers": {
        "openai": {"model": "gpt-4", "api_key_id": "uuid"},
        "zhipu": {"model": "glm-4-flash", "api_key_id": "uuid"}
    }
}
```

### 交易所配置

```http
# 获取交易所配置
GET /api/v1/config/exchanges/binance

# 更新交易所配置
PUT /api/v1/config/exchanges/binance
{
    "api_url": "https://api.binance.com",
    "testnet": false,
    "market_type": "futures"
}
```

### 策略配置

```http
# 获取策略配置
GET /api/v1/config/strategy

# 更新策略配置
PUT /api/v1/config/strategy
{
    "momentum_weight": 0.3,
    "trend_weight": 0.3,
    "flow_weight": 0.2,
    "sentiment_weight": 0.2
}
```

---

## 配置文件清单

| 文件 | 用途 | 提交版本控制 |
|------|------|-------------|
| `config/environments/*.yaml` | 环境配置 | ✅ 是 |
| `config/infra/infra.yaml` | 基础设施配置 | ✅ 是 |
| `.env` | 敏感信息 | ❌ 否 |
| `.env.example` | 配置模板 | ✅ 是 |
| Redis `config:*` | 动态配置 | N/A |

---

## 迁移指南

### 从硬编码迁移到 ConfigService

**Before**:
```python
BASE_URL = "https://api.binance.com"
api_key = os.environ.get("BINANCE_API_KEY")
```

**After**:
```python
from shared.config import get_exchange_credentials

async def get_binance_client():
    config = await get_exchange_credentials("binance")
    return BinanceClient(
        api_url=config.get("api_url", "https://api.binance.com"),
        api_key=config.get("api_key"),
        secret=config.get("secret"),
    )
```
