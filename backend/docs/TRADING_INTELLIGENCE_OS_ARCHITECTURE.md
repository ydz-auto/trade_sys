# 交易智能操作系统架构 - 2026-05-21

## 总览

系统已经从原型进化为**分布式事件驱动交易操作系统**。

## 核心架构图

```
                    ┌─────────────┐
                    │  数据源      │
                    │  (Exchange)  │
                    └──────┬──────┘
                           │
                           ↓
                    ┌──────────────┐
                    │ ingestion    │
                    │ runtime      │
                    └──────┬───────┘
                           │
                           ↓
                    ┌──────────────┐
                    │ Feature      │
                    │ Materializer │
                    └──────┬───────┘
                           │
                           ↓
              ┌───────────────────────────────┐
              │  Feature Matrix (Central Truth) │
              └──────┬────────────────────────┘
                     │
            ┌────────┼────────┐
            │        │        │
            ↓        ↓        ↓
        ┌──────────────────────────┐
        │   Signal Domain          │ ← NEW!
        │  (统一信号层)            │
        └──────┬───────────────────┘
               │
               ↓
        ┌──────────────────┐
        │ Regime Runtime   │ ← NEW!
        │ (市场状态识别)   │
        └──────┬───────────┘
               │
               ↓
        ┌──────────────────┐
        │ Portfolio Runtime│ ← NEW!
        │  (实盘核心)      │
        └──────┬───────────┘
               │
               ↓
        ┌──────────────────────────────┐
        │  Execution Runtime           │
        │  + Execution Intelligence    │ ← NEW!
        └──────┬───────────────────────┘
               │
               ↓
        ┌──────────────────┐
        │ Projection       │
        │ Runtime          │
        └──────┬───────────┘
               │
               ↓
        ┌──────────────────┐
        │   前端           │
        └──────────────────┘
```

## 核心闭环

### Feature → Signal → Portfolio → Execution → Projection

这是现在系统的**完整智能闭环**。

---

## 新模块详解

### 1. domain/signal/ - 统一信号层（最重要）

现在系统最大的缺口被填补了！

```
domain/signal/
├── models/
│   ├── __init__.py
│   ├── Signal              # 统一信号模型
│   ├── SignalDirection     # 信号方向 (long/short/neutral)
│   ├── SignalConfidence    # 信号置信度
│   ├── SignalStrength      # 信号强度
│   └── SignalState         # 信号状态 (pending/active/expired)
│
├── fusion/
│   ├── __init__.py
│   ├── VotingFusion        # 投票融合
│   ├── BlendingFusion      # 加权混合
│   ├── ConsensusFusion     # 共识融合
│   └── EnsembleFusion      # 集成融合
│
├── lifecycle/
│   ├── __init__.py
│   ├── SignalGenerator     # 信号生成
│   ├── SignalDecay         # 信号衰减
│   ├── SignalInvalidation  # 信号失效
│   └── SignalCooldown      # 信号冷却
│
└── registry/
    ├── __init__.py
    └── SignalRegistry      # 信号注册表
```

#### 关键特性：
- **统一信号模型**：所有信号都走这里
- **信号融合**：支持多种融合策略
- **生命周期管理**：生成、衰减、失效、冷却
- **注册表**：集中管理所有信号

---

### 2. runtime/regime_runtime/ - 市场状态识别

策略不应该永远启用，而应该**regime-aware**！

```
runtime/regime_runtime/
└── __init__.py
    ├── MarketRegime        # 市场状态枚举
    │   ├── HIGH_VOLATILITY      # 高波动 → breakout
    │   ├── LOW_VOLATILITY       # 低波动 → reversal
    │   ├── TRENDING             # 趋势 → trend-following
    │   ├── RANGING              # 横盘 → mean-reversion
    │   ├── LIQUIDATION_CASCADE  # 爆仓潮 → liquidation
    │   ├── NARRATIVE_BURST      # 叙事爆发 → momentum
    │   └── LIQUIDITY_DRAIN      # 流动性枯竭 → passive
    │
    └── RegimeRuntime       # 状态识别运行时
```

#### 关键特性：
- **实时状态分类**
- **策略自动启用/禁用**
- **状态历史记录**
- **特征工程支持**

---

### 3. runtime/portfolio_runtime/ - 实盘核心

