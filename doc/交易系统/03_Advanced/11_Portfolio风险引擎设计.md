# TradeAgent Portfolio Risk Engine（组合风险引擎）设计文档

---

# 🧠 一、模块定位

## 1.1 核心问题

你现在的系统是**单标的思维**：
- BTC 多单 → 看 BTC 的风险
- 但真实交易是**多仓位 + 相关性**

## 1.2 组合风险的本质

```
不是你持有什么
而是你"暴露"于什么
```

## 1.3 在系统中的位置

```
Factor → Risk → Portfolio Risk → Decision → Position → Execution
                              ↑
                        Regime Engine
```

---

# 🎯 二、核心输出

## 2.1 完整输出结构

```json
{
  "portfolio_risk": {
    "total_exposure": 0.65,
    "net_exposure": 0.35,
    "gross_exposure": 0.85,
    "risk_concentration": 0.72,
    "correlation_risk": "HIGH",
    "expected_shortfall_95": 0.08,
    "var_95": 0.05,
    "max_drawdown_estimate": 0.12,
    "correlation_matrix": {
      "BTC_ETH": 0.85,
      "BTC_GOLD": -0.30,
      "ETH_GOLD": -0.25
    },
    "risk_contribution": {
      "BTC": 0.45,
      "ETH": 0.35,
      "GOLD_HEDGE": 0.10
    },
    "action_required": "REDUCE",
    "action_amount": 0.15
  }
}
```

## 2.2 字段说明

| 字段 | 说明 |
|------|------|
| total_exposure | 总风险暴露（所有仓位绝对值之和） |
| net_exposure | 净暴露（多头 - 空头） |
| gross_exposure | 总暴露（多头 + 空头） |
| risk_concentration | 风险集中度（HHI指数） |
| correlation_risk | 相关性风险等级 |
| expected_shortfall_95 | 95%置信度下预期亏损（CVaR） |
| var_95 | 95%置信度下最大亏损（VaR） |
| max_drawdown_estimate | 预估最大回撤 |
| correlation_matrix | 资产间相关性矩阵 |
| risk_contribution | 各资产对组合风险的贡献度 |
| action_required | 需要采取的行动 |
| action_amount | 需要调整的仓位比例 |

---

# 📊 三、核心概念

## 3.1 Exposure（暴露）vs Position（仓位）

```
Position = 你持有多少
Exposure = 你暴露于多大的市场波动

Example:
- BTC多单 20%，3x杠杆 → Exposure = 60%
- ETH多单 10%，2x杠杆 → Exposure = 20%
- 总Exposure = 80%

问题：BTC和ETH相关性0.85
→ 实际风险暴露远大于单个仓位之和
```

## 3.2 为什么单标风控不够

```
场景：
- BTC多单 30%
- ETH多单 30%
- 看起来总仓位 60%

实际情况：
- BTC + ETH 相关性 0.85
- 等效风险暴露 ≈ 80%
- 如果BTC跌10% → ETH大概跌8.5%
- 总亏损 ≈ 30% * 10% + 30% * 8.5% = 5.55%

你以为分散了 → 实际没分散
```

---

# 🧮 四、核心计算逻辑

## 4.1 基础暴露计算

```python
def compute_exposure(position):
    exposure = abs(position.size * position.leverage)

    if position.direction == "LONG":
        return exposure
    else:
        return -exposure  # 空头为负

# 总暴露
total_exposure = sum(abs(e) for e in all_exposures)

# 净暴露
net_exposure = sum(all_exposures)

# 总暴露（ gross）
gross_exposure = sum(abs(all_exposures))
```

## 4.2 风险集中度（HHI指数）

```python
def compute_hhi(exposures):
    """
    Herfindahl-Hirschman Index
    衡量风险集中程度
    """
    total = sum(abs(e) for e in exposures)
    if total == 0:
        return 0

    shares = [abs(e) / total for e in exposures]
    hhi = sum(s ** 2 for s in shares)

    return hhi  # 接近1 = 集中，接近0 = 分散

# HHI 判断
hhi > 0.5 → HIGH_CONCENTRATION
hhi > 0.7 → EXTREME_CONCENTRATION
```

