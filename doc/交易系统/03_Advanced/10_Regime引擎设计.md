# TradeAgent Regime Engine（市场状态引擎）设计文档

---

# 🧠 一、模块定位

## 1.1 核心作用

Regime Engine 是整个系统的"环境感知层"，负责判断当前市场处于哪种状态，从而让下游模块（Decision / Risk / Position）做出适配当前环境的决策。

## 1.2 在系统中的位置

```
Data → Feature → Factor → Regime Engine → Decision → Risk → Position → Execution
                                    ↓
                              Monitoring
```

## 1.3 核心目标

```
输入：多资产 + 多因子数据
输出：市场状态（Regime）+ 置信度 + 风险等级 + 驱动因素
```

---

# 🎯 二、输出结构（标准接口）

## 2.1 完整输出

```json
{
  "regime": "TRENDING | RANGE | PANIC | EUPHORIA | RISK_OFF | UNCERTAIN",
  "confidence": 0.85,
  "risk_level": 0-100,
  "drivers": ["volatility_spike", "ETF_outflow", "negative_news"],
  "regime_scores": {
    "TRENDING": 0.2,
    "RANGE": 0.1,
    "PANIC": 0.6,
    "EUPHORIA": 0.05,
    "RISK_OFF": 0.05
  },
  "timeframe": "1h",
  "duration": 5,
  "timestamp": 1710000000
}
```

## 2.2 输出字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| regime | enum | 当前市场状态 |
| confidence | float | 置信度 [0.5, 1.0] |
| risk_level | int | 风险等级 [0, 100] |
| drivers | list | 主要驱动因素 |
| regime_scores | dict | 各状态分数分布 |
| timeframe | string | 判定时间框架 |
| duration | int | 当前状态持续周期数 |
| timestamp | int | 更新时间戳 |

---

# 🏷️ 三、Regime 分类定义

## 3.1 五类状态（充分且必要）

| Regime | 特征 | 策略适配 |
|--------|------|----------|
| **TRENDING** | 低波动 + 明确方向 | 趋势跟踪 |
| **RANGE** | 低趋势 + 中波动 | 震荡/均值回归 |
| **PANIC** | 高波动 + 下跌 + ETF流出 | 禁止开多/减仓 |
| **EUPHORIA** | 上涨过快 + 贪婪 | 可能反转/轻仓做空 |
| **RISK_OFF** | 宏观主导（黄金涨/原油涨） | 降低风险暴露 |

## 3.2 UNCERTAIN 状态（特殊处理）

当多时间框架信号不一致时，输出 UNCERTAIN：
- 1h 和 1d 信号不一致
- 置信度 < 0.6
- 此时只做轻仓或观望

---

# 📊 四、输入因子设计

## 4.1 四层输入结构

```
Layer 1: 市场结构（价格）
├── trend_score（趋势强度）
├── momentum（动量）
└── drawdown（回撤）

Layer 2: 波动风险
├── volatility（ATR/std）
└── volatility_spike（波动率突增）

Layer 3: 资金流
├── ETF inflow/outflow
└── volume_anomaly（成交量异常）

Layer 4: 宏观 + 情绪
├── gold_return
├── oil_return
├── fear_greed
└── news_sentiment（LLM）
```

## 4.2 标准化要求

所有输入因子统一标准化到 [-1, 1] 范围：
- 使用 z-score / tanh / min-max
- 确保不同量纲的因子可比较

---

# 🧮 五、核心计算逻辑

## 5.1 子评分计算

### 5.1.1 趋势分

```python
trend_score = 0.6 * momentum + 0.4 * MA_slope
```

### 5.1.2 波动分

```python
vol_score = normalized_volatility  # ATR / price 或 std / mean
```

### 5.1.3 资金流分

```python
flow_score = ETF_inflow_zscore + volume_anomaly_score
```

### 5.1.4 宏观分

```python
macro_score = -w1 * gold_return - w2 * oil_spike
# 负号：风险资产与黄金/原油反向
```

### 5.1.5 情绪分

```python
sentiment_score = 0.5 * fear_greed + 0.5 * news_sentiment
```

## 5.2 Regime 判定规则（核心）

