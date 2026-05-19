# 研究闭环 - 从历史数据到策略研究

## 一、当前状态 ✅

我们已经搭建完成第一条完整的研究链路！

### 数据湖结构
```
data_lake/
├── crypto/
│   └── binance/
│       ├── klines/
│       │   └── symbol=BTCUSDT/
│       │       ├── year=2024/
│       │       ├── year=2025/
│       │       └── year=2026/
│       ├── funding/
│       │   └── symbol=BTCUSDT/data.parquet
│       └── oi/
│           └── symbol=BTCUSDT/data.parquet
└── features/
    └── binance/
        ├── BTCUSDT/features.parquet
        └── ETHUSDT/features.parquet
```

### 已生成的特征
```
基础价格：open, high, low, close, volume
Returns：returns_1m, returns_5m, returns_1h
Volatility：volatility_1h, realized_vol_2h
技术指标：rsi_14, macd, macd_signal, macd_hist
布林带：bb_upper, bb_middle, bb_lower, bb_position
成交量：volume_ma20, volume_ratio
Funding：funding_rate, funding_ma8h, funding_delta, funding_zscore
Open Interest：open_interest, oi_ma60, oi_delta, oi_change_1h
```

## 二、快速开始

### 1. 加载特征数据
```python
import pandas as pd
import numpy as np
from pathlib import Path

feature_path = Path('data_lake/features/binance/BTCUSDT/features.parquet')
df = pd.read_parquet(feature_path)

print(f'数据范围: {df["timestamp"].min()} 至 {df["timestamp"].max()}')
print(f'数据行数: {len(df)}')
```

### 2. 特征分析
```python
# 统计分析
print(df[['close', 'rsi_14', 'funding_rate', 'open_interest']].describe())

# 查看某一段时间
mask = (df['timestamp'] >= '2024-03-01') & (df['timestamp'] < '2024-04-01')
df_sample = df.loc[mask].copy()
```

### 3. 生成新特征
修改 `scripts/generate_features.py` 中的 `compute_features_batch` 函数，然后重新运行：
```bash
python scripts/generate_features.py --symbols BTCUSDT ETHUSDT --exchange binance
```

## 三、研究闭环流程图

```
历史数据下载 (Binance ZIP)
        ↓
统一Schema + 合并 (K线 + Funding + OI)
        ↓
特征计算 (generate_features.py)
        ↓
特征Parquet存储 (features.parquet)
        ↓
策略/因子研究 (Jupyter/脚本)
        ↓
Replay回放 (待完善)
        ↓
策略评估 + 迭代
```

## 四、下一步工作

### 优先级 1 - 策略回测
- [ ] 实现简单的回测引擎
- [ ] 接入特征数据
- [ ] 支持止损/止盈

### 优先级 2 - Replay Runtime
- [ ] 完善现有的Replay系统
- [ ] 接入特征数据
- [ ] 支持事件回放

### 优先级 3 - 更多数据
- [ ] 下载Trades数据（如需要）
- [ ] 支持更多交易对
- [ ] 支持更多交易所

## 五、文件说明

| 文件 | 说明 |
|------|------|
| `scripts/download_binance_klines.py` | Binance K线下载（官方ZIP） |
| `scripts/download_binance_funding.py` | Funding数据下载 |
| `scripts/download_binance_oi.py` | Open Interest下载 |
| `scripts/generate_features.py` | 特征生成流水线 |
| `data_lake/crypto/binance/` | 原始数据存储 |
| `data_lake/features/binance/` | 特征数据存储 |
