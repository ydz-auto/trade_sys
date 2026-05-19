# 数据湖 (Data Lake)

统一的历史数据存储层，支持 Binance 和 OKX 交易所。

## 目录结构

```
backend/data_lake/
  crypto/
    binance/
      klines/       # K线数据
      funding/      # 资金费率
      oi/           # 持仓量
      trades/       # 成交数据 (可选，数据量大)
      liquidation/  # 强平数据 (仅实时WebSocket)
    
    okx/
      klines/
      funding/
      oi/
      trades/
      liquidation/
```

## 数据格式

所有数据统一使用 **Parquet + ZSTD** 压缩格式存储。

### K线 Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | datetime64 | 时间戳 |
| exchange | string | 交易所 (binance/okx) |
| symbol | string | 交易对 |
| interval | string | K线周期 |
| open | float64 | 开盘价 |
| high | float64 | 最高价 |
| low | float64 | 最低价 |
| close | float64 | 收盘价 |
| volume | float64 | 成交量 |

### Funding Rate Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | datetime64 | 时间戳 |
| exchange | string | 交易所 |
| symbol | string | 交易对 |
| funding_rate | float64 | 资金费率 |

### Open Interest Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | datetime64 | 时间戳 |
| exchange | string | 交易所 |
| symbol | string | 交易对 |
| sum_open_interest | float64 | 持仓量 |

## 使用方法

### 初始化

```bash
cd backend
python scripts/data_lake_download.py --init
```

### 下载数据

```bash
# 下载 Binance K线
python scripts/data_lake_download.py --binance-klines --symbols BTCUSDT ETHUSDT --years 2024 2025

# 下载 Binance Funding Rate
python scripts/data_lake_download.py --binance-funding --symbols BTCUSDT ETHUSDT --years 2024 2025

# 下载 Binance OI
python scripts/data_lake_download.py --binance-oi --symbols BTCUSDT ETHUSDT --years 2024 2025

# 下载 Binance 全部 (不含 trades)
python scripts/data_lake_download.py --binance-klines --binance-funding --binance-oi --symbols BTCUSDT ETHUSDT SOLUSDT ZECUSDT --years 2024 2025 2026

# 下载 OKX 全部 (不含 trades)
python scripts/data_lake_download.py --okx-klines --okx-funding --okx-oi --symbols BTCUSDT ETHUSDT SOLUSDT ZECUSDT --years 2024 2025 2026

# 下载全部数据
python scripts/data_lake_download.py --all --symbols BTCUSDT ETHUSDT SOLUSDT ZECUSDT --years 2024 2025 2026
```

### 实时 Liquidation 订阅

```bash
# Binance (仅支持实时)
python scripts/download_binance_liquidation.py --realtime --duration 24

# OKX
python scripts/data_lake_download.py --okx-liquidation --symbols BTC-USDT-SWAP
```

## 数据来源

| 数据类型 | Binance | OKX |
|---------|---------|-----|
| K线 | Data Vision ZIP | REST API |
| Funding | REST API | REST API |
| OI | REST API | REST API |
| Trades | Data Vision ZIP | REST API |
| Liquidation | WebSocket | REST API |

## 存储估算

### 10年数据 (4交易对)

| 数据类型 | 估算大小 |
|----------|----------|
| K线 | ~1 GB |
| Funding | ~4 MB |
| OI | ~200 MB |
| Trades | ~50-100 GB (可选) |
| **总计 (不含Trades)** | **~1.2 GB** |

## 读取数据

```python
import pandas as pd
from pathlib import Path

# 读取 K线
df = pd.read_parquet('data_lake/crypto/binance/klines/symbol=BTCUSDT/year=2024/month=01/data.parquet')

# 按时间范围读取
import pyarrow.parquet as pq

dataset = pq.ParquetDataset('data_lake/crypto/binance/klines/')
table = dataset.read(filters=[('symbol', '=', 'BTCUSDT')])
df = table.to_pandas()
```

## 脚本列表

| 脚本 | 功能 |
|------|------|
| data_lake_download.py | 统一入口 |
| download_binance_klines.py | Binance K线 |
| download_binance_funding.py | Binance Funding |
| download_binance_oi.py | Binance OI |
| download_binance_trades.py | Binance Trades |
| download_binance_liquidation.py | Binance Liquidation (实时) |
| download_okx_klines.py | OKX K线 |
| download_okx_funding.py | OKX Funding |
| download_okx_oi.py | OKX OI |
| download_okx_trades.py | OKX Trades |
| download_okx_liquidation.py | OKX Liquidation |

## 注意事项

1. **Trades 数据量大**: 每月约 1GB/交易对，谨慎下载
2. **API 限流**: 脚本已内置限流处理
3. **断点续传**: 已下载的数据会自动跳过
4. **时间范围**: Binance Data Vision 提供历史数据，OKX 需要通过 REST API 逐页获取
