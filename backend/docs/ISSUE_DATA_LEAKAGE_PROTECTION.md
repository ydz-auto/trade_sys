# Data Leakage Protection - 数据泄漏防护完整方案

## 概述

本文档记录了系统中数据泄漏问题的修复方案和新增的防护机制。

**创建日期**: 2026-05-22  
**状态**: 已实施  
**优先级**: Critical

---

## 一、已识别的泄漏类型

### 1.1 全局统计泄漏 (Global Statistics Leakage)

**风险等级**: ⭐⭐⭐⭐⭐ Critical

**问题描述**:
使用全局 `mean()`, `std()`, `quantile()` 计算统计量，包含了未来所有数据。

**示例**:
```python
# 错误写法
df["z"] = (df["close"] - df["close"].mean()) / df["close"].std()
q_high = volatility.quantile(0.9)
```

**影响**:
- 模型在训练时"看到"了未来数据的分布特征
- 回测结果虚高
- 实盘表现大幅下降

**修复方案**:
```python
# 正确写法
rolling_mean = series.rolling(window=288, min_periods=20).mean()
rolling_std = series.rolling(window=288, min_periods=20).std()
z_score = (series - rolling_mean) / (rolling_std + 1e-8)

# quantile 也必须用 rolling
q_high = volatility.rolling(window=288, min_periods=20).quantile(0.9)
```

### 1.2 多周期聚合泄漏 (Multi-Period Aggregation Leakage)

**风险等级**: ⭐⭐⭐⭐ High

**问题描述**:
在周期未结束时使用完整的聚合数据。

**示例**:
```
时间: 10:15
错误: 使用 10:00~11:00 完整的 1h K线数据
正确: 只能使用 10:00~10:15 的 partial candle
```

**修复方案**:
使用 `FeatureAvailabilityGuard` 检查特征可用性。

### 1.3 Label 污染 (Label Contamination)

**风险等级**: ⭐⭐⭐⭐⭐ Critical

**问题描述**:
`future_return`, `target` 等标签被混入特征 DataFrame。

**示例**:
```python
# 错误写法
df['future_return_1h'] = df['close'].shift(-12)
features = df[feature_columns]  # future_return_1h 可能被误加入
```

**修复方案**:
使用 `PointInTimeFeatureStore` 隔离 Label。

---

## 二、已修复的文件

| 文件 | 泄漏类型 | 修复方式 |
|------|----------|----------|
| `services/strategy_service/feature_matrix.py` | 全局标准化 | 使用 rolling mean/std |
| `services/research_service/context_engine.py` | 全局 quantile | 使用 rolling quantile |
| `services/research_service/strategy_research_matrix.py` | 全局 quantile | 使用 rolling quantile |
| `services/research_service/crypto_behavioral_playbooks.py` | 全局 quantile | 使用 rolling quantile |
| `research/factor/advanced.py` | 全局 mean/std | 使用 rolling 统计 |
| `research/factor/advanced.py` | sentiment_momentum_combo | 使用 rolling 标准化 |
| `research/correlation/data_preparation.py` | 全局标准化 | 新增 rolling_zscore 方法 |

---

## 三、新增防护机制

### 3.1 Point-In-Time Feature Store

**文件**: `infrastructure/storage/point_in_time_store.py`

**功能**:
- 只允许 `timestamp <= current_runtime_time` 的数据进入
- Label 自动隔离到独立存储
- 记录每个特征的 `available_at` 时间
- 泄漏尝试日志和报告

**用法**:
```python
from infrastructure.storage import get_point_in_time_store

store = get_point_in_time_store("BTCUSDT")

# 存储特征
store.store_feature("volatility_1h", 0.05, timestamp)

# 存储标签（自动隔离）
store.store_feature("future_return_1h", 0.02, timestamp)

# 获取指定时间点可用的特征
snapshot = store.get_features_at_time(query_time)
# future_return_1h 不会出现在 snapshot.features 中

# 获取标签（仅训练时使用）
label = store.get_label_at_time(query_time, "future_return_1h")
```

### 3.2 Feature Generation Guard

**文件**: `domain/feature/generation_guard.py`

