# Binance 数据对比表

## 核心数据可用性对比

| 数据类型 | 官方历史下载 | 数据格式 | 压缩 | 大致数据量（BTCUSDT） | 备注 |
|---------|------------|---------|-----|---------------------|------|
| **Trades (成交记录)** | ✅ **提供** | CSV | ✅ 官方Zip (按月打包) | ~3-5 GB/年 | 包含：价格、数量、买卖方向、时间戳 |
| **K线 (Klines)** | ✅ **提供** | CSV | ✅ 官方Zip | ~100-200 MB/年 | 按分钟/小时等聚合 |
| **Order Book (订单簿)** | ❌ **不提供** | JSON (仅实时) | ❌ 无 | 需自己存 | 实时快照，Binance不提供历史 |
| **Open Interest (持仓量)** | ✅ **提供** | CSV | ✅ 官方Zip | ~5-10 MB/年 | 每小时/每天聚合 |
| **Funding Rate (资金费率)** | ✅ **提供** | CSV | ✅ 官方Zip | ~2-5 MB/年 | 每8小时 |
| **Liquidation (爆仓)** | ✅ **提供** | CSV | ✅ 官方Zip | ~10-50 MB/年 | 按日/月 |

---

## Trades 数据详细说明

### 下载地址
```
https://data.binance.vision/data/futures/um/monthly/trades/
```

### 文件结构
```
BTCUSDT-trades-2024-01.zip
  └── BTCUSDT-trades-2024-01.csv
      ├── id: 成交ID
      ├── price: 价格
      ├── qty: 数量
      ├── quote_qty: 成交额（USD）
      ├── time: 时间戳（ms）
      └── is_buyer_maker: 买方做市（False=主动买, True=主动卖）
```

### 可提取的 Trade 特征
| 特征 | 说明 | 价值 |
|------|------|------|
| `trade_delta` | 主动买卖量差 | ⭐⭐⭐⭐⭐ |
| `cumulative_delta` | 累积主动流 | ⭐⭐⭐⭐⭐ |
| `aggressive_buy_volume` | 主动买量 | ⭐⭐⭐⭐⭐ |
| `aggressive_sell_volume` | 主动卖量 | ⭐⭐⭐⭐⭐ |
| `vwap` | 成交量加权均价 | ⭐⭐⭐⭐⭐ |
| `large_trade_ratio` | 大单占比 | ⭐⭐⭐⭐ |
| `buy_sell_ratio` | 买卖比例 | ⭐⭐⭐⭐ |
| `trade_intensity` | 交易强度 | ⭐⭐⭐ |
| `price_impact` | 价格冲击 | ⭐⭐⭐ |
| `avg_trade_size` | 平均单笔成交量 | ⭐⭐⭐ |

### 可估算的 Order Book 特征
| 特征 | 说明 | 精度 |
|------|------|------|
| `imbalance_1/5/10` | 订单簿失衡 | ⭐⭐⭐（基于成交流向估算） |
| `spread` | 点差 | ⭐⭐（基于VWAP估算） |
| `depth_ratio` | 深度比率 | ⭐⭐ |
| `book_pressure` | 订单簿压力 | ⭐⭐⭐ |

---

## 存储方案对比

| 方案 | 适用数据 | 存储格式 | 压缩 | 示例大小（1年BTCUSDT） |
|------|---------|---------|-----|---------------------|
| **原始 Trades** | Trades历史数据 | Parquet + zstd | 高 | ~3-5 GB |
| **提取后特征** | 1秒聚合特征 | Parquet + zstd | 极高 | ~1-2 GB |
| **混合方案** | Trades + 特征 | 分开存储 | 高 | ~4-7 GB |

---

## 数据下载策略

### 阶段1：下载历史Trades（已准备）
```bash
python scripts/download_binance_trades.py --symbols BTCUSDT ETHUSDT --years 2024 2025 2026
```

### 阶段2：提取特征（已准备）
```bash
python scripts/extract_features_from_trades.py --symbols BTCUSDT ETHUSDT --years 2024 2025 2026
```

### 阶段3：实时采集（可选）
```bash
python scripts/extract_orderbook_features.py --symbols BTCUSDT ETHUSDT
```

---

## 数据量估算表

### BTCUSDT - 过去一年数据量

| 数据类型 | 频率 | 记录数 | 存储大小 |
|---------|-----|-------|--------|
| **Trades** | 实时 | ~100-300M | ~3-5 GB |
| **提取后特征** | 1秒 | ~31,536,000 | ~1-2 GB |
| **K线** | 1分钟 | ~525,600 | ~100 MB |
| **持仓量** | 1小时 | ~8,760 | ~5 MB |

### 完整方案：BTC + ETH（过去一年）

| 阶段 | 动作 | 预估大小 |
|------|------|--------|
| 1 | 下载Trades | ~6-10 GB |
| 2 | 提取特征 | ~2-4 GB |
| **总计** | **完整方案** | **~8-14 GB** |

---

## 完整数据链路

```
Binance Data Vision
    │
    ├─→ [下载] Trades (ZIP → CSV → Parquet)
    │       └─→ 3-5 GB/币/年
    │
    ├─→ [提取] Trade特征 (1秒聚合)
    │       └─→ 1-2 GB/币/年
    │
    └─→ [可选] 实时采集 OrderBook
            └─→ 实时保存
```

---

## 快速开始

### 1️⃣ 测试下载
```bash
python scripts/test_download_single_month.py
```

### 2️⃣ 下载过去一年数据
```bash
python scripts/download_binance_trades.py --symbols BTCUSDT ETHUSDT --years 2024 2025 2026
```

### 3️⃣ 提取特征
```bash
python scripts/extract_features_from_trades.py --symbols BTCUSDT ETHUSDT --years 2024 2025 2026
```
