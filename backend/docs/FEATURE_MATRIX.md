# Feature Matrix 架构设计

## 概述

Feature Matrix 是统一的特征存储和管理系统，合并了原来的「因子层」和「特征层」。

## 设计目标

1. **简化架构**：不再区分「特征」和「因子」，统一在一个矩阵中管理
2. **多币种支持**：每个币种有独立的 Feature Matrix
3. **分类清晰**：特征按类型分类，便于策略发现时的优先级排序
4. **易于扩展**：新特征可以快速添加到分类中

## 特征分类

```
Feature Matrix
├── raw_features (原始特征)
│   ├── open, high, low, close, volume
│   ├── funding_rate, open_interest
│   └── long_liquidations, short_liquidations
│
├── derived_features (衍生特征 - 原"因子"层)
│   ├── rsi_14, rsi_7
│   ├── macd_line, macd_signal, macd_histogram
│   ├── bollinger_upper, bollinger_lower, bollinger_middle
│   ├── atr_14, volatility_24h
│   ├── trend_ma_short, trend_ma_long
│   ├── funding_zscore, oi_change_24h
│   └── volume_zscore
│
├── microstructure_features (微观结构特征)
│   ├── spread, spread_pct, mid_price, microprice
│   ├── imbalance_1, imbalance_5, imbalance_10
│   ├── top5_bid_volume, top5_ask_volume
│   ├── trade_delta, cumulative_delta
│   ├── aggressive_buy_volume, aggressive_sell_volume
│   ├── large_trade_ratio, trade_velocity
│   └── sweep_score
│
├── cross_market_features (跨市场特征)
│   ├── basis_binance_okx
│   ├── basis_futures_spot
│   ├── btc_dominance
│   ├── vix_crypto
│   ├── risk_on_off
│   └── usd_weakness
│
└── event_features (事件/叙事特征)
    ├── news_sentiment
    ├── twitter_velocity
    ├── news_velocity
    ├── bullish_score
    └── bearish_score
```

## 核心组件

### 1. FeatureMatrix 类

位置：`services/strategy_service/feature_matrix.py`

主要功能：
- 加载和管理特征数据
- 按分类查询特征
- 特征标准化
- 特征矩阵输出

### 2. 元数据管理

每个特征都有元数据：
```python
FeatureMetadata(
    name="RSI 14",
    name_en="RSI 14",
    category=FeatureCategory.DERIVED,
    description="14周期相对强弱指标",
    normalization_range=(0, 100),
    is_factor=True,  # 兼容原因子标识
    source="internal",
    default_weight=1.0,
)
```

### 3. 与 FactorCalculator 的关系

| 组件 | 定位 | 用途 |
|------|------|------|
| **FeatureMatrix** | 离线存储 | 策略发现、回测、AI模型训练 |
| **FactorCalculator** | 实时指标 | 仪表盘展示、权重调整 |

## 使用示例

### 1. 加载 Feature Matrix

```python
from services.strategy_service.feature_matrix import FeatureMatrix

# 加载 BTC 的 Feature Matrix
fm = FeatureMatrix.load_for_symbol("BTCUSDT")

# 查看摘要
print(fm.summary())
```

### 2. 查询特征

```python
# 获取所有衍生特征（原因子层）
derived_features = fm.get_derived_features()

# 获取微观结构特征
micro_features = fm.get_microstructure_features()

# 按分类查询
raw_features = fm.get_features_by_category(FeatureCategory.RAW)
```

### 3. 获取特征矩阵

```python
# 获取指定特征的矩阵
feature_matrix = fm.get_feature_matrix([
    "rsi_14", "macd_line", "spread", "imbalance_5"
])

# 获取所有特征
all_features = fm.get_feature_matrix()
```

### 4. 策略发现集成

策略发现引擎已自动集成 Feature Matrix：
```python
# 策略发现引擎会自动使用 Feature Matrix 的分类
# 优先扫描衍生特征和微观结构特征
engine = StrategyDiscoveryEngine(symbols=["BTCUSDT", "ETHUSDT"])
patterns = engine.discover_all_symbols()
```

## 数据文件位置

```
data_lake/
└── features/
    └── binance/
        ├── BTCUSDT/
        │   └── features_with_structure.parquet
        ├── ETHUSDT/
        │   └── features_with_structure.parquet
        └── SOLUSDT/
            └── features_with_structure.parquet
```

## 多币种支持

每个币种有独立的 Feature Matrix：
- 策略发现按币种独立运行
- 特征参数按币种独立优化
- SymbolStrategyRegistry 管理币种级策略配置

## 迁移说明

### 原因子层 → derived_features

原来的「因子」现在是 `derived_features` 分类的一部分，保持了兼容性：
- `is_factor=True` 标识保留
- Meta data 保留了原来的配置

### 原特征层 → 对应分类

原来的特征按类型分配到不同分类中。

## 下一步

1. 特征标准化方法完善
2. 特征重要性分析
3. 特征工程自动优化
4. AI 模型训练集成