## 4.3 动态相关性矩阵

```python
def compute_correlation_matrix(assets, returns_df, window=24):
    """
    计算滚动相关性矩阵
    window = 24小时
    """
    correlations = {}

    for i, asset1 in enumerate(assets):
        for asset2 in assets[i+1:]:
            corr = returns_df[asset1].rolling(window).corr(returns_df[asset2]).iloc[-1]
            correlations[f"{asset1}_{asset2}"] = corr

    return correlations
```

## 4.4 组合波动率

```python
def compute_portfolio_volatility(exposures, correlation_matrix, volatilities):
    """
    组合波动率 = sqrt(w * Σ * w^T)
    """
    n = len(exposures)
    weights = np.array(exposures)
    cov_matrix = correlation_matrix * np.outer(volatilities, volatilities)

    portfolio_vol = np.sqrt(weights @ cov_matrix @ weights.T)

    return portfolio_vol
```

## 4.5 VaR（Value at Risk）

```python
def compute_var(returns, confidence=0.95):
    """
    95%置信度下最大损失
    """
    return np.percentile(returns, (1 - confidence) * 100)
```

## 4.6 Expected Shortfall（CVaR）

```python
def compute_expected_shortfall(returns, confidence=0.95):
    """
    平均亏损（超过VaR的损失）
    这才是真正有意义的尾部风险
    """
    var = compute_var(returns, confidence)
    return returns[returns <= var].mean()
```

## 4.7 风险贡献度

```python
def compute_risk_contribution(position, correlation_matrix, volatilities):
    """
    每个仓位对组合风险的贡献
    """
    exposures = [p.exposure for p in positions]
    weights = np.array(exposures) / sum(exposures)

    portfolio_vol = compute_portfolio_volatility(exposures, correlation_matrix, volatilities)

    marginal_contrib = correlation_matrix @ volatilities @ weights
    risk_contrib = weights * marginal_contrib / portfolio_vol

    return {p.symbol: rc for p, rc in zip(positions, risk_contrib)}
```

---

# ⚠️ 五、风险阈值设计

## 5.1 硬性阈值（触发行动）

```python
PORTFOLIO_RISK_LIMITS = {
    "max_total_exposure": 0.80,      # 总暴露不超过80%
    "max_net_exposure": 0.60,        # 净暴露不超过60%
    "max_gross_exposure": 1.20,     # 总暴露不超过120%（包含杠杆）
    "max_hhi": 0.65,                # HHI不超过0.65
    "max_correlation": 0.90,        # 任意两资产相关性不超过0.9
    "max_var_95": 0.05,             # 单日VaR不超过5%
    "max_es_95": 0.08,              # 单日CVaR不超过8%
    "max_estimated_drawdown": 0.15,  # 预估最大回撤不超过15%
}
```

## 5.2 软性阈值（警告）

```python
PORTFOLIO_RISK_WARNINGS = {
    "total_exposure": 0.60,         # 60%开始警告
    "hhi": 0.50,                    # 0.5开始警告
    "correlation": 0.75,            # 0.75开始警告
}
```

## 5.3 行动级别

```python
def determine_action(portfolio_risk):
    if portfolio_risk.total_exposure > PORTFOLIO_RISK_LIMITS["max_total_exposure"]:
        return "FORCE_REDUCE", portfolio_risk.total_exposure - PORTFOLIO_RISK_LIMITS["max_total_exposure"]

    if portfolio_risk.hhi > PORTFOLIO_RISK_LIMITS["max_hhi"]:
        return "REBALANCE", compute_rebalance_amount()

    if portfolio_risk.correlation_risk == "HIGH":
        return "DIVERSIFY", 0.10

    if portfolio_risk.es_95 > PORTFOLIO_RISK_LIMITS["max_es_95"]:
        return "EMERGENCY_REDUCE", 0.20

    return "OK", 0
```

