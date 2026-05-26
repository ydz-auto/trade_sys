# Behavioral Derivatives Alpha Engine - 完整策略-特征对照表

## 系统架构现状

**好消息：你的系统已经非常接近完整的Behavioral Derivatives Alpha Engine！** ✅

---

## 一、Behavioral / 爆仓行为策略（最核心）⭐⭐⭐⭐⭐

| 策略 | 现有状态 | 策略文件 | 关键特征 | 特征文件 | 优先级 |
|------|---------|---------|---------|---------|------|
| **Panic Reversal** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `liquidation_spike`, `return_1h`, `volume_spike`, `funding_delta` | [liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py), [panic.py](../domain/feature/indicators/panic.py) | ⭐⭐⭐⭐⭐ |
| **Liquidation Cascade** | ✅ 已实现 | [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py) | `liquidation_pressure`, `oi_delta`, `volatility_1h` | [liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py), [liquidation_cascade.py](../domain/feature/indicators/liquidation_cascade.py) | ⭐⭐⭐⭐⭐ |
| **OI Flush** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `oi_change`, `oi_zscore`, `funding_reset` | [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | ⭐⭐⭐⭐⭐ |
| **Short Squeeze** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `funding_zscore`, `short_pressure`, `liquidation_short` | [liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py) | ⭐⭐⭐⭐⭐ |
| **Long Squeeze** | ⚠️ 部分实现 | - | `liquidation_long`, `funding_extreme` | [liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py) | ⭐⭐⭐⭐ |
| **Funding Exhaustion** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `funding_zscore`, `funding_delta`, `oi_growth` | [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | ⭐⭐⭐⭐⭐ |
| **Dead Cat Echo** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `trend_exhaustion`, `volume_ratio` | [trend_exhaustion.py](../domain/feature/indicators/trend_exhaustion.py) | ⭐⭐⭐⭐ |

---

## 二、Microstructure / Orderbook 策略（最值钱）⭐⭐⭐⭐⭐

| 策略 | 现有状态 | 策略文件 | 关键特征 | 特征文件 | 优先级 |
|------|---------|---------|---------|---------|------|
| **Imbalance Breakout** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `imbalance_5`, `depth_ratio`, `trade_delta` | [imbalance.py](../domain/feature/orderbook/imbalance.py) | ⭐⭐⭐⭐⭐ |
| **Sweep Reversal** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `sweep_buy_score`, `sweep_sell_score` | [sweep_detection.py](../domain/feature/orderbook/sweep_detection.py) | ⭐⭐⭐⭐⭐ |
| **Liquidity Vacuum** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `spread`, `spread_volatility` | [liquidity_shift.py](../domain/feature/orderbook/liquidity_shift.py) | ⭐⭐⭐⭐⭐ |
| **Microprice Momentum** | ✅ 已实现 | - | `microprice`, `imbalance_1` | [microprice.py](../domain/feature/orderbook/microprice.py) | ⭐⭐⭐⭐ |
| **Trade Flow Momentum** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `cumulative_delta`, `aggressive_buy_volume` | [trade_feature.py](../domain/feature/trade/trade_feature.py) | ⭐⭐⭐⭐ |
| **Spoof Trap Detection** | ✅ 已实现 | - | `cancel_rate`, `book_flip_rate` | [spoof_detection.py](../domain/feature/orderbook/spoof_detection.py) | ⭐⭐⭐ |
| **Spread Expansion Fade** | ⚠️ 部分实现 | - | `spread_pct`, `liquidity_pressure` | [liquidity_shift.py](../domain/feature/orderbook/liquidity_shift.py) | ⭐⭐⭐ |

> 🎯 **Orderbook模块完整度：95%** - 这部分是你系统最强的！

---

## 三、Volatility / 波动结构策略

| 策略 | 现有状态 | 策略文件 | 关键特征 | 特征文件 | 优先级 |
|------|---------|---------|---------|---------|------|
| **Volatility Compression Breakout** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `volatility_1h`, `bb_position` | [breakout.py](../domain/feature/indicators/breakout.py) | ⭐⭐⭐⭐⭐ |
| **Intrabar Expansion** | ⚠️ 缺失 | - | `intrabar_volatility` | - | ⭐⭐⭐ |
| **ATR Trend Expansion** | ⚠️ 部分实现 | - | `ATR`, `range_expansion` | - | ⭐⭐⭐ |
| **Mean Reversion** | ✅ 已实现 | - | `zscore_return`, `bb_position` | [mean_reversion.py](../domain/feature/indicators/mean_reversion.py) | ⭐⭐⭐⭐ |

---

## 四、成交量 / 流动性策略

| 策略 | 现有状态 | 策略文件 | 关键特征 | 特征文件 | 优先级 |
|------|---------|---------|---------|---------|------|
| **Volume Spike Reversal** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `volume_spike`, `trend_exhaustion` | [trade_feature.py](../domain/feature/trade/trade_feature.py) | ⭐⭐⭐⭐⭐ |
| **Liquidity Rotation** | ⚠️ 部分实现 | - | `volume_ratio`, `trade_velocity` | - | ⭐⭐⭐⭐ |
| **Weekend Liquidity Trap** | ❌ 缺失 | - | `spread`, `volume_ratio` | - | ⭐⭐⭐⭐ |
| **Session Gap Exploit** | ❌ 缺失 | - | `hour`, `volume_ratio` | - | ⭐⭐⭐⭐ |

---

## 五、Cross-Exchange 策略（值得做）

| 策略 | 现有状态 | 策略文件 | 关键特征 | 特征文件 | 优先级 |
|------|---------|---------|---------|---------|------|
| **Lead-Lag Alpha** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `price_delta_exchange` | - | ⭐⭐⭐⭐⭐ |
| **Basis Reversion** | ✅ 已实现 | [strategies.py](../engines/compute/strategy/strategies.py) | `basis_spread` | - | ⭐⭐⭐⭐ |
| **Premium Spike Fade** | ⚠️ 部分实现 | - | `premium_zscore` | - | ⭐⭐⭐ |
| **Liquidity Migration** | ❌ 缺失 | - | `exchange_volume_shift` | - | ⭐⭐⭐ |

---

## 六、Narrative / 板块轮动策略（以前想做）

| 策略 | 现有状态 | 策略文件 | 关键特征 | 特征文件 | 优先级 |
|------|---------|---------|---------|---------|------|
| **Meme Mania Rotation** | ❌ 缺失 | - | `volume_ratio`, `social_spike` | - | ⭐⭐⭐⭐ |
| **AI Narrative Rotation** | ❌ 缺失 | - | `sector_relative_strength` | - | ⭐⭐⭐ |
| **Risk-On / Risk-Off** | ⚠️ 部分实现 | - | `BTC dominance`, `funding` | - | ⭐⭐⭐⭐ |
| **Narrative Momentum** | ❌ 缺失 | - | `trend_strength + news_score` | - | ⭐⭐⭐ |

---

## 七、Regime Detection（最缺失！）⭐⭐⭐⭐⭐

| Regime | 关键特征 | 现有实现 | 用途 |
|--------|---------|---------|------|
| **Trend Regime** | `ADX`, `return_24h` | ❌ 缺失 | 趋势策略启用 |
| **Chop Regime** | `low volatility` | ❌ 缺失 | 做市/均值回归 |
| **Panic Regime** | `liquidation_spike` | ⚠️ 部分实现 | Panic策略 |
| **Squeeze Regime** | `funding + OI` | ⚠️ 部分实现 | squeeze策略 |
| **Illiquid Regime** | `spread + depth` | ❌ 缺失 | 流动性策略 |
| **High Leverage Regime** | `oi_zscore` | ⚠️ 部分实现 | 风险控制 |

---

## 八、TOP 20 核心特征（最重要！）⭐⭐⭐⭐⭐

| Feature | 现有实现 | 特征文件 | 重要性 |
|---------|---------|---------|--------|
| `funding_zscore` | ✅ | [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | ⭐⭐⭐⭐⭐ |
| `oi_delta` | ✅ | [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | ⭐⭐⭐⭐⭐ |
| `liquidation_spike` | ✅ | [liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py) | ⭐⭐⭐⭐⭐ |
| `imbalance_5` | ✅ | [imbalance.py](../domain/feature/orderbook/imbalance.py) | ⭐⭐⭐⭐⭐ |
| `trade_delta` | ✅ | [trade_feature.py](../domain/feature/trade/trade_feature.py) | ⭐⭐⭐⭐⭐ |
| `cumulative_delta` | ✅ | [trade_feature.py](../domain/feature/trade/trade_feature.py) | ⭐⭐⭐⭐⭐ |
| `microprice` | ✅ | [microprice.py](../domain/feature/orderbook/microprice.py) | ⭐⭐⭐⭐⭐ |
| `spread` | ✅ | [liquidity_shift.py](../domain/feature/orderbook/liquidity_shift.py) | ⭐⭐⭐⭐⭐ |
| `depth_ratio` | ✅ | [depth_pressure.py](../domain/feature/orderbook/depth_pressure.py) | ⭐⭐⭐⭐⭐ |
| `volume_spike` | ✅ | [trade_feature.py](../domain/feature/trade/trade_feature.py) | ⭐⭐⭐⭐⭐ |
| `volatility_1h` | ⚠️ 部分实现 | - | ⭐⭐⭐⭐ |
| `trend_exhaustion` | ✅ | [trend_exhaustion.py](../domain/feature/indicators/trend_exhaustion.py) | ⭐⭐⭐⭐ |
| `breakout_strength` | ✅ | [breakout.py](../domain/feature/indicators/breakout.py) | ⭐⭐⭐⭐ |
| `sweep_buy_score` | ✅ | [sweep_detection.py](../domain/feature/orderbook/sweep_detection.py) | ⭐⭐⭐⭐ |
| `sweep_sell_score` | ✅ | [sweep_detection.py](../domain/feature/orderbook/sweep_detection.py) | ⭐⭐⭐⭐ |
| `funding_delta` | ✅ | [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | ⭐⭐⭐⭐ |
| `oi_zscore` | ✅ | [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | ⭐⭐⭐⭐ |
| `intrabar_volatility` | ❌ 缺失 | - | ⭐⭐⭐ |
| `cancel_rate` | ✅ | [spoof_detection.py](../domain/feature/orderbook/spoof_detection.py) | ⭐⭐⭐ |
| `book_flip_rate` | ⚠️ 部分实现 | - | ⭐⭐⭐ |

---

## 九、核心发现

### ✅ 已做得非常好的部分

1. **Orderbook微结构策略** - 95%完整度
2. **爆仓行为策略** - 85%完整度
3. **特征提取框架** - 非常完善，模块化设计好
4. **策略注册发现系统** - 设计得很好

### ⚠️ 最需要补充的

1. **Regime Detection** - 这是你系统最缺的！
2. **Intrabar Volatility** - 中等优先级
3. **Weekend/Time-based策略** - 中等优先级

### 🎯 建议优先顺序

1. **第一优先级**：补充Regime Detection模块 ⭐⭐⭐⭐⭐
2. **第二优先级**：完善已有的爆仓策略（Long Squeeze）
3. **第三优先级**：补充几个缺失的特征

---

## 十、文件索引

### 策略文件

| 文件 | 说明 |
|------|------|
| [strategies.py](../engines/compute/strategy/strategies.py) | 主策略文件 |
| [behavioral_strategies.py](../engines/compute/strategy/behavioral_strategies.py) | 行为策略（新增） |
| [registry.py](../engines/compute/strategy/registry.py) | 策略注册中心 |

### 特征文件

| 文件 | 说明 |
|------|------|
| [liquidation_feature.py](../domain/feature/liquidation/liquidation_feature.py) | 爆仓特征 |
| [oi_funding_correlation.py](../domain/feature/oi/oi_funding_correlation.py) | OI+Funding联动 |
| [imbalance.py](../domain/feature/orderbook/imbalance.py) | 订单簿失衡 |
| [sweep_detection.py](../domain/feature/orderbook/sweep_detection.py) | 大单扫盘检测 |
| [spoof_detection.py](../domain/feature/orderbook/spoof_detection.py) | 假挂单检测 |
| [microprice.py](../domain/feature/orderbook/microprice.py) | 微价格 |
| [liquidity_shift.py](../domain/feature/orderbook/liquidity_shift.py) | 流动性迁移 |
| [trade_feature.py](../domain/feature/trade/trade_feature.py) | 交易特征 |
| [indicators/](../domain/feature/indicators/) | 技术指标探测器 |