portfolio 不能只停留在 domain 层，必须 **runtime 化**！

```
runtime/portfolio_runtime/
└── __init__.py
    ├── PortfolioRuntime    # 组合运行时
    │   ├── update_position      # 更新仓位
    │   ├── calculate_exposure   # 计算敞口
    │   ├── check_risk           # 风险检查
    │   ├── allocate_capital     # 资金分配
    │   └── detect_conflicts     # 策略冲突检测
```

#### 关键特性：
- **实时仓位管理**
- **实时风险监控**
- **实时净敞口计算**
- **实时资金分配**
- **策略冲突检测**

---

### 4. domain/execution/intelligence/ - 执行智能

现在不只有 execution quality（智能执行、订单拆分），
还有 **execution intelligence**（滑点预测、市场冲击、流动性估计、执行优化）！

```
domain/execution/intelligence/
├── __init__.py
├── slippage_predictor.py  # 滑点预测器
├── impact_model.py        # 市场冲击模型
├── liquidity_estimator.py # 流动性估计器
└── execution_optimizer.py # 执行优化器
```

#### 关键特性：
- **滑点预测**：预期滑点、标准差、最坏情况
- **市场冲击**：临时冲击、永久冲击、恢复时间
- **流动性估计**：评级、可用深度、滑点估算
- **执行优化**：策略选择、计划生成

---

## 完整系统结构

```
backend/
├── api/                    # API 层
├── application/            # 应用层
├── domain/                 # 领域层
│   ├── feature/            # 特征领域
│   ├── signal/             # 信号领域 ← NEW!
│   ├── execution/          # 执行领域
│   │   └── intelligence/   # 执行智能 ← NEW!
│   ├── replay/             # 回放领域
│   ├── regime/             # 市场状态领域 (TODO)
│   ├── portfolio/          # 组合领域
│   ├── analysis/           # 分析领域
│   └── ...
├── runtime/                # 运行时层
│   ├── ingestion_runtime/
│   ├── feature_runtime/
│   ├── signal_runtime/     # 信号运行时 (TODO)
│   ├── regime_runtime/     # 市场状态运行时 ← NEW!
│   ├── portfolio_runtime/  # 组合运行时 ← NEW!
│   ├── execution_runtime/
│   ├── replay_runtime/
│   ├── projection_runtime/
│   └── orchestrator/
├── services/               # 服务层
├── infrastructure/         # 基础设施层
├── research/               # 研究层
│   └── feature_lab/        # 特征实验室
└── config/
```

---

## 数据流向闭环

### 1. 数据摄入
```
Exchange → ingestion_runtime → Kafka
```

### 2. 特征工程
```
Kafka → Feature Materializer → Feature Matrix
```

### 3. 信号生成
```
Feature Matrix → Signal Domain (fusion/lifecycle)
           ↓
      Regime Runtime (策略选择)
```

### 4. 组合管理
```
Signals → Portfolio Runtime (风险/敞口/分配)
```

### 5. 执行优化
```
Portfolio → Execution Runtime
         ↓
    Execution Intelligence (滑点/冲击/优化)
```

### 6. 状态投影
```
Execution → Projection Runtime → Frontend
```

---

## 优先级路线图

### 第一阶段（已完成）
- [x] domain/signal/ - 统一信号层
- [x] runtime/portfolio_runtime/ - 实盘核心
- [x] runtime/regime_runtime/ - 市场状态识别
- [x] domain/execution/intelligence/ - 执行智能

### 第二阶段（下一步）
- [ ] Execution 真实性验证
- [ ] Replay 真实性验证
- [ ] Position/Risk 模型完善
- [ ] Orderbook 特征工程

### 第三阶段（未来）
- [ ] Ensemble 策略组合
- [ ] Online Learning 在线学习
- [ ] Narrative Intelligence 叙事智能

---

## 关键决策点

### Feature Matrix 是核心真理
所有信号都基于 Feature Matrix，不是分散的因子。

### Signal Domain 是统一层
不再有策略层、执行层各自的信号，全部统一。

### Regime-aware 策略
策略不应该永远开着，要看市场状态。

### Execution Intelligence
执行不仅是下单，还要智能优化。

---

## 总结

系统现在真正进入了**交易智能阶段**！

核心闭环：
**Feature → Signal → Portfolio → Execution → Projection**

所有层级边界清晰，各司其职。
