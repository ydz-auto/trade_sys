# 策略清理与重构指南

> 基于现有策略代码库分析 + 架构评估

## 一、策略分类矩阵

| 分类 | 策略数量 | 处理方式 | 目标架构 |
|------|---------|---------|---------|
| **核心保留（重构为 V2）** | 4-6 | 重构为 V2 架构 | State + Event 驱动 |
| **合并整合** | 3-4 | 合并到现有策略 | 减少重复逻辑 |
| **降级为辅助** | 2-3 | 作为特征/过滤器，不单独发信号 | |
| **归档（暂不删除）** | 3-5 | 标记为 `legacy_`，默认禁用 | 保留历史回测用 |

---

## 二、详细策略评估

### ✅ 第一梯队：核心保留（重构为 V2）

| 策略名称 | 评分 | 为什么保留 | V2 状态 |
|---------|------|-----------|---------|
| `OpenInterestBehaviorStrategy` | 8.5/10 | 最符合我们的架构，基于真实仓位行为 | ✅ 已重构为 `OpenInterestBehaviorV2` |
| `TradePressureExhaustionStrategy` | 8.0/10 | 最能体现"事件驱动"理念 | ✅ 已重构为 `TradePressureExhaustionV2` |
| `FundingExtremeReversalStrategy` | 7.8/10 | 市场共识度高，逻辑清晰 | ✅ 已重构为 `FundingExtremeReversalV2` |
| `LiquidationCascadeStrategy` | 7.5/10 | 事件驱动，数据来源可靠 | ✅ 已重构为 `LiquidationCascadeV2` |

---

### ⚠️ 第二梯队：需要整合/调整

| 策略名称 | 评分 | 问题 | 建议处理 |
|---------|------|------|---------|
| `TradePressureSqueezeStrategy` | 7.0/10 | 与 Pressure 系列其他策略逻辑重复 | 合并到 `TradePressureExhaustionV2` |
| `TradePressureAbsorptionStrategy` | 6.5/10 | 逻辑太松，交易频繁 | 合并/改造为过滤器 |
| `CVDDivergenceStrategy` | 6.8/10 | 特征计算方式需验证，防止 Lookahead | 暂时保留为辅助特征 |
| `PanicReversalStrategy` | 7.0/10 | 逻辑尚可，但与其他反转策略重叠 | 合并到 `TradePressureExhaustionV2` |
| `VolumeClimaxFadeStrategy` | 6.5/10 | 与 Pressure 系列重复 | 整合为特征 |
| `AuctionLiquidityHunt` | 7.5/10 | 有特色，逻辑清晰 | **待定** - 评估是否真的需要 |
| `TrendExhaustionStrategy` | 6.5/10 | 与其他策略重叠 | 整合为特征 |
| `WeakBounceShortStrategy` | 6.2/10 | 需要 State 确认 | 暂时禁用，或降级为辅助 |
| `BreakoutContinuationStrategy` | 7.0/10 | 逻辑尚可 | **待定** - 看是否有真实 edge |
| `MeanReversionRegimeStrategy` | 6.8/10 | Regime 意识好，但与 State Machine 重叠 | 整合到 State Machine 本身 |
| `VolatilityExpansionStrategy` | 6.5/10 | 一般 | 降级为过滤器 |
| `OrderflowImbalanceStrategy` | 7.2/10 | 有特色，但受限于合成 Orderbook | 保留为辅助特征 |
| `LongShortPressureDivergence` | 7.0/10 | 与 Pressure 系列重复 | 合并 |
| `SqueezeMomentumStrategy` | 6.8/10 | 与 Squeeze Regime 重叠 | 整合到 State Machine |

---

### ❌ 第三梯队：降级/归档

| 策略名称 | 评分 | 为什么不保留 | 处理建议 |
|---------|------|-------------|---------|
| `RSIMeanReversionStrategy` | 5.5/10 | 传统指标，容易过拟合 | 🔴 标记为 `legacy_rsi_strategy`，默认禁用 |
| `MACDCrossoverStrategy` | 5.0/10 | 经典但弱，现代市场难获利 | 🔴 标记为 `legacy_macd_strategy`，默认禁用 |
| `WhaleTradeStrategy` | 6.0/10 | 大单检测假阳性高 | 🟡 降级为辅助特征（不单独发信号） |
| `FundingRateArbitrageStrategy` | 5.5/10 | 永续合约中套利空间很小 | 🔴 标记为 `legacy_funding_arbitrage`，默认禁用 |
| `LSTMRegimePredictor` | 6.0/10 | 计算重，样本外表现待验证 | 🟡 标记为 `experimental_lstm`，默认禁用 |
| `AdaptiveHybridStrategy` | 6.5/10 | 逻辑复杂，维护难 | 🟡 标记为 `experimental_hybrid`，默认禁用 |
| `MultiFactorConfluence` | 7.0/10 | 逻辑尚可，但应该是一个"Signal Orchestrator" | 🟡 重构为 V2 的 Signal Combiner，而非策略 |

