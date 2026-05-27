# MarketStateMachine 迁移计划

> 现状分析 + 分阶段迁移路线图

---

## 📊 现状分析

### ✅ 已完成

| 模块 | 状态 | 说明 |
|-----|------|------|
| MarketState 定义 | ✅ Done | Regime/Liquidity/Pressure/Volatility/Trend 5维状态空间 |
| MarketStateMachine | ✅ Done | 事件驱动的状态转换引擎 |
| V2 策略基类 | ✅ Done | StateAware/EventDriven/RegimeAware |
| V2 Core Strategies | ✅ Done | Top 5 策略重构（OpenInterest/TradePressure/Funding/Liquidation/Momentum） |
| V2 Orchestrator | ✅ Done | Multi-Strategy 编排器（Regime-based） |
| Domain Kernel | ✅ Done | 三范式统一运行时 |
| 完整文档 | ✅ Done | THREE_PARADIGM_UNIFIED_RUNTIME.md 等 |

### ❌ 未完成

| 模块 | 问题 |
|-----|------|
| 旧策略 | strategies.py 和 behavioral_strategies.py 中的 24~26 个策略仍在使用特征堆 if 判断 |
| 回放引擎 | replay_runtime 中的引擎未集成 V2 架构 |
| 回测引擎 | backtest_engine.py 未集成 |
| 其他 runtime | 其他 engine 未集成 |

---

## 🎯 核心问题

**MarketStateMachine 还没有用在您实际运行的系统中！**

---

## 📋 迁移计划（分阶段）

### Phase 0: 验证阶段（1天）
- [ ] 运行 V2 示例，验证 MarketStateMachine 工作正常
- [ ] 并行验证：V1 vs V2 信号一致性
- [ ] 检查没有回归问题

### Phase 1: 核心策略迁移（3~5天）
- [ ] 先迁移 Top 2 策略：
  - OpenInterestBehaviorStrategy（评分最高）
  - TradePressureExhaustionStrategy（核心策略）
- [ ] 在现有 runtime 中做「桥接」：
  - 保持旧策略不动
  - 新增 V2 策略并行运行
- [ ] 在回测中对比 V1 vs V2

### Phase 2: 核心引擎集成（5~7天）
- [ ] 在 replay_runtime 中集成 DomainKernel
- [ ] 在 backtest_engine 中集成 MarketStateMachine
- [ ] 支持并行运行（V1 和 V2 同时运行）

### Phase 3: 完全迁移（2周）
- [ ] 迁移完 Top 5 策略
- [ ] 把其他策略标记为 Legacy（放在 legacy/ 目录）
- [ ] 把 V2 设为默认

### Phase 4: 三范式验证（1周）
- [ ] LIVE/REPLAY/RESEARCH 三范式并行验证
- [ ] 完整回放测试
- [ ] 一致性保证

---

## 💡 快速开始方案

### 方案 A: 并行运行（推荐）

保持旧系统不动，新增 V2 系统并行运行：
```
现有系统 (V1, 旧策略) ──┐
                         ├── Orchestrator ── 执行
V2 新系统 (MarketState) ──┘
```

**优点**:
- 零风险
- 可以对比 V1 vs V2
- 渐进式迁移

### 方案 B: 直接替换（风险高）

把现有策略直接替换为 V2。

**不推荐**，除非 V1 已经验证 100% 一致。

---

## 🎯 下一步（今天可做）

1. **运行示例** 验证 MarketStateMachine 正常
   ```bash
   python -m domain.market_state.examples
   ```

2. **检查文档** 确认理解设计
   - `docs/THREE_PARADIGM_UNIFIED_RUNTIME.md`
   - `docs/FINAL_STRATEGY_PLAN.md`

3. **决定迁移策略** 您想先从哪个策略开始？

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [THREE_PARADIGM_UNIFIED_RUNTIME.md](THREE_PARADIGM_UNIFIED_RUNTIME.md) | 三范式统一架构 |
| [FINAL_STRATEGY_PLAN.md](FINAL_STRATEGY_PLAN.md) | 策略精简计划 |
| [STRATEGY_CLEANUP_GUIDE.md](STRATEGY_CLEANUP_GUIDE.md) | 策略清理指南 |
| [CLOCK_AUTHORITY_USAGE_GUIDE.md](CLOCK_AUTHORITY_USAGE_GUIDE.md) | 时钟使用规范 |