**功能**:
- 装饰器模式确保特征生成经过可用性检查
- 上下文管理器跟踪特征生成过程
- 基类继承简化特征提取器实现

**用法 1 - 装饰器**:
```python
from domain.feature import with_feature_guard

@with_feature_guard(feature_names=["volatility_1h", "trend_1h"])
def extract_volatility_features(df, timestamp):
    return {"volatility_1h": ..., "trend_1h": ...}
```

**用法 2 - 上下文管理器**:
```python
from domain.feature import FeatureGenerationContext

with FeatureGenerationContext(replay_clock=timestamp) as ctx:
    ctx.add_feature("spread", 0.02, timestamp)
    ctx.add_feature("volatility_1h", 0.05, timestamp)  # 自动检查可用性
    result = ctx.get_result()
```

**用法 3 - 基类继承**:
```python
from domain.feature import GuardedFeatureExtractor

class MyExtractor(GuardedFeatureExtractor):
    FEATURE_CATEGORY = "microstructure"
    REQUIRES_CLOSED_CANDLE = True
    AGGREGATION_PERIOD_MS = 60000
    
    def _extract_features(self, data, timestamp, **kwargs):
        return {"spread": ..., "imbalance": ...}
```

### 3.3 Live vs Replay 一致性测试

**文件**: `tests/verification/test_live_replay_consistency.py`

**功能**:
- 验证同一时间点 Live Runtime 和 Replay Runtime 生成的特征一致
- 检测特征可用性守卫是否正确工作
- 验证 Label 隔离是否有效

**运行测试**:
```bash
pytest tests/verification/test_live_replay_consistency.py -v
```

---

## 四、FeatureAvailabilityGuard 规则

**文件**: `shared/replay/feature_availability_guard.py`

### 4.1 多周期特征规则

```python
MULTI_PERIOD_FEATURES = {
    "volatility_5m": {"period_ms": 5 * 60 * 1000, "delay_periods": 1},
    "volatility_15m": {"period_ms": 15 * 60 * 1000, "delay_periods": 1},
    "volatility_1h": {"period_ms": 60 * 60 * 1000, "delay_periods": 1},
    "volatility_4h": {"period_ms": 4 * 60 * 60 * 1000, "delay_periods": 1},
    "trend_5m": {"period_ms": 5 * 60 * 1000, "delay_periods": 1},
    "trend_15m": {"period_ms": 15 * 60 * 1000, "delay_periods": 1},
    "trend_1h": {"period_ms": 60 * 60 * 1000, "delay_periods": 1},
}
```

### 4.2 衍生品特征规则

```python
DERIVATIVES_FEATURES = {
    "funding_zscore": {"delay_periods": 1, "lookback": 240},
    "oi_zscore": {"delay_periods": 1, "lookback": 240},
    "leverage_crowdedness": {"delay_periods": 1, "lookback": 240},
}
```

### 4.3 即时特征（无延迟）

```python
SAFE_INSTANT_FEATURES = {
    "spread", "imbalance_5", "trade_delta", "aggressive_buy_ratio",
    "sweep_score", "oi_delta", "funding_rate", "liquidation_cluster",
}
```

---

## 五、验证方法

### 5.1 运行一致性测试

```bash
# 运行所有验证测试
pytest tests/verification/ -v

# 只运行 Live vs Replay 测试
pytest tests/verification/test_live_replay_consistency.py -v
```

### 5.2 审计特征提取器

```python
from domain.feature import audit_all_extractors

result = audit_all_extractors()
print(result)
```

### 5.3 检查泄漏报告

```python
from infrastructure.storage import get_point_in_time_store

store = get_point_in_time_store("BTCUSDT")

# 获取泄漏尝试报告
report = store.get_leakage_report()
print(f"Total leakage attempts: {report['total_attempts']}")
print(f"Features with most attempts: {report['feature_counts']}")

# 验证时间范围内没有泄漏
validation = store.validate_no_leakage(start_time, end_time)
print(f"Has issues: {validation['has_issues']}")
```

---

## 六、最佳实践

### 6.1 特征计算

