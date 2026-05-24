# Feature Service（特征工程层）设计文档

# 🧠 1. 模块定位

# 1.1 核心作用

原始数据 → 标准化特征（Features）

它是**数据层到因子层之间的桥梁**，负责：
- 数据清洗与校验
- 指标计算
- 时间对齐
- 输出标准化特征

# 1.2 在系统中的位置

```
Data Layer → Feature Service → Factor Layer → Risk Engine → Decision → Position
```

# 📊 2. 输入数据

# 2.1 价格数据

```json
{
  "symbol": "BTC",
  "price": 68000.0,
  "open": 67500.0,
  "high": 68500.0,
  "low": 67000.0,
  "volume": 12345.67,
  "timestamp": 1710000000
}
```

# 2.2 ETF资金流数据

```json
{
  "symbol": "BTC ETF",
  "inflow": 150000000,
  "outflow": 80000000,
  "net_flow": 70000000,
  "timestamp": 1710000000
}
```

# 2.3 宏观经济数据

```json
{
  "gold": 2020.5,
  "oil": 78.3,
  "timestamp": 1710000000
}
```

# 2.4 新闻数据

```json
{
  "title": "...",
  "content": "...",
  "source": "...",
  "timestamp": 1710000000
}
```

# 🧮 3. 特征计算（核心功能）

# 3.1 价格特征

| 特征名 | 计算方法 | 输出 |
|--------|----------|------|
| returns | (price - prev_price) / prev_price | float |
| volatility | std(returns, window=20) | float |
| momentum | price / MA(price, 20) - 1 | float |
| atr | ATR(14) | float |
| high_low_ratio | high / low - 1 | float |

# 3.2 趋势特征

| 特征名 | 计算方法 | 输出 |
|--------|----------|------|
| ma_5 | MA(price, 5) | float |
| ma_20 | MA(price, 20) | float |
| ma_alignment | ma_5 > ma_20 ? 1 : -1 | int |
| trend_strength | \|ma_5 / ma_20 - 1\| | float |

# 3.3 资金流特征

| 特征名 | 计算方法 | 输出 |
|--------|----------|------|
| net_flow | inflow - outflow | float |
| flow_change | net_flow - prev_net_flow | float |
| flow_acceleration | flow_change - prev_flow_change | float |
| flow_direction | net_flow > 0 ? 1 : -1 | int |

# 3.4 宏观特征

| 特征名 | 计算方法 | 输出 |
|--------|----------|------|
| gold_return | (gold - prev_gold) / prev_gold | float |
| oil_return | (oil - prev_oil) / prev_oil | float |
| macro_signal | -(gold_return + oil_return) / 2 | float |

# 3.5 波动率特征

```python
def compute_volatility_features(prices: list, window: int = 20) -> dict:
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    volatility = np.std(returns[-window:])
    atr = compute_atr(highs, lows, closes, period=14)
    return {
        "volatility": volatility,
        "atr": atr,
        "atr_percent": atr / prices[-1]
    }
```

# 🔧 4. 时间对齐机制

# 4.1 统一时间粒度

```python
TIME_FRAMES = {
    "1m": 60,
    "5m": 300,
    "1h": 3600,
    "1d": 86400
}
```

# 4.2 对齐规则

```python
def align_to_timeframe(data: dict, target_frame: str) -> dict:
    for key, value in data.items():
        if "timestamp" in value:
            value["timestamp"] = floor_timestamp(
                value["timestamp"],
                TIME_FRAMES[target_frame]
            )
    return data
```

# 4.3 数据完整性检查

```python
def validate_data_completeness(features: dict, required_fields: list) -> bool:
    for field in required_fields:
        if field not in features or features[field] is None:
            return False
    return True
```

# 📤 5. 输出格式

# 5.1 标准特征输出

