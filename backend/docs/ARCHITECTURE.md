"""
System Architecture Documentation
系统架构文档
"""

# 系统架构

## 概述

本系统是一个加密货币交易代理平台，采用微服务架构设计，具有以下核心能力：
- 数据采集与聚合
- 信号生成与回测
- 订单执行与管理
- 数据质量监控与自动修复

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        External APIs                             │
│              (Binance, OKX, CoinGecko, etc.)                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Ingestion Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  WebSocket   │  │    REST      │  │   Kafka      │          │
│  │   Client     │  │   Client     │  │   Consumer   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Aggregation Service (SSOT)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Candle Aggregator                           │  │
│  │   1m → 5m → 15m → 1h → 4h → 1d                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Trade Processor                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  ClickHouse  │  │    Redis     │  │   Kafka      │          │
│  │  (TimeSeries)│  │   (Cache)    │  │  (Events)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Processing Services                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Signal    │  │  Execution   │  │   Repair     │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Fusion     │  │   Strategy   │  │   Backtest   │          │
│  │   Service    │  │   Service    │  │   Engine     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Shared Infrastructure                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Contracts (Candle, Trade, Signal, Timeframe, Exchange)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │  Replay/   │ │Idempotency │ │  Service   │ │ Permission │  │
│  │  Rebuild   │ │   Manager  │ │  Registry  │ │  Manager   │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │Observability│ │Data Quality│ │   Cache    │ │Auto Repair │  │
│  │   Module   │ │  Checker   │ │   Module   │ │   Engine   │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. shared.contracts
统一的数据契约定义，作为系统的唯一真相源。

```python
from shared.contracts import Candle, Trade, Signal, Timeframe, Exchange

candle = Candle(
    exchange=Exchange.BINANCE,
    symbol="BTCUSDT",
    timeframe=Timeframe.M5,
    open_time=1700000000000,
    ...
)
```

### 2. shared.replay
回放重建系统，支持历史数据回放和数据修复。

```python
from shared.replay import get_replay_orchestrator

orchestrator = await get_replay_orchestrator()
task = await orchestrator.create_replay_task(...)
await orchestrator.start_replay(task.task_id)
```

### 3. shared.idempotency
幂等性管理，确保操作不会被重复执行。

```python
from shared.idempotency import get_idempotency_manager

idempotency = await get_idempotency_manager()
can_execute, existing = await idempotency.check_and_lock(
    operation_type="order",
    operation_key="unique_order_id",
)
```

### 4. shared.service_registry
去中心化服务注册与发现。

```python
from shared.service_registry import get_service_registry

registry = get_service_registry()
service_id = await registry.register(
    service_name="aggregation_service",
    version="1.0.0",
    endpoints=[ServiceEndpoint(host="localhost", port=8080)],
)
```

### 5. shared.permission
基于角色的访问控制 (RBAC)。

```python
from shared.permission import get_permission_manager, PermissionAction

permission = get_permission_manager()
await permission.assign_role("user_001", "operator")
can_write = await permission.check_permission(
    "user_001",
    PermissionAction.WRITE,
    "api_key",
    "config",
)
```

### 6. shared.observability
可观测性模块，提供指标、追踪和健康检查。

```python
from shared.observability import get_observability_manager

observability = get_observability_manager("my_service")
observability.record_request("/api/candles", "GET", 200, 45.5)
span = observability.start_operation("process_candle")
# ... do work ...
observability.end_operation(span, success=True)
```

### 7. shared.data_quality
数据质量检测，支持完整性、准确性、一致性检查。

```python
from shared.data_quality import CandleDataQualityChecker

checker = CandleDataQualityChecker()
quality = checker.check_candles(candles)
print(f"Status: {quality.status}, Completeness: {quality.completeness}")
```

### 8. shared.cache
多级缓存和异步批处理。

```python
from shared.cache import get_cache, cached

cache = get_cache()
await cache.set("key", value, ttl=300)
value = await cache.get("key")

@cached(ttl=60)
async def expensive_operation():
    ...
```

### 9. shared.backtest
信号回测引擎。

```python
from shared.backtest import BacktestEngine, BacktestConfig

engine = BacktestEngine(BacktestConfig(initial_capital=10000))
engine.set_strategy(my_strategy)
result = await engine.run(candles, strategy_name="my_strategy")
print(f"Return: {result.total_return:.2%}, Sharpe: {result.sharpe_ratio:.2f}")
```

### 10. shared.auto_repair
自动修复引擎。

```python
from shared.auto_repair import get_auto_repair_engine

engine = await get_auto_repair_engine()
results = await engine.analyze_and_repair(data)
```

## 数据流

```
Exchange API → WebSocket/REST → Kafka → Aggregation Service
                                              │
                                              ▼
                                         ClickHouse
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
            Signal Service           Execution Service          Repair Service
                    │                         │                         │
                    ▼                         ▼                         ▼
            Strategy Engine           Order Manager              Gap Detector
                    │                         │                         │
                    ▼                         ▼                         ▼
               Signals                   Orders                    Repairs
```

## 配置

系统配置通过 `shared.config` 模块管理，支持：
- 多环境配置
- 热更新
- 版本控制
- 敏感值保护

## 监控

系统提供完整的可观测性支持：
- **指标**: Prometheus 格式
- **追踪**: OpenTelemetry 兼容
- **健康检查**: `/health` 端点
- **监控面板**: `/api/dashboard/*`

## 部署

支持多种部署方式：
- Docker Compose (开发)
- Kubernetes (生产)
- 单机部署 (测试)

## 扩展

添加新服务的步骤：
1. 在 `services/` 下创建新目录
2. 定义服务接口和实现
3. 注册到服务注册中心
4. 添加健康检查
5. 配置监控指标