### 5.2.1 PANIC 判定

```python
if vol_score > 0.8 AND trend_score < -0.5:
    regime = "PANIC"
```

### 5.2.2 EUPHORIA 判定

```python
if sentiment_score > 0.7 AND trend_score > 0.5:
    regime = "EUPHORIA"
```

### 5.2.3 TRENDING 判定

```python
if abs(trend_score) > 0.6 AND vol_score < 0.6:
    regime = "TRENDING"
```

### 5.2.4 RANGE 判定

```python
if abs(trend_score) < 0.3 AND vol_score < 0.5:
    regime = "RANGE"
```

### 5.2.5 RISK_OFF 判定

```python
if macro_score < -0.6:
    regime = "RISK_OFF"
```

## 5.3 判定优先级

```
PANIC > EUPHORIA > RISK_OFF > TRENDING > RANGE
```

当多个条件同时满足时，按优先级选择。

---

# ⏱️ 六、Regime 惯性机制（Hysteresis）

## 6.1 问题

纯规则判定会导致 Regime 在临界点频繁切换，造成信号震荡。

## 6.2 解决方案：稳定周期

```python
class RegimeEngine:
    def __init__(self):
        self.current_regime = None
        self.pending_regime = None
        self.regime_duration = 0
        self.MIN_DURATION = 3  # 连续3次确认才切换
        self.MIN_DURATION_URGENT = 2  # PANIC可稍快

    def update(self, raw_regime):
        if raw_regime == self.current_regime:
            self.regime_duration += 1
            self.pending_regime = None
        else:
            if raw_regime == self.pending_regime:
                self.regime_duration += 1
            else:
                self.pending_regime = raw_regime
                self.regime_duration = 1

        # 判断是否满足切换条件
        min_dur = self.MIN_DURATION_URGENT if raw_regime == "PANIC" else self.MIN_DURATION

        if self.regime_duration >= min_dur:
            if self.pending_regime and self.can_transition(self.current_regime, self.pending_regime):
                self.current_regime = self.pending_regime
                self.regime_duration = 0
                self.pending_regime = None
```

## 6.3 切换规则限制

```python
IMPOSSIBLE_TRANSITIONS = {
    "PANIC": ["EUPHORIA"],      # 恐慌后不会立刻过热
    "EUPHORIA": ["PANIC"],      # 过热后不会立刻恐慌
    "TRENDING": ["RANGE"],     # 趋势后不会立刻震荡（需经过RANGE）
}

def can_transition(self, from_regime, to_regime):
    if to_regime in IMPOSSIBLE_TRANSITIONS.get(from_regime, []):
        return False
    return True
```

---

# 🔗 七、多时间框架融合

## 7.1 框架权重

| 时间框架 | 权重 | 作用 |
|----------|------|------|
| 1h | 0.5 | 主判断 |
| 1d | 0.3 | 背景趋势 |
| 5m | 0.2 | 入场时机 |

## 7.2 融合规则

```python
def compute_final_regime():
    tf_5m = detect_regime("5m")
    tf_1h = detect_regime("1h")
    tf_1d = detect_regime("1d")

    # 核心规则：1h 和 1d 必须一致
    if tf_1h != tf_1d:
        return {
            "regime": "UNCERTAIN",
            "confidence": 0.5,
            "reason": "multi_timeframe_mismatch"
        }

    # 5m 只用于确认
    if tf_5m != tf_1h:
        return {
            "regime": tf_1h,
            "confidence": 0.7,
            "reason": "5m_confirming"
        }

    return {
        "regime": tf_1h,
        "confidence": 0.9,
        "reason": "aligned"
    }
```

---

# 📏 八、置信度计算

## 8.1 计算公式

```python
def compute_confidence(regime_scores):
    sorted_scores = sorted(regime_scores.values(), reverse=True)
    top_score = sorted_scores[0]
    second_score = sorted_scores[1]

    gap = top_score - second_score
    confidence = 0.5 + 0.5 * min(gap, 1.0)

    # 数据不足打折
    if self.data_samples < MIN_SAMPLES:
        confidence *= 0.8

    return confidence
```

## 8.2 置信度等级

