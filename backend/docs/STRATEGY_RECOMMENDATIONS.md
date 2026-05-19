# 🚀 策略推荐文档

> 基于数据特征挖掘的量化交易策略体系

## 1. 策略分类概览

| 分类 | 策略数量 | 预期收益 | 风险等级 | 实施难度 |
|------|:-------:|:-------:|:--------:|:--------:|
| Behavioral | 8 | ⭐⭐⭐⭐⭐ | 中高 | ⭐⭐ |
| 特征挖掘 | 6 | ⭐⭐⭐⭐ | 中 | ⭐ |
| 组合信号 | 5 | ⭐⭐⭐⭐⭐ | 中高 | ⭐⭐ |
| 时间模式 | 4 | ⭐⭐⭐ | 中 | ⭐⭐ |
| 机器学习 | 3 | ⭐⭐⭐⭐⭐ | 高 | ⭐⭐⭐⭐ |
| 市场结构 | 4 | ⭐⭐⭐⭐ | 中 | ⭐⭐ |

---

## 2. Behavioral & Event-Driven 策略

### 2.1 Short Squeeze Hunt - 空头挤压猎手

**核心逻辑**：高资金费率环境下，空头被套牢，一旦价格反弹，空头被迫平仓形成连锁反应

**触发条件**：
```python
score = 0
if funding_rate > 0.0001: score += 2
if state_squeeze > 0: score += 3
if return_5m > 0.005: score += 1
if volume_ratio > 1.5: score += 1
if regime == "volatile": score += 1

if score >= 5:
    → 做多
```

**参数配置**：止盈3.5%，止损2%，最大持仓4小时

---

### 2.2 Long Liquidation Bounce - 多头踩踏反弹

**核心逻辑**：大幅下跌后，多头被迫平仓，反而形成最佳买入机会

**触发条件**：
```python
score = 0
if return_1h < -0.02: score += 3      # 1小时跌幅 > 2%
if state_panic_dump > 0: score += 3   # 恐慌抛售状态
if volatility_ratio > 2: score += 2    # 波动率飙升
if volume_ratio > 2: score += 1

if score >= 6:
    → 做多
```

**参数配置**：止盈4%，止损2.5%，最大持仓6小时

---

### 2.3 Fake Breakout Trap - 假突破陷阱

**核心逻辑**：假突破后快速回落，反向交易获利

**触发条件**：
```python
if 突破24小时高点 AND (
    volume_ratio < 1.2 OR          # 缺乏成交量确认
    regime == "ranging" OR          # 震荡市场更容易假突破
    close < high * 0.998           # 价格被拒绝
):
    → 做空
```

---

### 2.4 Weekend Liquidity Trap - 周末低流动性陷阱

**核心逻辑**：周末流动性枯竭，价格异常波动

**触发条件**：
```python
if (is_weekend OR hour in [0-7]) AND (
    low_liquidity == True AND
    abs(return_5m) > 0.005 AND
    spread_widening == True
):
    → 反向交易
```

---

### 2.5 OI Flush - 杠杆清洗

**核心逻辑**：高杠杆仓位被清洗后，趋势往往延续

**触发条件**：
```python
if oi_delta > 0.01 AND return_1h > 0.01:
    → 做多
elif oi_delta < -0.01 AND return_1h < -0.01:
    → 做空
```

---

### 2.6 Spread Widening Detector - 点差扩大预警

**核心逻辑**：点差突然扩大往往是流动性枯竭或爆仓前的信号

**触发条件**：
```python
score = 0
if spread_widening == True: score += 3
if volatility_ratio > 2: score += 2
if low_liquidity == True: score += 1
if abs(return_5m) > 0.008: score += 2

if score >= 5:
    → 反向交易
```

---

### 2.7 Volume Imbalance - 成交量失衡

**核心逻辑**：大阳线后缩量下跌，或大阴线后缩量上涨

**触发条件**：
```python
# 上涨后的失衡 → 看跌
if 大阳线 AND volume_ratio < 1.0 AND return_5m < 0:
    → 做空

# 下跌后的失衡 → 看涨
if 大阴线 AND volume_ratio < 1.0 AND return_5m > 0:
    → 做多
```

---

### 2.8 Liquidation Cascade - 爆仓链

**核心逻辑**：连续下跌触发多头止损，形成连锁反应