✅ **正确做法**:
```python
# 使用 rolling 窗口
rolling_mean = series.rolling(window=288, min_periods=20).mean()
rolling_std = series.rolling(window=288, min_periods=20).std()

# 使用 expanding 窗口（只使用历史数据）
expanding_mean = series.expanding(min_periods=20).mean()

# 使用 EMA（指数加权，只依赖历史）
ema = series.ewm(span=20).mean()
```

❌ **错误做法**:
```python
# 全局统计
mean = series.mean()
std = series.std()
q = series.quantile(0.9)
```

### 6.2 Label 处理

✅ **正确做法**:
```python
# Label 独立存储
store.store_feature("future_return_1h", value, timestamp)

# 训练时单独获取
label = store.get_label_at_time(timestamp, "future_return_1h")
```

❌ **错误做法**:
```python
# Label 混入 DataFrame
df['future_return_1h'] = df['close'].shift(-12)
features = df[feature_columns]  # 可能包含 future_return
```

### 6.3 多周期特征

✅ **正确做法**:
```python
# 检查特征可用性
guard = get_feature_availability_guard()
check = guard.check_availability("volatility_1h", feature_timestamp, replay_clock)

if check.status == FeatureAvailabilityStatus.AVAILABLE:
    # 使用特征
    pass
```

❌ **错误做法**:
```python
# 直接使用，不检查可用性
vol_1h = df["volatility_1h"].iloc[i]
```

---

## 七、后续任务

### 7.1 必须完成

- [ ] 将所有特征提取器改为继承 `GuardedFeatureExtractor`
- [ ] 在 Replay Runtime 中集成 `PointInTimeFeatureStore`
- [ ] 定期运行 `test_live_replay_consistency.py`

### 7.2 建议完成

- [ ] 添加 CI/CD 自动运行泄漏检测
- [ ] 创建泄漏监控仪表板
- [ ] 编写训练数据生成最佳实践文档

---

## 八、相关文档

- [ISSUE_DATA_LEAKAGE_FIX.md](./ISSUE_DATA_LEAKAGE_FIX.md) - 原始泄漏问题记录
- [DATA_LEAKAGE_PROTECTION_20260521.md](./DATA_LEAKAGE_PROTECTION_20260521.md) - 防护方案设计
- [ARCHITECTURE_REFACTORING_20260521.md](./ARCHITECTURE_REFACTORING_20260521.md) - 架构重构

---

## 九、变更日志

| 日期 | 变更内容 |
|------|----------|
| 2026-05-22 | 创建 Point-In-Time Feature Store |
| 2026-05-22 | 创建 Feature Generation Guard |
| 2026-05-22 | 创建 Live vs Replay 一致性测试 |
| 2026-05-22 | 修复 strategy_research_matrix.py 全局 quantile |
| 2026-05-22 | 修复 crypto_behavioral_playbooks.py 全局 quantile |
| 2026-05-22 | 修复 advanced.py 全局 mean/std |
| 2026-05-22 | 修复 advanced.py sentiment_momentum_combo |
| 2026-05-22 | 修复 data_preparation.py 全局标准化（新增 rolling_zscore） |

---

## 十、当前数据泄漏防护状态总表

