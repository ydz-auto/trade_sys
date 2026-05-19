# OrderBook 特征提取指南

## 概述

已创建完整的订单簿特征提取系统，支持从 Binance 实时获取订单簿和成交数据，提取 44 个高价值特征。

## 数据限制说明

**重要**: Binance 不提供历史订单簿数据的 API 下载。只有：

- ✅ **实时订单簿**: 通过 WebSocket 可实时获取
- ✅ **历史成交数据**: 可通过 REST API 获取（但只能提取交易流特征）
- ❌ **历史订单簿**: Binance 不提供

## 使用方法

### 1. 实时采集（推荐）

从现在开始实时采集订单簿和成交数据：

```bash
# 采集 BTCUSDT 和 ETHUSDT，持续 1 小时
python scripts/extract_orderbook_features.py \
  --symbols BTCUSDT ETHUSDT \
  --duration 3600 \
  --output data_lake/orderbook_features

# 持续采集（无时间限制）
python scripts/extract_orderbook_features.py \
  --symbols BTCUSDT ETHUSDT \
  --output data_lake/orderbook_features

# 后台运行采集
nohup python scripts/extract_orderbook_features.py \
  --symbols BTCUSDT ETHUSDT \
  --output data_lake/orderbook_features \
  > orderbook_collection.log 2>&1 &
```

### 2. 批量处理历史成交数据

从 Binance API 获取历史成交数据并提取交易流特征：

```bash
# 提取过去一年的 BTCUSDT 成交特征
python scripts/batch_extract_orderbook_features.py \
  --symbol BTCUSDT \
  --start-date 2024-05-19 \
  --end-date 2025-05-19 \
  --output data_lake/orderbook_features

# 注意：只能提取交易流相关的特征，订单簿失衡等特征为估算值
```

### 3. 测试 WebSocket 连接

```bash
python scripts/test_websocket_connection.py
```

## 输出位置

所有特征数据存储在：`data_lake/orderbook_features/`

目录结构：
```
data_lake/orderbook_features/
├── binance/
│   ├── BTCUSDT/
│   │   ├── date=20260519/
│   │   │   └── features.parquet
│   │   └── date=20260520/
│   │       └── features.parquet
│   └── ETHUSDT/
│       └── date=20260519/
│           └── features.parquet
```

## 存储估算

| 配置 | 估算 |
|------|------|
| 频率 | 1秒快照 |
| 交易对 | BTC + ETH |
| 字段数 | 44个 |
| 压缩 | Parquet + zstd |
| 每天 | ~100 MB |
| 每月 | ~3 GB |
| 每年 | ~36 GB |

**注意**: 仍在你的 70G 预算内！

## 获取历史订单簿数据的替代方案

如果需要过去一年的完整订单簿数据，考虑以下付费服务：

1. **CoinAPI**: https://www.coinapi.io/
   - 提供完整的历史订单簿数据
   - 支持 Binance, Coinbase, Kraken 等
   
2. **CryptoAPIs**: https://cryptoapis.io/
   - 历史市场数据
   - RESTful API

3. **Binance Historical Data (付费版)**:
   - Binance 提供部分历史数据下载

## 数据使用示例

```python
import pandas as pd

# 读取特征数据
df = pd.read_parquet('data_lake/orderbook_features/binance/BTCUSDT/date=20260519/features.parquet')

# 查看数据结构
print(df.columns.tolist())

# 基础统计
print(df[['spread', 'imbalance_10', 'trade_delta', 'vwap']].describe())

# 分析买卖失衡
print(f"平均失衡: {df['imbalance_10'].mean():.4f}")
print(f"买盘占优比例: {(df['imbalance_10'] > 0).mean():.2%}")

# 分析大单
print(f"大单占比: {df['large_trade_ratio'].mean():.4f}")
```

## 监控采集状态

查看日志：
```bash
tail -f orderbook_collection.log
```

查看存储统计：
```python
from services.aggregation_service.publishers.parquet_writer import get_parquet_writer

writer = get_parquet_writer()
stats = writer.get_storage_stats()
print(stats)
```