**触发条件**：
```python
score = 0
if return_4h < -0.03: score += 3
if state_panic_dump > 0: score += 3
if volume_ratio > 2: score += 1
if volatility_ratio > 2: score += 1

if score >= 6:
    → 做多（超跌反弹）
```

---

## 3. 基于数据特征挖掘的策略

### 3.1 Trend Exhaustion Reversal - 趋势衰竭反转

**触发条件**：
```python
if trend_exhaustion == 1 AND momentum_shift == 1:
    if trend_direction_12h > 0:
        → 做空
    else:
        → 做多
```

---

### 3.2 Volatility Crush Mean Reversion - 波动率收缩均值回归

**触发条件**：
```python
if volatility_surge == 1 AND volatility_ratio < 1.5:
    → 等待价格回调后做均值回归
```

---

### 3.3 Regime Transition Momentum - 市场状态转换动量

**触发条件**：
```python
if 当前regime == "volatile" AND 前1小时regime == "ranging":
    → 顺势交易
```

---

### 3.4 Price-MA Divergence - 价格均线偏离

**触发条件**：
```python
if price_vs_ma_20 > 0.05:
    → 回调概率增加
elif price_vs_ma_20 < -0.05:
    → 反弹概率增加
```

---

### 3.5 RSI Extreme + Trend Confirmation

**触发条件**：
```python
if rsi_14 < 30 AND trend_direction_12h > 0:
    → 做多
elif rsi_14 > 70 AND trend_direction_12h < 0:
    → 做空
```

---

### 3.6 Spike Detection - 异常波动检测

**触发条件**：
```python
if spike_up == 1 AND major_spike_up == 0:
    → 短期回调概率增加
if spike_down == 1 AND major_spike_down == 0:
    → 短期反弹概率增加
```

---

## 4. 组合特征策略

### 4.1 Smart Money Detection - 聪明钱检测 ⭐⭐⭐⭐⭐

**触发条件**：
```python
if (
    funding_rate > 0.0002 AND      # 高资金费率
    oi_delta > 0.01 AND           # OI 增加
    volume_ratio < 1.2 AND        # 缩量
    regime == "volatile"           # 高波动环境
):
    → 做多
```

---

### 4.2 Retail Trap - 散户陷阱 ⭐⭐⭐⭐⭐

**触发条件**：
```python
if (
    funding_rate < 0.0001 AND
    oi_delta > 0.02 AND
    volume_ratio > 2.0 AND
    regime == "volatile"
):
    → 做空
```

---

### 4.3 Squeeze Release - 挤压释放

**触发条件**：
```python
if (
    state_squeeze > 0 AND
    volatility_surge == 1 AND
    bb_width < 0.01
):
    → 等待突破方向顺势交易
```

---

### 4.4 Dead Cat Bounce V2

**触发条件**：
```python
if (
    major_spike_down == 1 AND
    state_panic_dump > 0 AND
    volume_ratio < 1.0 AND
    return_15m > 0.005
):
    → 做空
```

---

### 4.5 Accumulation Detection - 吸筹检测

**触发条件**：
```python
if (
    state_accumulation > 0 AND
    oi_delta > 0.01 AND
    volume_ratio < 1.5 AND
    regime == "ranging"
):
    → 区间下沿做多
```

---

## 5. 时间模式策略

### 5.1 亚洲盘低波动突破

**触发条件**：
```python
if session == "asia" AND volume_ratio < 0.8 AND volatility_ratio < 0.8:
    → 等待欧美盘开盘突破
```

---

### 5.2 纽约开盘动量

**触发条件**：
```python
if hour == 21 AND return_15m > 0.005 AND volume_ratio > 1.5:
    → 顺势交易
```

---

### 5.3 周五收盘效应

**触发条件**：
```python
if day_of_week == 4 AND hour >= 20 AND abs(return_5m) > 0.005:
    → 反向交易
```

---

### 5.4 月初效应

**触发条件**：
```python
if day_of_month <= 3 AND volume_ratio > 1.3 AND abs(return_1h) > 0.01:
    → 顺势交易
```

---

## 6. 机器学习增强策略

### 6.1 随机森林信号

**特征工程**：
```python
features = [
    'rsi_14', 'macd', 'macd_signal', 
    'volume_ratio', 'funding_rate', 'funding_zscore',
    'oi_delta', 'regime_code', 'trend_strength_12h',
    'volatility_1h', 'bb_position', 'return_5m', 'return_1h'
]

# 预测：下一根K线方向
```

---

