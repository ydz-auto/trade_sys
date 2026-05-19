# 市场结构特征 (Market Structure Features)

## 一、什么是 Market Structure Feature

Market Structure Feature 比 RSI、MACD 更高级，因为：

- **描述市场行为** 而不是单点指标
- **包含上下文信息** 而不是孤立数据
- **支持事件分析** 而不是静态分析
- **Market State Engine** 而不是指标系统

---

## 二、已实现的市场结构特征

### 1. Rolling High / Low（滚动高低价）

| 特征 | 说明 |
|------|------|
| `rolling_high_24h` | 24小时滚动最高价 |
| `rolling_low_24h` | 24小时滚动最低价 |
| `rolling_high_72h` | 3天滚动最高价 |
| `rolling_low_72h` | 3天滚动最低价 |
| `rolling_high_168h` | 7天滚动最高价 |
| `rolling_low_168h` | 7天滚动最低价 |

### 2. Distance to Resistance / Support（距离压力/支撑位）

| 特征 | 说明 |
|------|------|
| `dist_to_resistance_24h` | 距离24h阻力位的百分比 |
| `dist_to_support_24h` | 距离24h支撑位的百分比 |
| `position_in_range_24h` | 在区间中的位置（0=底部，1=顶部） |

### 3. Breakout Detection（突破检测）

| 特征 | 说明 |
|------|------|
| `breakout_high_24h` | 是否突破24h高点 |
| `breakout_low_24h` | 是否跌破24h低点 |
| `breakout_strength_24h` | 突破强度 |

### 4. Spike Event Detection（暴涨暴跌事件）

| 特征 | 说明 |
|------|------|
| `spike_up` | 是否暴涨（5m > 3%） |
| `spike_down` | 是否暴跌（5m < -3%） |
| `major_spike_up` | 是否大幅暴涨（5m > 5%） |
| `spike_strength` | Spike强度 |

### 5. Follow-through Return（后续收益）

| 特征 | 说明 |
|------|------|
| `follow_through_5m` | Spike后5分钟收益 |
| `follow_through_15m` | Spike后15分钟收益 |
| `follow_through_1h` | Spike后1小时收益 |

### 6. Trend Classification（趋势分类）

| 特征 | 说明 |
|------|------|
| `trend_direction_12h` | 12h趋势方向 |
| `trend_direction_24h` | 24h趋势方向 |
| `trend_strength_12h` | 12h趋势强度 |
| `trend_strength_24h` | 24h趋势强度 |
| `trend_acceleration` | 趋势加速度 |

### 7. Market State Classification（市场状态分类）

| 状态 | 说明 | 触发条件 |
|------|------|----------|
| `state_squeeze` | 吸筹/蓄力 | 价格涨 + OI涨 + volatility低 |
| `state_panic_dump` | 恐慌抛售 | 价格跌 + volume放大 |
| `state_breakout` | 突破 | 突破rolling high + volume放大 |
| `state_accumulation` | 积累 | 区间内 + volume稳定 + funding低 |

### 8. Advanced State Features（高级状态特征）

| 特征 | 说明 |
|------|------|
| `trend_exhaustion` | 趋势衰竭信号 |
| `trend_healthy` | 健康趋势信号 |
| `momentum_shift` | 动量转换 |
| `volatility_surge` | 波动率异常 |

---

## 三、Market Regime（市场状态）

| Regime | 说明 |
|--------|------|
| `trending_up` | 强势上涨 |
| `trending_down` | 强势下跌 |
| `volatile` | 高波动 |
| `ranging` | 区间震荡 |

---

## 四、使用方法

### 1. 加载市场结构特征数据

```python
import pandas as pd

df = pd.read_parquet("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
```

### 2. 使用市场状态

```python
# 找所有的突破事件
breakouts = df[df["breakout_high_24h"] == True]

# 找Squeeze状态
squeezes = df[df["state_squeeze"] == 1]

# 找趋势衰竭
exhaustions = df[df["trend_exhaustion"] == 1]
```

### 3. 事件分析

```python
# 分析所有spike事件后的收益
spike_events = df[df["spike_up"] == True]
avg_return_after_spike = spike_events["follow_through_1h"].mean()
```

---

## 五、策略回测结果（2024全年）

| 策略 | 收益 | 最大回撤 | 胜率 | 交易数 |
|------|------|----------|------|--------|
| 市场结构策略 | -36.66% | 56.35% | 44.59% | 4041 |
| 突破策略 | -3.33% | 37.84% | 42.24% | 850 |
| **均值回归策略** | **+9.92%** | **36.49%** | **54.41%** | 884 |

> 注：2024年是熊市，全年BTC从42k跌到93k，简单策略表现不佳是正常的

---

## 六、下一步

### 高级特性（后面可以实现）

1. **Volume Profile（成交量分布）**
   - 大量成交密集区
   - High Liquidity Zone
   - Low Liquidity Zone

2. **OI Wall（持仓墙）**
   - 杠杆密集区
   - Short Squeeze预测
   - Long Squeeze预测

3. **VWAP Anchored Level**
   - 从特定事件开始的VWAP
   - 动态支撑/阻力

4. **Event Study（事件研究）**
   - 对所有历史事件统计
   - 平均后续收益曲线
   - 不同市场状态下的表现

5. **Contextual Features**
   - 突破前市场状态
   - 资金流向
   - 宏观因素

---

## 七、文件结构

```
data_lake/features/binance/BTCUSDT/
├── features.parquet                    # 基础特征（33个）
└── features_with_structure.parquet     # 市场结构特征（94个）
```

---

## 八、运行命令

```bash
# 生成市场结构特征
python scripts/generate_market_structure_features.py

# 运行市场结构策略回测
python scripts/backtest_market_structure.py
```
