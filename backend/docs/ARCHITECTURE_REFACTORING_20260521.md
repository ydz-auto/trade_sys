# Architecture Refactoring Report - 2026-05-21 (Updated)

## Executive Summary

成功完成统一架构收敛，消除 Research Pipeline 和 Runtime Pipeline 的分叉问题。

**核心改进：**
- 删除了 `scripts/` 目录（100+ 个脚本）
- 统一了 Feature 计算逻辑（在线/离线一致）
- 统一了回测引擎（走 Runtime Pipeline）
- 添加了数据泄漏保护机制

---

## 1. 统一 Runtime Pipeline

### 1.1 核心架构

所有路径（Live/Replay/Optimization/Backtest）都走同一条 Pipeline：

```
ingestion_runtime / replay_runtime
        ↓
feature_runtime / domain/feature/unified_calculator.py
        ↓
feature_matrix
        ↓
signal_runtime
        ↓
execution_runtime
        ↓
projection_runtime
```

### 1.2 关键原则

| 原则 | 说明 |
|------|------|
| **事件驱动** | 所有数据流都是事件流 |
| **Feature Matrix 是中央真相** | 所有特征都通过 Feature Matrix |
| **防止数据泄漏** | FeatureAvailabilityGuard 检查特征可用性 |
| **在线/离线一致** | UnifiedFeatureCalculator 确保计算逻辑相同 |

---

## 2. 删除的模块

### 2.1 scripts/ 目录（已删除）

所有脚本已迁移到对应模块：

| 已删除的脚本 | 替代方案 |
|-------------|----------|
| scripts/generate_features.py | domain/feature/generation_service.py |
| scripts/generate_orderbook_features.py | domain/feature/generation_service.py |
| scripts/run_backtest.py | application/backtest_service.py |
| scripts/backtest_all_strategies.py | application/backtest_service.py |
| scripts/strategy_optimization_backtest.py | application/backtest_service.py |
| scripts/download_binance_*.py | runtime/ingestion_runtime/download_service.py |
| scripts/train_lstm_strategy.py | domain/ml/lstm_dataset_builder.py |

---

## 3. 新建的核心模块

### 3.1 统一特征计算

```
domain/feature/
├── unified_calculator.py   # 统一特征计算器（在线/离线一致）
├── generation_service.py   # 特征生成服务
└── materializer/           # 特征材料化器
    ├── schema_registry.py  # 特征 Schema（含 available_after_periods）
    └── matrix_builder.py   # 特征矩阵（含时间纪律）
```

**关键特性：**
- `UnifiedFeatureCalculator` - 所有特征计算的统一入口
- `FeatureSchema` - 每个特征有 `available_after_periods` 定义
- `get_available_time()` - 计算特征可用时间

### 3.2 统一回测引擎

```
application/
├── optimization_service/
│   ├── engine.py           # 回测引擎（走 Runtime Pipeline）
│   ├── service.py          # 优化服务
│   └── models.py           # 数据模型
└── backtest_service.py     # 回测服务
```

**关键特性：**
- 使用 `shared/replay/market_event_emitter.py` 发出事件流
- 使用 `FeatureAvailabilityGuard` 防止数据泄漏
- 支持滑点、延迟、部分成交等真实模拟

### 3.3 数据泄漏保护

```
shared/replay/
├── market_event_emitter.py       # 事件发射器
├── feature_availability_guard.py # 防泄漏守卫
└── orchestrator.py               # 回放协调器
```

**关键特性：**
- `filter_available_features()` - 过滤不可用特征
- 基于时间戳检查特征可用性
- 记录泄漏统计信息

---

## 4. 测试验证

### 4.1 测试结果

```
============================================================
测试结果汇总
============================================================
  模块导入: ✅ 通过
  特征计算器: ✅ 通过
  特征 Schema: ✅ 通过
  数据泄漏保护: ✅ 通过
  回测配置: ✅ 通过
  策略注册表: ✅ 通过

总计: 6/6 测试通过
```

### 4.2 验证的功能

| 功能 | 验证结果 |
|------|----------|
| 特征计算 | 21 个特征正确计算，RSI 范围 0-100 |
| 特征 Schema | RSI_14 有 14 周期延迟定义 |
| 数据泄漏保护 | FeatureAvailabilityGuard 正常工作 |
| 回测配置 | 所有参数正确配置 |
| 策略注册 | 6 个策略已注册 |

---

## 5. 架构边界

### 5.1 层级职责

| 层级 | 职责 | 包含 |
|------|------|------|
| **domain/** | 核心领域模型 | 模型、配置、纯逻辑 |
| **application/** | 应用服务 | 业务编排、优化服务 |
| **runtime/** | 运行时编排 | Kafka 消费者、生命周期 |
| **services/** | 业务逻辑 | 服务实现、适配器 |
| **shared/** | 跨层关注点 | 回放编排、合约 |
| **infrastructure/** | 技术基础设施 | 数据库、消息、缓存 |

### 5.2 关键决策

1. **Feature Matrix 是中央真相**：所有特征都通过 Feature Matrix
2. **Domain 模型是纯的**：无基础设施依赖
3. **Runtime 只做编排**：不实现业务逻辑
4. **防止数据泄漏**：所有特征有时间纪律

---

## 6. 文件变更总结

### 6.1 新建文件

```
domain/feature/unified_calculator.py    # 统一特征计算器
domain/feature/generation_service.py    # 特征生成服务
domain/ml/lstm_dataset_builder.py       # LSTM 数据集构建器

application/backtest_service.py         # 回测服务
application/optimization_service/engine.py  # 优化回测引擎

runtime/ingestion_runtime/download_service.py  # 数据下载服务

shared/replay/market_event_emitter.py   # 事件发射器

DEPRECATED.py                           # 废弃模块记录
```

### 6.2 删除文件

```
scripts/  # 整个目录已删除
```

### 6.3 修改文件

```
application/services/__init__.py        # 修复导入
application/optimization_service/service.py  # 更新类名
```

---

## 7. 统一架构图

```
                    ┌─────────────────────────────────────┐
                    │         Exchange / News             │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      ingestion_runtime              │
                    │   (download_service.py)             │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      domain/feature/                │
                    │   (unified_calculator.py)           │
                    │   (generation_service.py)           │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      Feature Matrix                 │
                    │      (Central Truth)                │
                    └─────────────────┬───────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
┌─────────▼─────────┐     ┌──────────▼──────────┐     ┌─────────▼─────────┐
│   signal_runtime  │     │   replay_runtime    │     │  optimization     │
│                   │     │                     │     │     service       │
└─────────┬─────────┘     └──────────┬──────────┘     └─────────┬─────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      execution_runtime              │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      projection_runtime             │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │           Frontend                  │
                    └─────────────────────────────────────┘
```

---

## 8. 下一步

1. **运行参数优化** - 使用 2024 年数据优化策略参数
2. **运行回测** - 使用 2025-2026 年数据验证策略
3. **监控数据泄漏** - 确保优化结果与实盘一致

---

**状态:** ✅ 重构完成  
**日期:** 2026-05-21  
**测试:** 6/6 通过