---

## 三、具体执行步骤

### Phase 1: 快速归档（30 分钟）
1. 重命名所有 legacy 策略为 `legacy_*`
2. 在注册表中默认禁用它们
3. 添加 deprecation warning
4. 保留代码但不参与实盘/回测

### Phase 2: 整合重复策略（1-2 天）
1. 合并所有 Pressure 系列策略到 `TradePressureExhaustionV2`
2. 把其他策略转化为特征/过滤器
3. 整合到 State Machine 中

### Phase 3: 完善 V2 生态（3-5 天）
1. 完善 State Machine 的转换规则
2. 添加完整的 Event Detector
3. 实现统一的 Signal Orchestrator

---

## 四、最终目标策略清单（V2）

| 优先级 | V2 策略 | 类型 | 描述 |
|-------|---------|------|------|
| P0 | `OpenInterestBehaviorV2` | State 感知 | 仓位行为策略 |
| P0 | `TradePressureExhaustionV2` | Event 驱动 | 交易压力事件策略 |
| P1 | `FundingExtremeReversalV2` | State 感知 | 资金费率策略 |
| P1 | `LiquidationCascadeV2` | Event 驱动 | 爆仓连锁策略 |
| P2 | `SignalCombiner` | Orchestrator | 多信号组合器（非策略） |

**总计：4-5 个核心策略** → 简洁、高信号质量、可维护

---

## 五、架构对比：V1 vs V2

| 维度 | V1（现有） | V2（重构） |
|------|----------|----------|
| 策略数量 | ~24-26 个 | 4-5 个 + Orchestrator |
| 参数方式 | 散参数 `params['x']` | 类型化 `StrategyConfigV2` |
| 信号触发 | 特征堆 `if zscore < -3 and ...` | 语义化 `state.is_exhausted()` |
| 事件处理 | 没有统一事件体系 | `EventDrivenStrategy` 基类 |
| 状态管理 | 每个策略自己维护 | 统一 `MarketStateMachine` |
| 可回放性 | 低（策略内部状态） | 高（无状态策略 + 完整 State 历史） |
| 可维护性 | 中（逻辑分散） | 高（语义清晰，分层明确） |

---

## 六、回测验证计划

### 验证 1: 代码重构的等效性
- 确保 V2 策略在相同数据上产生相同（或更好）的信号
- 用历史数据验证转换逻辑正确性

### 验证 2: State Machine 稳定性
- 验证 State 转换逻辑的合理性
- 验证不同 Regime 下的行为是否符合预期

### 验证 3: 参数完整性
- 确保 V2 策略没有任何"硬编码"的魔法数字
- 所有参数都在 `StrategyConfigV2` 中

---

## 七、文件重命名/归档清单

```
# 要重命名/归档的策略
strategies.py 中的：
- RsiStrategy → legacy_rsi_strategy
- MACDStrategy → legacy_macd_strategy
- ... (其他 legacy 策略)

behavioral_strategies.py 中的：
- 暂时不动，但逐步迁移到 v2_core_strategies.py

# 新增文件
v2_base.py                (基类 - 已创建)
v2_core_strategies.py     (核心策略 - 已创建)
v2_signal_combiner.py     (信号组合器 - 待创建)
```

---

## 总结

**当前状态：**
- 已创建：新的配置类型、扩展的 EventType、Market State Machine、V2 策略基类、4 个核心 V2 策略
- 待做：执行清理计划、完善 State Machine、验证回测一致性

**核心改进：**
1. ✅ **统一配置** - 不再是散参数，都是类型化的 Config
2. ✅ **事件体系** - 从"特征检测"转为"事件检测器"
3. ✅ **状态管理** - Market State Machine 提供统一事实来源
4. ✅ **语义清晰** - `if state.is_exhausted()` vs `if zscore < -3`

接下来就是执行这个清理计划了！