---

# 🔗 六、与 Regime Engine 联动

## 6.1 Regime 影响组合风险

```python
REGIME_PORTFOLIO_ADJUSTMENTS = {
    "TRENDING": {
        "max_total_exposure_multiplier": 1.0,
        "max_leverage_multiplier": 1.0,
    },
    "RANGE": {
        "max_total_exposure_multiplier": 0.8,
        "max_leverage_multiplier": 0.8,
    },
    "PANIC": {
        "max_total_exposure_multiplier": 0.3,
        "max_leverage_multiplier": 0.5,
        "force_hedge": True,
    },
    "EUPHORIA": {
        "max_total_exposure_multiplier": 0.6,
        "max_leverage_multiplier": 0.7,
        "allow_short": True,
    },
    "RISK_OFF": {
        "max_total_exposure_multiplier": 0.5,
        "max_leverage_multiplier": 0.5,
        "require_hedge": True,
    },
}
```

## 6.2 联动计算

```python
def compute_regime_adjusted_limits(regime):
    base_limits = PORTFOLIO_RISK_LIMITS
    adjustments = REGIME_PORTFOLIO_ADJUSTMENTS.get(regime, REGIME_PORTFOLIO_ADJUSTMENTS["TRENDING"])

    adjusted = {}
    for key, value in base_limits.items():
        multiplier_key = f"{key}_multiplier"
        if multiplier_key in adjustments:
            adjusted[key] = value * adjustments[multiplier_key]
        else:
            adjusted[key] = value

    return adjusted
```

---

# 🔄 七、再平衡逻辑

## 7.1 什么时候需要再平衡

```python
def needs_rebalance(portfolio_risk):
    # 1. 集中度超标
    if portfolio_risk.hhi > PORTFOLIO_RISK_WARNINGS["hhi"]:
        return True, "concentration"

    # 2. 相关性过高
    if portfolio_risk.correlation_risk == "HIGH":
        return True, "correlation"

    # 3. 暴露偏离目标
    if abs(portfolio_risk.total_exposure - TARGET_EXPOSURE) > 0.15:
        return True, "exposure_drift"

    return False, None
```

## 7.2 再平衡目标

```python
TARGET_PORTFOLIO = {
    "BTC": 0.40,      # 目标40%
    "ETH": 0.25,      # 目标25%
    "GOLD_HEDGE": 0.15,  # 15%黄金对冲
    "CASH": 0.20,     # 20%现金
}
```

## 7.3 再平衡执行

```python
def rebalance(current_positions, target_portfolio, portfolio_risk):
    actions = []

    for symbol, target_weight in target_portfolio.items():
        current_weight = portfolio_risk.risk_contribution.get(symbol, 0)

        if abs(current_weight - target_weight) > REBALANCE_THRESHOLD:
            diff = target_weight - current_weight
            actions.append({
                "symbol": symbol,
                "action": "BUY" if diff > 0 else "SELL",
                "weight_change": diff
            })

    return actions
```

---

# 🛡️ 八、对冲策略

## 8.1 相关性对冲

```python
def compute_hedge_ratio(asset1_returns, asset2_returns):
    """
    计算对冲比例（最小方差对冲）
    """
    covariance = np.cov(asset1_returns, asset2_returns)[0][1]
    variance = np.var(asset2_returns)

    return -covariance / variance
```

## 8.2 自动对冲触发

```python
def should_hedge(portfolio_risk, regime):
    # 如果是 RISK_OFF 或 PANIC，自动增加对冲
    if regime in ["RISK_OFF", "PANIC"]:
        return True

    # 如果相关性超过阈值
    if portfolio_risk.correlation_risk == "HIGH":
        return True

    return False
```

## 8.3 对冲操作

