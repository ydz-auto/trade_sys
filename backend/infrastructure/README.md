# TradeAgent Infrastructure

基础设施模块，提供日志、监控、数据库、缓存、API网关、告警等基础设施服务。

## 模块结构

```
infrastructure/
├── alerting/          # 告警系统
│   ├── channels.py    # 告警渠道 (Telegram/Email/SMS/Webhook)
│   ├── config.py      # 告警配置
│   ├── rules.py       # 告警规则引擎
│   └── sender.py      # 告警发送器
├── api_gateway/       # API 网关
│   ├── config.py      # 网关配置
│   ├── exceptions.py  # API 异常定义
│   ├── middleware.py  # 中间件 (Auth/RateLimit/CORS/Logger)
│   ├── response.py    # 响应格式化
│   ├── router.py      # 路由管理
│   └── security.py    # 认证授权 (APIKey/JWT/Permission)
├── cache/             # 缓存模块
│   ├── cache_manager.py    # 缓存管理器
│   ├── circuit_breaker.py  # 熔断器
│   ├── config.py           # 缓存配置
│   ├── keys.py             # 缓存 Key 工具
│   └── redis_client.py     # Redis 客户端
├── database/          # 数据库模块
│   ├── clickhouse.py       # ClickHouse 管理器
│   ├── configs.py          # 数据库配置
│   ├── connection_pool.py  # 连接池
│   ├── enums.py            # 数据库枚举
│   ├── postgresql.py       # PostgreSQL 管理器
│   └── schemas/            # 数据表结构
├── logging/            # 日志系统
│   ├── config.py           # 日志配置
│   ├── context.py          # 日志上下文
│   ├── formatters.py       # 格式化器 (JSON/Text)
│   ├── handlers.py         # 处理器 (File/Console/ES)
│   └── logger.py           # 日志工厂
├── middleware/         # 中间件
│   ├── config.py           # 中间件配置
│   └── kafka.py            # Kafka 生产者/消费者
└── monitoring/          # 监控系统
    ├── alert.py            # 告警管理
    ├── config.py           # 监控配置
    ├── dashboard.py        # 监控面板
    ├── health.py           # 健康检查
    └── metrics.py          # 指标收集
```

## 核心功能

| 模块 | 功能 |
|------|------|
| **cache** | Redis 缓存、缓存管理器、熔断机制 |
| **database** | PostgreSQL/ClickHouse 连接池管理 |
| **logging** | 统一日志、JSON/Text 格式化、ES 输出 |
| **monitoring** | 健康检查、Metrics 采集、监控面板 |
| **alerting** | 多渠道告警 (Telegram/Email/SMS/Webhook) |
| **api_gateway** | 路由、认证、限流、CORS、请求日志 |
| **middleware** | Kafka 消息队列集成 |

## 快速使用

```python
from infrastructure import (
    LoggerFactory,
    get_redis_client,
    get_postgres_manager,
    HealthChecker,
    Router,
)

# 日志
logger = LoggerFactory.get_logger(__name__)

# 缓存
redis = get_redis_client()

# 数据库
pg = get_postgres_manager()

# 健康检查
health = HealthChecker()
```