| 模块/机制 | 当前状态 | 泄漏风险 | 是否已解决 | 备注 |
|-----------|----------|----------|------------|------|
| 全局 mean/std | rolling 替代 | 高 | ✅ | 已避免 future statistics |
| 全局 quantile | rolling quantile | 高 | ✅ | research/context 已修 |
| 全局 zscore | rolling/online | 高 | ✅ | 但 warmup 仍需注意 |
| Feature Matrix | PIT 化 | 极高 | ✅ 部分 | 已有 point_in_time_store |
| future_returns | label隔离 | 极高 | ✅ | 未混入 feature |
| Label contamination | label隔离 | 极高 | ✅ 部分 | 需持续 audit |
| Replay Runtime | 时间推进 | 极高 | ⚠️ 部分 | replay/live 还未完全统一 |
| Live vs Replay Test | consistency test | 极高 | ✅ | 非常关键 |
| Feature Guard | runtime guard | 高 | ✅ | 很正确 |
| FeatureAvailabilityGuard | availability检查 | 高 | ✅ | replay保护 |
| 多周期聚合 | partial candle | 极高 | ⚠️ 高风险 | 最容易漏 |
| Feature Cache | overwrite风险 | 高 | ⚠️ 未完全解决 | 建议 immutable snapshot |
| Feature Parquet | 时间污染 | 高 | ⚠️ 部分 | generation_time不足 |
| Correlation Feature | cross-symbol leakage | 高 | ⚠️ 需检查 | 特别危险 |
| Funding/OI Feature | availability timing | 高 | ⚠️ 未完全解决 | event-time语义 |
| Online Normalization | warmup偏移 | 中 | ⚠️ 部分 | replay/live初始化可能不同 |
| Orderbook Feature | future depth snapshot | 极高 | ⚠️ 未完全验证 | 高频特征风险大 |
| Replay Determinism | feature一致性 | 极高 | ✅ 初版 | 建议扩大覆盖 |
| Strategy Research Matrix | quantile泄漏 | 高 | ✅ | 已修 |
| Context Engine | quantile泄漏 | 高 | ✅ | 已修 |
| Advanced Feature | global stats | 高 | ✅ | 已修 |
| Behavioral Playbooks | quantile泄漏 | 高 | ✅ | 已修 |
| Outcome Engine | 后验统计 | 低 | ✅ | 不属于 feature |
| VWAP Window Mean | 当前窗口 | 低 | ✅ | 安全 |
| LSTM Dataset | label shift风险 | 极高 | ⚠️ 需持续检查 | sequence最容易污染 |
| Train/Test Split | 时间穿越 | 极高 | ⚠️ 未完全确认 | walk-forward 很重要 |
| Feature Store Versioning | snapshot version | 高 | ❌ 缺失 | 建议加 feature_version |
| Event Availability Time | receive_time | 极高 | ❌ 缺失 | 下一阶段核心 |
| Runtime Event Semantics | exchange/receive | 高 | ❌ 缺失 | replay/live关键 |
| Immutable Feature Snapshot | 不可变特征 | 高 | ❌ 缺失 | 避免重生成污染 |
| Point-In-Time Query | timestamp query | 极高 | ✅ | 很关键 |
| Rolling Window Feature | online rolling | 高 | ✅ | 已明显改善 |
| Replay → Runtime Event化 | event sourcing | 极高 | ⚠️ 未完全统一 | 当前最大裂缝 |

---

## 十一、当前整体成熟度评估

| 领域 | 成熟度 |
|------|--------|
| 普通量化脚本 | 已超越 |
| Feature Pipeline | ⭐⭐⭐⭐ |
| Runtime 架构 | ⭐⭐⭐⭐ |
| Replay 一致性 | ⭐⭐⭐ |
| PIT Feature Store | ⭐⭐⭐⭐ |
| 防泄漏体系 | ⭐⭐⭐⭐ |
| Event-Time Semantics | ⭐⭐ |
| Quant Infrastructure | ⭐⭐⭐⭐ |
| HFT级 Determinism | ⭐⭐ |
| Institutional-grade PIT | ⭐⭐⭐ |

---

## 十二、剩余最危险的 5 个点（优先级）

| 优先级 | 风险 | 原因 |
|--------|------|------|
| ⭐⭐⭐⭐⭐ | Partial Candle Leakage | 最隐蔽 |
| ⭐⭐⭐⭐⭐ | Replay ≠ Live | 最大架构裂缝 |
| ⭐⭐⭐⭐⭐ | Event Availability Time | 时间语义未闭环 |
| ⭐⭐⭐⭐ | Feature Snapshot Overwrite | 历史特征污染 |
| ⭐⭐⭐⭐ | Cross-Symbol Leakage | correlation 很危险 |

---

## 十三、当前阶段定位

**已经超越**: "做策略" 阶段

**当前阶段**: Point-In-Time Quant Runtime Infrastructure

这是完全不同的层级。

---

## 十四、下一阶段核心任务

### 14.1 Event Availability Time（优先级最高）

**问题**: 当前只有 `feature_timestamp`，没有 `event_receive_time`

