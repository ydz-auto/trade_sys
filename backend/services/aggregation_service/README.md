# Aggregation Service - K线聚合服务

## 📊 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Data Service (事实层)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  Binance    │  │    OKX      │  │   Exchange   │                │
│  │  WebSocket  │  │  WebSocket  │  │    APIs     │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Aggregation Service ⭐                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │  Candle        │  │  Trade         │  │  OrderBook    │           │
│  │  Aggregator    │  │  Aggregator    │  │  Aggregator   │           │
│  │                │  │                │  │               │           │
│  │  1m → 5m      │  │  trade → 1s   │  │  snapshot →  │           │
│  │  1m → 15m     │  │                │  │  features     │           │
│  │  1m → 1h      │  │                │  │               │           │
│  └────────────────┘  └────────────────┘  └────────────────┘           │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                    State Manager                                  │   │
│  │  ┌──────────────────────┐  ┌──────────────────────┐              │   │
│  │  │  Window State (内存) │  │  Checkpoint (Redis)  │              │   │
│  │  └──────────────────────┘  └──────────────────────┘              │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           输出层                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │    Kafka     │  │  ClickHouse  │  │    Redis    │                │
│  │  (实时流)    │  │  (历史存储)   │  │  (Checkpoint)│                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
aggregation_service/
├── models/
│   ├── candle_model.py        # K线数据模型
│   ├── trade_model.py         # 成交数据模型
│   └── orderbook_model.py     # 订单簿数据模型
│
├── aggregators/
│   ├── candle/
│   │   └── candle_aggregator.py  # K线聚合器
│   ├── trade/
│   │   └── trade_aggregator.py   # 成交转K线聚合器
│   └── orderbook/
│       └── orderbook_aggregator.py  # 订单簿聚合器
│
├── consumers/                  # Kafka 消费者
├── state/
│   └── state_manager.py        # 窗口状态管理
├── publishers/
│   ├── kafka_publisher.py     # Kafka 发布器
│   └── clickhouse_writer.py   # ClickHouse 写入器
├── replay/
│   └── replay_runner.py       # 回放器
├── main.py                     # 主入口
└── README.md
```

---

## 🎯 核心职责

| 职责 | 说明 |
|------|------|
| 1m → 5m/15m/1h | 直接从 closed 1m 生成高周期K线 |
| trade → 1s candle | 将原始成交聚合为1秒K线 |
| orderbook → feature | 从订单簿快照提取特征 |
| 时间对齐 | 统一 UTC 时间桶 |
| 缺失检测 | 检测缺K并标记 |
| checkpoint | Redis 保存窗口状态 |
| replay | 从原始数据重新生成 |

---

## 🚫 不负责

| ❌ 不负责 | 原因 |
|----------|------|
| Feature 计算 | 属于 feature_service |
| Factor 计算 | 属于 factor_service |
| Signal | 属于 fusion_service |
| LLM | 属于 event_service |

---

## 🔥 核心设计原则

### 1. 唯一真相层

| 数据 | 真相 |
|------|------|
| 高周期K线 | 1m |
| 1m | 1s |
| 1s | trade |

### 2. 不链式聚合

```text
❌ 错误：5m → 15m → 1h
✅ 正确：1m → 5m, 1m → 15m, 1m → 1h
```

### 3. UTC 时间对齐

```python
bucket = ts - (ts % timeframe_ms)
```

---

## 🔌 使用示例

### 1. 处理 K线

```python
from services.aggregation_service.main import get_aggregation_service

service = await get_aggregation_service()

candle_data = {
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "open_time": 1715500000000,
    "close_time": 1715500059999,
    "open": 100000,
    "high": 101000,
    "low": 99000,
    "close": 100500,
    "volume": 100,
    "is_closed": True
}

aggregated = await service.process_candle(candle_data)
print(f"Aggregated to: {[c.timeframe for c in aggregated]}")
```

### 2. 处理成交

```python
trade_data = {
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "trade_id": "12345",
    "price": 100500,
    "quantity": 0.5,
    "quote_quantity": 50250,
    "timestamp": 1715500005000,
    "is_buyer_maker": False
}

candle = await service.process_trade(trade_data)
```

### 3. Replay

```python
from services.aggregation_service.replay import run_replay

await run_replay(
    exchange="binance",
    symbol="BTCUSDT",
    start_time=1704067200000,  # 2024-01-01
    end_time=1711929600000,   # 2024-04-01
    source_timeframe="1m"
)
```

---

## 📊 Kafka Topic

### 输入

```text
raw.trade.binance
raw.kline.binance.1m.closed
raw.orderbook.binance.snapshot
```

### 输出

```text
kline.binance.1s
kline.binance.1m
kline.binance.5m
kline.binance.15m
kline.binance.1h
kline.binance.4h
kline.binance.1d
orderbook.binance.feature
```

---

## 📈 ClickHouse 表

```sql
CREATE TABLE candles (
    exchange String,
    symbol String,
    timeframe String,
    open_time UInt64,
    open_time_dt DateTime,
    close_time UInt64,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    quote_volume Float64,
    trade_count UInt32,
    is_closed UInt8,
    is_complete UInt8,
    missing_count UInt16
)
ENGINE = ReplacingMergeTree()
ORDER BY (exchange, symbol, timeframe, open_time)
```

---

## 🔧 Redis Checkpoint

```text
agg:checkpoint:binance:BTCUSDT:5m
```

保存内容：

```json
{
    "bucket": 1715500000000,
    "state": {"open": 100000, "high": 101000},
    "timestamp": 1715500100
}
```

---

## 📚 相关文档

- [repair_service/README.md](../repair_service/README.md) - 修复服务
- [Topic System](../../infrastructure/messaging/topics.py) - 分层 Topic 体系
- [ClickHouse Setup](../../infrastructure/database/clickhouse.py) - ClickHouse 配置
