# Schema 统一规范文档

## 📋 概述

本文档定义了系统中核心数据模型（`Candle`、`Trade`、`Timeframe`、`Exchange`）的统一规范，确保所有服务使用一致的数据定义，避免因 schema 不一致导致的 bug。

## 🎯 核心原则

### 1. 唯一真相源（SSOT）

```
shared/contracts/__init__.py  ← 系统唯一真相源
         ↓
所有服务从这里导入
```

### 2. 不重复定义

| ❌ 禁止 | ✅ 正确 |
|---------|--------|
| 在各服务中定义自己的 Candle | 从 shared.contracts 导入 |
| 维护多份 Timeframe Enum | 使用统一的 Timeframe |
| 使用字符串表示交易所 | 使用 Exchange Enum |

### 3. 类型一致性

- `exchange`: 必须使用 `Exchange` 类型，不能用字符串
- `timeframe`: 必须使用 `Timeframe` 类型
- `symbol`: 使用字符串，如 "BTCUSDT"
- 时间戳: 使用毫秒级 Unix 时间戳 (int)

---

## 📦 核心 Schema

### Exchange（交易所）

```python
from shared.contracts import Exchange

# 支持的交易所
Exchange.BINANCE   # "binance"
Exchange.OKX       # "okx"
Exchange.COINBASE  # "coinbase"
Exchange.KRAKEN    # "kraken"
Exchange.BYBIT     # "bybit"

# 使用示例
exchange = Exchange.BINANCE
print(exchange.value)  # "binance"
```

### Timeframe（时间周期）

```python
from shared.contracts import Timeframe

# 支持的时间周期
Timeframe.S1   # "1s"
Timeframe.M1   # "1m"
Timeframe.M5   # "5m"
Timeframe.M15  # "15m"
Timeframe.M30  # "30m"
Timeframe.H1   # "1h"
Timeframe.H4   # "4h"
Timeframe.D1   # "1d"
Timeframe.W1   # "1w"

# 属性
Timeframe.M5.seconds  # 300

# 从字符串创建
tf = Timeframe.from_string("5m")
```

### Candle（K线）

```python
from shared.contracts import Exchange, Timeframe, Candle

candle = Candle(
    exchange=Exchange.BINANCE,        # 必须是 Exchange 类型
    symbol="BTCUSDT",                  # 字符串
    timeframe=Timeframe.M5,           # 必须是 Timeframe 类型
    open_time=1700000000000,          # 毫秒时间戳
    close_time=1700000299999,
    open=50000.0,
    high=50100.0,
    low=49900.0,
    close=50050.0,
    volume=100.0,
    quote_volume=5000000.0,
    trade_count=50,
    is_closed=True,
    source="aggregated",
)

# 序列化
candle.to_dict()           # 返回 dict
candle.to_clickhouse_row() # 返回 ClickHouse 格式

# 反序列化
c2 = Candle.from_dict(data)

# 辅助方法
candle.is_bullish()         # 是否阳线
candle.is_bearish()        # 是否阴线
candle.get_body()          # 实体大小
candle.get_range()         # 波动范围
candle.canonical_symbol    # "BTC"
```

### Trade（成交）

```python
from shared.contracts import Exchange, Trade

trade = Trade(
    exchange=Exchange.BINANCE,
    symbol="BTCUSDT",
    timestamp=1700000000000,
    price=50000.0,
    quantity=0.5,
    quote_quantity=25000.0,
    is_buyer_maker=True,  # True=卖方主动
    trade_id="12345",
)

# 属性
trade.side                # "sell" 或 "buy"
trade.canonical_symbol    # "BTC"

# 序列化
trade.to_dict()
Trade.from_dict(data)
```

---

## 📁 导入规范

### ✅ 正确导入方式

```python
# 方式1: 直接从 shared.contracts 导入
from shared.contracts import Timeframe, Exchange, Candle, Trade

# 方式2: 从服务层导入（推荐用于业务逻辑）
from services.aggregation_service import Candle, Timeframe
from services.repair_service import GapInfo

# 方式3: 继承后扩展
from shared.contracts import Candle as ContractCandle

class MyCandle(ContractCandle):
    """业务层扩展"""
    pass
```

### ❌ 禁止的导入方式

```python
# 禁止: 在各服务中重新定义
class Candle:  # ❌ 错误
    pass

# 禁止: 使用字符串代替 Enum
exchange = "binance"  # ❌ 错误，应使用 Exchange.BINANCE

# 禁止: 使用字符串代替 Timeframe
timeframe = "5m"      # ❌ 错误，应使用 Timeframe.M5
```

---

## 🔧 服务层使用规范

### aggregation_service

```python
from services.aggregation_service.models.candle_model import Candle, CandleWindow, Timeframe

# CandleWindow 用于内存聚合
window = CandleWindow(
    exchange=Exchange.BINANCE,  # 使用 Exchange 类型
    symbol="BTCUSDT",
    timeframe=Timeframe.M5,
    bucket=1700000000000,
)
```

### repair_service

```python
from services.repair_service.models.repair_models import GapInfo, Timeframe

gap = GapInfo(
    exchange="binance",  # 可以用字符串
    symbol="BTCUSDT",
    timeframe=Timeframe.M5,
    gap_start=1700000000000,
    gap_end=1700000300000,
    missing_count=3,
)
```

---

## 🔄 数据流

```
原始数据 (API/WebSocket)
         ↓
data_service 收集
         ↓
StandardEvent 标准化
         ↓
aggregation_service 聚合
         ↓
Candle / Trade 统一格式
         ↓
  ┌─────┴─────┐
  ↓           ↓
Kafka      ClickHouse
(实时)     (历史)
  ↓           ↓
  └─────┬─────┘
        ↓
  fusion_service
        ↓
   Signal 生成
```

---

## 🧪 测试验证

```python
import sys
sys.path.insert(0, '.')

from shared.contracts import Timeframe, Exchange, Candle, Trade
from services.aggregation_service import Candle, Timeframe, Trade

# 验证导入一致性
c = Candle(
    exchange=Exchange.BINANCE,
    symbol='BTCUSDT',
    timeframe=Timeframe.M5,
    open_time=1000000,
    close_time=1000300,
    open=50000.0,
    high=50100.0,
    low=49900.0,
    close=50050.0,
    volume=100.0
)

assert c.to_dict()['timeframe'] == '5m'
assert Timeframe.M5.seconds == 300
print("✅ Schema 一致性验证通过")
```

---

## 📝 变更记录

### 2024-01-01

- 初始版本
- 统一 Candle/Trade/Timeframe/Exchange 定义
- aggregation_service 作为唯一真相层