### 6.2 XGBoost 二分类

```python
# 正样本：盈利超过1%的交易
# 负样本：亏损超过1%的交易
# 训练模型预测信号质量
```

---

### 6.3 LSTM 时序预测

```python
sequence_length = 24  # 24根5分钟K线

X = [close_prices, volumes, funding_rates, returns, volatilities]

# 预测：未来12小时的走势
```

---

## 7. 市场结构策略

### 7.1 支撑阻力突破 + 成交量确认

**触发条件**：
```python
if (
    close > breakout_high_24h AND
    volume_ratio > 1.5 AND
    funding_zscore > 1
):
    → 做多突破
```

---

### 7.2 布林带多周期共振

**触发条件**：
```python
if (
    当前5m_bb_width < 0.01 AND
    1h_bb_width < 0.015 AND
    volume_ratio > 1.3
):
    → 等待突破方向顺势交易
```

---

### 7.3 RSI + MACD 背离

**触发条件**：
```python
# 顶背离
if 价格创24小时新高 AND rsi_14 < 70 AND macd < 前一bar_macd:
    → 做空

# 底背离
if 价格创24小时新低 AND rsi_14 > 30 AND macd > 前一bar_macd:
    → 做多
```

---

## 8. 实施优先级

| 优先级 | 策略 | 预期收益 | 实施难度 |
|:------:|------|:--------:|:--------:|
| 1 | **Smart Money Detection** | ⭐⭐⭐⭐⭐ | ⭐ |
| 2 | **Trend Exhaustion Reversal** | ⭐⭐⭐⭐ | ⭐ |
| 3 | **Regime Transition** | ⭐⭐⭐⭐ | ⭐⭐ |
| 4 | **Short Squeeze Hunt** | ⭐⭐⭐⭐ | ⭐ |
| 5 | **Liquidation Cascade** | ⭐⭐⭐⭐ | ⭐ |
| 6 | **Volatility Crush** | ⭐⭐⭐ | ⭐⭐ |
| 7 | **机器学习信号** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 8 | **时间模式** | ⭐⭐⭐ | ⭐⭐ |

---

## 9. 回测结果汇总

### 已有策略表现（2024-2026 全部数据）

| 策略 | 分类 | 方向 | 交易数 | 胜率 | 收益率 | 夏普 | 推荐度 |
|------|------|:----:|:------:|:----:|:------:|:----:|:------:|
| **Panic Reversal** | Behavioral | 做多 | 240 | 51.7% | +1,088% | 1.26 | ⭐⭐⭐⭐⭐ |
| **Weak Bounce Short V2** | 优化做空 | 做空 | 130 | 53.8% | +572% | 3.15 | ⭐⭐⭐⭐⭐ |
| **Liquidation Cascade** | Behavioral | 做多 | 21 | 61.9% | +282% | 5.25 | ⭐⭐⭐⭐ |
| **Weekend Liquidity Trap V2** | 优化做空 | 双向 | 86 | 57.0% | +170% | 2.21 | ⭐⭐⭐⭐ |
| **Cascade Flip** | 创新策略 | 做多 | 27 | 51.9% | +109% | 2.66 | ⭐⭐⭐ |
| **Meme Mania Rotation** | 创新策略 | 做多 | 24 | 50.0% | +91% | 2.02 | ⭐⭐⭐ |

### 近5个月表现 vs 全部数据

| 策略 | 近5个月 | 全部数据 | 稳定性 |
|------|:-------:|:--------:|:------:|
| **Volume Climax Fade V2** | +281% | +8% | ⚠️ 短期极佳 |
| **Weak Bounce Short V2** | +151% | +572% | ✅ 稳定 |
| **Panic Reversal** | +93% | +1,088% | ✅ 稳定 |
| **Liquidation Cascade** | +137% | +282% | ✅ 稳定 |

---

## 10. 下一步行动

### 立即可实施
1. ✅ 实现 Smart Money Detection
2. ✅ 实现 Trend Exhaustion Reversal  
3. ✅ 实现 Regime Transition

### 需要数据支持
4. 🔧 获取更长期的行情数据（用于 ML 训练）
5. 🔧 添加盘口数据（用于微结构分析）

### 高级功能
6. 🛠️ 构建 ML 模型pipeline
7. 🛠️ 实现策略组合优化
8. 🛠️ 添加实盘接口

---

**文档版本**：1.0  
**创建时间**：2026-05-19
