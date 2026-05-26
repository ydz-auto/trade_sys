# 行为和事件驱动策略总结

## 概述

根据您的建议，我已经完善了策略系统，重点补充了第一梯队的行为策略。行为和事件驱动策略比传统技术指标更有潜力，因为它们反映了市场参与者的真实行为。

## 策略分类

### 第一梯队（优先推荐）

这三个策略是最推荐优先使用的，因为数据获取容易，效果显著：

#### 1. `oi_behavior` - Open Interest 行为策略

**核心逻辑：**
- 价格↑ + OI↑ = 新多进场 → 趋势确认做多
- 价格↑ + OI↓ = 空头回补 → 谨慎或做空
- 价格↓ + OI↑ = 新空进场 → 趋势确认做空
- 价格↓ + OI↓ = 多头离场 → 谨慎或做多

**特征需求：**
- close_prices
- oi_history
- oi_delta
- oi_zscore
- volumes

**文件位置：** [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)

#### 2. `funding_extreme_reversal` - Funding Rate 极端反转策略

**核心逻辑：**
- 当市场极度一致看多时（Funding极端+OI新高+价格滞涨）→ 做空
- 当市场极度一致看空时 → 做多

**特征需求：**
- close_prices
- oi_history
- funding_rate
- funding_zscore
- oi_funding_divergence
- funding_extreme_reversal

**文件位置：** [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)

#### 3. `liquidation_cascade` - 爆仓连锁策略

**核心逻辑：**
- 大量多头被强平（>100万美元）+ OI下降>5% + 价格下跌>3% → 做反弹
- 大量空头被强平 + OI下降 + 价格上涨 → 继续上涨

**特征需求：**
- close_prices
- oi_history
- liquidation_long
- liquidation_short
- liquidation_spike
- liquidation_reversal_signal

**文件位置：** [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)

### 第二梯队（次级推荐）

#### 4. `cvd_divergence` - CVD背离策略

**核心逻辑：**
- 价格新高 + CVD不新高 → 买盘衰竭 → 做空
- 价格新低 + CVD不新低 → 卖盘衰竭 → 做多

**特征需求：**
- close_prices
- cvd_history

**文件位置：** [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)

#### 5. `whale_trade` - 大单策略

**核心逻辑：**
- 连续大额主动买入 + OI上升 → 跟随做多
- 连续大额主动卖出 + OI下降 → 跟随做空

**特征需求：**
- close_prices
- oi_history
- whale_buy_count
- whale_sell_count
- whale_buy_volume
- whale_sell_volume
- aggressive_flow

**文件位置：** [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)

#### 6. `funding_settlement` - 资金费率结算事件策略

**核心逻辑：**
- Binance每8小时结算（07:50、15:50、23:50）
- 结算前：高费率做空，低费率做多
- 结算后：反向（套利平仓）

**特征需求：**
- close_prices
- timestamp
- funding_rate

**文件位置：** [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)

## 策略架构

### 新增文件

1. **[behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py)** - 新增行为策略模块
   - 包含所有6个新策略的实现
   - 完整的策略逻辑和信号生成

### 修改文件

1. **[strategies.py](../engines/compute/strategy/strategies.py)** - 原有策略文件
   - 已包含基础行为策略：OIFlushStrategy、ShortSqueezeStrategy、FundingExhaustionTrapStrategy等

2. **[registry.py](../engines/compute/strategy/registry.py)** - 策略注册表
   - 新增6个策略的注册信息
   - 支持策略桥接和动态加载

## 特征提取框架

您的系统已经有非常完善的特征提取架构：

### 1. 清算特征
- 文件：[liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py)
- 功能：liquidation_long/short、liquidation_spike、liquidation_reversal_signal等

### 2. OI和Funding联动特征
- 文件：[oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py)
- 功能：oi_funding_divergence、oi_squeeze_probability、funding_extreme_reversal等

### 3. 其他微观结构特征
- 订单簿特征：[orderbook/](../domain/feature/orderbook/)
- 交易特征：[trade_feature.py](../domain/feature/trade/trade_feature.py)
- 技术指标：[indicators/](../domain/feature/indicators/)

## 推荐使用方式

### 策略组合建议

**最优先组合（3个策略）：**
```python
strategy_list = [
    "oi_behavior",              # 第一梯队，核心
    "funding_extreme_reversal", # 第一梯队，反转
    "liquidation_cascade"       # 第一梯队，事件
]
```

**完整组合（6个策略）：**
```python
strategy_list = [
    # 第一梯队
    "oi_behavior",
    "funding_extreme_reversal",
    "liquidation_cascade",
    # 第二梯队（可选）
    "cvd_divergence",
    "whale_trade",
    "funding_settlement"
]
```

### 特征优先级

确保以下特征被正确提取和提供：

1. **必需特征（第一梯队）：**
   - `oi_delta` / `oi_zscore`
   - `funding_rate` / `funding_zscore`
   - `liquidation_long` / `liquidation_short`
   - `oi_history` / `close_prices`

2. **增强特征（推荐）：**
   - `cvd_history`
   - `whale_*` 系列
   - `aggressive_flow`
   - `volume_surge`

## 对比：技术指标 vs 行为策略

| 维度 | 技术指标策略 | 行为策略（推荐） |
|------|-------------|----------------|
| 数据源 | K线价格/成交量 | OI、Funding、爆仓等 |
| 逻辑 | 价格形态分析 | 市场参与者行为分析 |
| 信息量 | 中 | 高 |
| 时效性 | 滞后 | 即时 |
| 机构关注 | 一般 | 高 |
| 数据可得性 | 容易 | Binance公开数据 |

## 总结

您的系统已经有很好的基础架构，现在通过补充行为和事件驱动策略，策略库更加完整。第一梯队的三个策略应该优先投入使用，它们：

1. ✅ 使用Binance公开数据
2. ✅ 反映真实市场参与者行为
3. ✅ 比技术指标更有信息量
4. ✅ 可以直接集成现有特征框架