```json
{
  "symbol": "BTC",
  "timeframe": "5m",
  "timestamp": 1710000000,
  "price_features": {
    "returns": 0.0123,
    "volatility": 0.025,
    "momentum": 0.035,
    "atr": 0.025,
    "atr_percent": 0.025
  },
  "trend_features": {
    "ma_5": 67800,
    "ma_20": 67000,
    "ma_alignment": 1,
    "trend_strength": 0.012
  },
  "flow_features": {
    "net_flow": 70000000,
    "flow_change": 5000000,
    "flow_acceleration": 1000000,
    "flow_direction": 1
  },
  "macro_features": {
    "gold_return": 0.005,
    "oil_return": -0.003,
    "macro_signal": 0.001
  },
  "data_quality": {
    "complete": true,
    "sources": ["binance", "etf", "macro"]
  }
}
```

# ⚠️ 6. 质量控制

# 6.1 异常值处理

```python
def handle_outliers(values: list, threshold: float = 3.0) -> list:
    mean = np.mean(values)
    std = np.std(values)
    z_scores = [(v - mean) / std for v in values]
    return [v if abs(z) < threshold else mean for v, z in zip(values, z_scores)]
```

# 6.2 缺失值处理

```python
def handle_missing_values(values: list, method: str = "ffill") -> list:
    if method == "ffill":
        return pd.Series(values).fillna(method="ffill").tolist()
    elif method == "bfill":
        return pd.Series(values).fillna(method="bfill").tolist()
    elif method == "interpolate":
        return pd.Series(values).interpolate().tolist()
    return values
```

# 6.3 数据源优先级

```
价格数据：binance > okx > coinbase
ETF数据：farside > sosovalue > 备用源
宏观数据：yahoo > alternative源
```

# 🔄 7. 运行节奏

| 特征类型 | 更新频率 | 说明 |
|----------|----------|------|
| 价格特征 | 实时 | 每次新价格 |
| 趋势特征 | 1分钟 | 均线更新 |
| 波动率特征 | 5分钟 | ATR计算 |
| ETF特征 | 每日收盘 | 日级别更新 |
| 宏观特征 | 每日 | 黄金/原油 |

# 🏗️ 8. 架构设计

```
FeatureService
├── PriceFeatureEngine
│   ├── ReturnsCalculator
│   ├── VolatilityCalculator
│   ├── MomentumCalculator
│   └── ATRCalculator
├── TrendFeatureEngine
│   ├── MACalculator
│   └── TrendAlignmentChecker
├── FlowFeatureEngine
│   ├── ETFFlowProcessor
│   └── FlowChangeCalculator
├── MacroFeatureEngine
│   ├── GoldPriceProcessor
│   └── OilPriceProcessor
└── QualityControl
    ├── OutlierHandler
    ├── MissingValueHandler
    └── DataValidator
```

# 📁 9. 存储设计

# 9.1 特征数据表

```sql
CREATE TABLE features (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    timestamp BIGINT NOT NULL,
    feature_type VARCHAR(50) NOT NULL,
    feature_name VARCHAR(50) NOT NULL,
    value DECIMAL(20, 10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_timeframe_type_name (symbol, timeframe, timestamp, feature_type, feature_name),
    INDEX idx_symbol_timestamp (symbol, timestamp)
);
```

# 9.2 原始数据缓存

```python
FEATURE_CACHE = {
    "BTC_5m": {"data": [...], "last_update": 1710000000},
    "ETH_1h": {"data": [...], "last_update": 1709999000}
}
```

# ✅ 10. 与因子层对接

```python
class FeatureService:
    def get_features(self, symbol: str, timeframe: str, timestamp: int) -> dict:
        features = self.load_from_cache_or_db(symbol, timeframe, timestamp)
        return self.format_for_factor_layer(features)

    def format_for_factor_layer(self, features: dict) -> dict:
        return {
            "returns": features["price_features"]["returns"],
            "volatility": features["price_features"]["volatility"],
            "atr": features["price_features"]["atr"],
            "ma_alignment": features["trend_features"]["ma_alignment"],
            "net_flow": features["flow_features"]["net_flow"],
            "macro_signal": features["macro_features"]["macro_signal"]
        }
```

# 🚀 11. 扩展方向

- 实时计算优化（向量化）
- 多时间框架特征聚合
- 自定义特征注册机制
- 特征重要性分析