| 范围 | 等级 | 操作建议 |
|------|------|----------|
| 0.9 - 1.0 | 极高 | 正常执行 |
| 0.7 - 0.9 | 高 | 正常执行 |
| 0.6 - 0.7 | 中 | 降低仓位50% |
| 0.5 - 0.6 | 低 | 观望 |
| < 0.5 | 极低 | 不执行 |

---

# 📉 九、Risk Index 计算

## 9.1 公式

```
RiskIndex = 0.4 * Vol + 0.3 * Drawdown + 0.2 * Flow + 0.1 * Macro
```

所有项已标准化到 [0, 1]，1 = 高风险。

## 9.2 风险等级划分

| Range | Level | 说明 |
|-------|-------|------|
| 0 - 30 | LOW | 正常交易 |
| 30 - 60 | MEDIUM | 谨慎 |
| 60 - 80 | HIGH | 降仓 |
| 80 - 100 | EXTREME | 禁止开仓 |

---

# 🎯 十、Regime 专属仓位规则

## 10.1 规则表

```python
REGIME_RULES = {
    "TRENDING": {
        "max_position": 0.30,
        "max_leverage": 3,
        "allow_short": False,
        "allow_new_entries": True,
        "strategy": "trend_following"
    },
    "RANGE": {
        "max_position": 0.20,
        "max_leverage": 2,
        "allow_short": True,
        "allow_new_entries": True,
        "strategy": "mean_reversion"
    },
    "PANIC": {
        "max_position": 0.10,
        "max_leverage": 1,
        "allow_short": False,
        "allow_new_entries": False,
        "action": "reduce_existing"
    },
    "EUPHORIA": {
        "max_position": 0.15,
        "max_leverage": 2,
        "allow_short": True,
        "allow_new_entries": True,
        "take_profit_tighter": True
    },
    "RISK_OFF": {
        "max_position": 0.15,
        "max_leverage": 1,
        "allow_short": False,
        "allow_new_entries": False,
        "action": "hedge_only"
    },
    "UNCERTAIN": {
        "max_position": 0.10,
        "max_leverage": 1,
        "allow_short": False,
        "allow_new_entries": False,
        "action": "observe_only"
    }
}
```

## 10.2 规则生效优先级

```
1. Regime 规则（最高优先）
2. Risk Index 规则
3. 基础风控规则（硬编码）
```

---

# 🔌 十一、与下游模块对接

## 11.1 对接 Decision Engine

```python
class DecisionEngine:
    def __init__(self, regime_engine):
        self.regime_engine = regime_engine

    def make_decision(self, factor_signals):
        regime = self.regime_engine.get_current_regime()
        rules = REGIME_RULES[regime]

        if not rules["allow_new_entries"]:
            return {
                "action": "HOLD",
                "reason": f"regime={regime}",
                "regime_rules_applied": True
            }

        base_signal = self.compute_base_signal(factor_signals)
        signal = self.apply_regime_rules(base_signal, rules)

        return signal

    def apply_regime_rules(self, signal, rules):
        signal.max_position = rules["max_position"]
        signal.max_leverage = rules["max_leverage"]
        signal.allow_short = rules["allow_short"]

        if rules.get("take_profit_tighter"):
            signal.tp_multiplier *= 0.8

        return signal
```

## 11.2 对接 Risk Engine

```python
class RiskEngine:
    def adjust_for_regime(self, base_risk, regime):
        regime_multipliers = {
            "TRENDING": 1.0,
            "RANGE": 0.9,
            "PANIC": 1.5,
            "EUPHORIA": 1.2,
            "RISK_OFF": 1.3,
            "UNCERTAIN": 1.4
        }

        return base_risk * regime_multipliers.get(regime, 1.0)
```

## 11.3 对接 Position Engine

```python
class PositionEngine:
    def compute_position(self, signal, regime):
        rules = REGIME_RULES[regime]

        position = super().compute_position(signal)

        position.size = min(position.size, rules["max_position"])
        position.leverage = min(position.leverage, rules["max_leverage"])

        return position
```

---

# 📝 十二、Drivers（驱动因素）

## 12.1 预定义驱动因素