**需要实现**:
```python
@dataclass
class EventTimeRecord:
    exchange_time: int      # 交易所时间
    receive_time: int       # 本地接收时间
    available_at: int       # 可用时间（考虑延迟）
```

### 14.2 Immutable Feature Snapshot

**问题**: Feature Cache 可能被 overwrite

**需要实现**:
```python
class ImmutableFeatureSnapshot:
    snapshot_id: str
    snapshot_time: int
    features: Dict[str, Any]
    version: int
    hash: str  # 防篡改
```

### 14.3 Cross-Symbol Leakage 检查

**问题**: correlation 特征可能泄漏跨品种未来信息

**需要检查**:
- `lead_lag` 特征是否使用未来数据
- `basis` 特征的时间对齐
- `risk_on_off` 特征的计算窗口

---

## 十五、新增模块（2026-05-22 更新）

### 15.1 Cross-Symbol Event Semantics

**文件**: `infrastructure/event/cross_symbol_semantics.py`

**功能**:
- 跟踪每个品种的事件可用性
- 跨品种特征必须等待所有品种数据就绪
- 检测跨品种数据泄漏

```python
from infrastructure.event import get_cross_symbol_semantics

semantics = get_cross_symbol_semantics(["BTCUSDT", "ETHUSDT"])

# 注册跨品种特征
semantics.register_cross_symbol_feature("btc_eth_correlation", ["BTCUSDT", "ETHUSDT"])

# 检查可用性
is_available, availability = semantics.check_feature_availability("btc_eth_correlation", query_time)
```

### 15.2 Event Ordering Determinism

**文件**: `infrastructure/event/event_ordering.py`

**功能**:
- 为事件分配确定性的排序键
- 确保相同事件集合总是产生相同顺序
- 支持多种排序策略

```python
from infrastructure.event import get_event_ordering, create_deterministic_event

ordering = get_event_ordering()

# 创建有序事件
event = create_deterministic_event(
    event_type="trade",
    timestamp=1704070800000,
    data={"price": 42000, "quantity": 1.5},
    symbol="BTCUSDT",
)

# 排序事件
sorted_events = ordering.sort_events(events)
```

### 15.3 Warmup Determinism

**文件**: `infrastructure/feature/warmup_determinism.py`

**功能**:
- 管理 rolling 特征的预热状态
- 支持状态保存和恢复
- 确保 Replay 和 Live 初始状态一致

```python
from infrastructure.feature import get_warmup_manager

manager = get_warmup_manager()

# 注册特征
manager.register_feature("volatility_1h", window_size=60, min_periods=20)

# 保存状态（Replay 结束时）
manager.save_state("replay_end")

# 恢复状态（Live 启动时）
manager.restore_state("replay_end")
```

### 15.4 Feature Lineage System

**文件**: `infrastructure/feature/feature_lineage.py`

**功能**:
- 记录特征依赖关系
- 支持血缘追溯
- 影响分析

```python
from infrastructure.feature import get_feature_lineage, register_feature_lineage

lineage = get_feature_lineage()

# 注册特征血缘
register_feature_lineage(
    feature_name="volatility_zscore",
    feature_type="derived",
    dependencies=["volatility_1h", "volatility_mean", "volatility_std"],
)

# 分析影响
impact = lineage.analyze_impact(["volatility_1h"])
print(f"Affected features: {impact['affected_features']}")
```

---

## 十六、新增文件清单

| 文件 | 功能 |
|------|------|
| `infrastructure/feature/partial_candle_handler.py` | Partial Candle 检测 |
| `infrastructure/event/event_time.py` | Event Time 语义 |
| `infrastructure/event/unified_event_processor.py` | 统一事件处理 |
| `infrastructure/storage/immutable_snapshot.py` | 不可变快照 |
| `infrastructure/event/cross_symbol_semantics.py` | 跨品种事件语义 |
| `infrastructure/event/event_ordering.py` | 事件排序确定性 |
| `infrastructure/feature/warmup_determinism.py` | 预热确定性控制 |
| `infrastructure/feature/feature_lineage.py` | 特征血缘系统 |

---

**Labels**: `data-leakage`, `critical`, `feature-store`, `replay`, `backtesting`