```python
def apply_hedge(portfolio_risk, hedge_asset="GOLD"):
    if not should_hedge(portfolio_risk):
        return []

    # 计算需要的对冲比例
    btc_exposure = portfolio_risk.positions["BTC"]
    eth_exposure = portfolio_risk.positions["ETH"]

    avg_correlation = portfolio_risk.correlation_matrix.get("BTC_GOLD", -0.3)
    hedge_ratio = compute_hedge_ratio(btc_exposure, hedge_asset)

    hedge_size = -(btc_exposure + eth_exposure) * abs(avg_correlation) * hedge_ratio

    return [{
        "symbol": "GOLD",
        "action": "BUY",
        "size": hedge_size,
        "reason": "portfolio_hedge"
    }]
```

---

# 🚨 九、紧急风控

## 9.1 触发条件

```python
EMERGENCY_CONDITIONS = {
    "portfolio_es_breach": 0.12,      # CVaR超过12%
    "single_day_loss": 0.06,          # 单日亏损6%
    "consecutive_loss_days": 3,       # 连续3日亏损
    "correlation_spike": 0.95,       # 相关性突增到0.95
}
```

## 9.2 紧急行动

```python
def emergency_reduce(portfolio_risk):
    """
    紧急降仓
    """
    actions = []

    # 1. 平掉最大风险贡献的仓位
    sorted_contrib = sorted(portfolio_risk.risk_contribution.items(), key=lambda x: x[1], reverse=True)

    for symbol, contrib in sorted_contrib:
        if contrib > 0.30:
            actions.append({
                "symbol": symbol,
                "action": "CLOSE",
                "reason": "emergency_risk_contribution",
                "priority": 1
            })

    # 2. 如果不够，平掉所有高相关性仓位
    high_corr_positions = [s for s, c in portfolio_risk.correlation_matrix.items()
                          if abs(c) > 0.85]

    for pos in high_corr_positions:
        actions.append({
            "symbol": pos,
            "action": "CLOSE",
            "reason": "emergency_correlation",
            "priority": 2
        })

    return actions
```

---

# 📊 十、监控面板

## 10.1 实时监控指标

```json
{
  "dashboard": {
    "total_exposure": {
      "value": 0.65,
      "limit": 0.80,
      "status": "NORMAL"
    },
    "net_exposure": {
      "value": 0.35,
      "limit": 0.60,
      "status": "NORMAL"
    },
    "hhi": {
      "value": 0.45,
      "limit": 0.65,
      "status": "WARNING"
    },
    "correlation_risk": {
      "value": "MEDIUM",
      "status": "WARNING"
    },
    "var_95": {
      "value": 0.04,
      "limit": 0.05,
      "status": "NORMAL"
    },
    "es_95": {
      "value": 0.06,
      "limit": 0.08,
      "status": "NORMAL"
    }
  }
}
```

---

# 🔄 十一、运行节奏

| 场景 | 频率 | 说明 |
|------|------|------|
| 正常 | 每5分钟 | 全量计算 |
| 仓位变动 | 实时 | 增量计算 |
| Regime切换 | 立即 | 重新评估限制 |
| 紧急检测 | 实时 | VaR/CVaR监控 |

---

# 🧪 十二、常见错误

| 错误 | 后果 | 正确做法 |
|------|------|----------|
| 只看仓位不看暴露 | 低估风险 | 用 exposure = size * leverage |
| 假设静态相关性 | 市场变时措手不及 | 用动态相关性 |
| 只看 VaR | 忽视尾部风险 | 同时看 CVaR |
| 不考虑 Regime | 风险控制不动态 | Regime 影响限制 |
| 没有再平衡机制 | 风险漂移 | 设置阈值自动触发 |

---

# 🧠 十三、一句话总结

> Portfolio Risk = 不是看你持有什么，而是看你暴露于什么风险。

---

# 🔗 关联文档

- [Regime引擎设计](./Regime引擎设计.md)
- [风险模型设计](./风险模型设计.md)
- [仓位引擎设计](./仓位引擎设计.md)