| Driver | 含义 |
|--------|------|
| volatility_spike | 波动率急剧上升 |
| ETF_outflow | ETF资金持续流出 |
| ETF_inflow | ETF资金持续流入 |
| negative_news | 重大负面新闻 |
| positive_news | 重大正面新闻 |
| gold_surge | 黄金大涨（宏观风险） |
| oil_surge | 原油大涨 |
| fear_extreme | 极度恐慌 |
| greed_extreme | 极度贪婪 |
| volume_anomaly | 成交量异常 |
| drawdown_high | 回撤过大 |

## 12.2 Drivers 生成规则

```python
def extract_drivers(regime, vol_score, flow_score, sentiment_score, macro_score):
    drivers = []

    if vol_score > 0.7:
        drivers.append("volatility_spike")

    if flow_score < -0.5:
        drivers.append("ETF_outflow")
    elif flow_score > 0.5:
        drivers.append("ETF_inflow")

    if sentiment_score < -0.6:
        drivers.append("negative_news")
    elif sentiment_score > 0.6:
        drivers.append("positive_news")

    if macro_score < -0.5:
        drivers.append("gold_surge")

    return drivers
```

## 12.3 Drivers 用途

1. **信号质量评分输入**
2. **LLM 解释生成**
3. **通知内容生成**
4. **历史复盘分析**

---

# 🧪 十三、信号质量评分集成

## 13.1 Regime 匹配度

```python
REGIME_MATCH = {
    ("LONG", "TRENDING"): 1.0,
    ("LONG", "RANGE"): 0.6,
    ("LONG", "PANIC"): 0.1,
    ("LONG", "EUPHORIA"): 0.3,
    ("LONG", "RISK_OFF"): 0.2,
    ("SHORT", "EUPHORIA"): 1.0,
    ("SHORT", "PANIC"): 0.3,
    ("SHORT", "TRENDING"): 0.5,
}
```

## 13.2 综合信号质量

```python
def compute_signal_quality(signal, regime, drivers):
    quality = 1.0

    match_score = REGIME_MATCH.get((signal.direction, regime), 0.5)
    quality *= match_score

    if "volatility_spike" in drivers:
        quality *= 0.7

    if "ETF_outflow" in drivers and signal.direction == "LONG":
        quality *= 0.8

    if "negative_news" in drivers:
        quality *= 0.8

    return quality
```

---

# 🔄 十四、运行节奏

| 场景 | 检测频率 | 说明 |
|------|----------|------|
| 正常 | 每5分钟 | 1h周期判断 |
| Regime切换时 | 每1分钟 | 确认稳定性 |
| PANIC检测 | 实时 | 快速响应 |

---

# 🚀 十五、版本路线

## 15.1 v1（当前版本）

- 规则 + 打分模型
- 可解释 + 可回测
- 五类 Regime
- 多时间框架融合

## 15.2 v2（计划）

- 加入 HMM（隐马尔可夫）做状态平滑
- Regime 持续时间建模

## 15.3 v3（计划）

- LLM 做 Regime 解释/辅助判断
- 极端情况下的专家模式

## 15.4 v4（远期）

- 自动学习权重（贝叶斯优化）
- 动态 Regime 数量

---

# ⚠️ 十六、常见错误

| 错误 | 后果 | 正确做法 |
|------|------|----------|
| Regime切换太灵敏 | 信号震荡 | 加MIN_DURATION |
| 不限制转换 | 物理不可能的跳变 | 加IMPOSSIBLE_TRANSITIONS |
| 多时间框架不校准 | 噪音过大 | 1h和1d必须一致 |
| Regime规则不锁死 | 执行不一致 | 规则表硬编码 |
| 全用ML做Regime | 不可解释/不可回测 | v1用规则 |

---

# 🧠 十七、一句话总结

> Regime Engine = 系统的"环境感知层"，核心不是复杂，而是稳定 + 可解释 + 可执行。

---

# 🔗 关联文档

- [决策系统设计](./决策系统.md)
- [风险模型设计](./风险模型设计.md)
- [仓位引擎设计](./仓位引擎设计.md)
- [因子系统](./因子系统.md)
