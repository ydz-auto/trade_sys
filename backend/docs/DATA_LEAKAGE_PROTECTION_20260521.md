# 数据泄漏防护系统实现文档

**日期**: 2026-05-21  
**作者**: Trading Intelligence OS Team

## 概述

本文档描述了系统中实现的数据泄漏防护机制，包括特征时间纪律、可用性防护和最佳实践。

## 修复的问题

### 1. 全局标准化问题（高风险）

**问题描述**:
- 原代码使用全局均值和标准差计算 Z-score
- 这导致未来数据泄漏到历史特征计算中
- 影响特征: `oi_zscore`, `funding_zscore`

**修复方案**:
- 使用滚动窗口（240周期）替代全局统计
- 只使用当前时间点之前的历史数据
- 文件: `domain/feature/oi/oi_funding_correlation.py`

**代码变更**:
```python
# 修复前（有泄漏）
oi_zscore = (oi - np.mean(oi_array)) / np.std(oi_array)

# 修复后（无泄漏）
window_size = min(240, len(oi_history))
oi_window = np.array(oi_history[-window_size:])
oi_mean = np.mean(oi_window)
oi_std = np.std(oi_window)
oi_zscore = (oi - oi_mean) / oi_std if oi_std > 0 else 0.0
```

## 新增功能

### 2. 特征Schema时间纪律扩展

**文件**: `domain/feature/materializer/schema_registry.py`

**新增字段**:
- `available_after_periods`: 特征需要等待多少周期后才能使用
- `requires_lookback`: 是否需要历史窗口
- `lookback_window`: 回溯窗口大小
- `is_future_derived`: 是否由未来数据派生

**高风险特征配置**:
| 特征 | 可用周期 | 回溯窗口 | 说明 |
|------|---------|---------|
| oi_zscore | 1 | 240 | 持仓量Z-score |
| funding_zscore | 1 | 240 | 资金费率Z-score |
| leverage_crowdedness | 1 | 240 | 杠杆拥挤度 |
| squeeze_probability | 1 | 24 | 挤压概率 |
| chain_probability | 1 | 30 | 连锁概率 |
| volatility_regime | 1 | 60 | 波动体制 |
| trend_regime | 1 | 20 | 趋势体制 |

### 3. 特征可用性防护机制

**文件**: `domain/feature/time_discipline.py`

**核心组件**:
- `FeatureAvailabilityGuard`: 主要防护类
- `LeakageCheckResult`: 泄漏检测结果
- `FeatureTimeRecord`: 特征时间记录
- `LeakageSeverity`: 严重程度枚举（NONE/LOW/MEDIUM/HIGH/CRITICAL）

**使用方法**:
```python
from domain.feature.time_discipline import get_feature_availability_guard

guard = get_feature_availability_guard()
guard.strict_mode = True  # 发现高/严重泄漏时抛出异常

result = guard.check_feature_availability(
    feature_name="oi_zscore",
    feature_timestamp=feature_ts,
    replay_clock=current_ts
)

if result.has_leakage:
    print(f"检测到泄漏: {result.message}")
```

### 4. 统一特征矩阵时间字段

**文件**: `domain/feature/materializer/matrix_builder.py`

**新增字段**:
- `feature_timestamps`: 每个特征的计算时间戳
- `available_ats`: 每个特征的可用时间戳

**新增方法**:
- `get_available_features_at(replay_clock)`: 获取指定时间可用的特征

**使用方法**:
```python
# 只获取在当前时间可用的特征
available_features = matrix.get_available_features_at(replay_time)
```

## 测试验证

**测试文件**: `scripts/test_data_leakage_protection.py`

**测试覆盖**:
1. 特征Schema时间纪律配置验证
2. 特征可用性防护功能测试
3. 带时间字段的特征矩阵测试
4. 滚动窗口vs全局统计对比验证

**运行测试**:
```bash
python scripts/test_data_leakage_protection.py
```

## 最佳实践

### 回测时的使用

```python
from domain.feature.time_discipline import get_feature_availability_guard

guard = get_feature_availability_guard()
guard.strict_mode = True  # 启用严格模式

for timestamp in timestamps:
    # 只使用在当前时间可用的特征
    features = matrix.get_available_features_at(timestamp)
    
    # 验证每个特征的可用性
    for feature_name in features:
        result = guard.check_feature_availability(
            feature_name=feature_name,
            feature_timestamp=timestamp,
            replay_clock=timestamp
        )
        if result.has_leakage and result.severity >= LeakageSeverity.HIGH:
            raise RuntimeError(f"数据泄漏检测: {result.message}")
    
    # 使用安全的特征进行策略决策
    signal = strategy.compute(features)
```

### 特征计算时的使用

```python
# 在特征物化时记录可用时间
for i, timestamp in enumerate(timestamps):
    schema = schema_registry.get_schema(feature_name)
    available_at = timestamp + (schema.available_after_periods * interval_ms)
    
    # 存储可用时间
    matrix.available_ats[feature_name][i] = available_at
```

## 泄漏防护检查清单

- [ ] 所有Z-score特征使用滚动窗口计算
- [ ] 多周期聚合特征正确设置`available_after_periods`
- [ ] 回测引擎使用`get_available_features_at()`获取特征
- [ ] 策略在实时模式中启用`FeatureAvailabilityGuard`
- [ ] 定期运行`test_data_leakage_protection.py`验证
- [ ] 检查泄漏摘要报告: `guard.get_leakage_summary()`

## 文件变更清单

1. **新增文件**:
   - `domain/feature/time_discipline.py` - 时间纪律和防护机制
   - `scripts/test_data_leakage_protection.py` - 测试脚本

2. **修改文件**:
   - `domain/feature/oi/oi_funding_correlation.py` - 修复全局标准化
   - `domain/feature/materializer/schema_registry.py` - 扩展时间纪律字段
   - `domain/feature/materializer/matrix_builder.py` - 增强矩阵时间字段

## 总结

本次实现为系统添加了完整的数据泄漏防护能力：

✅ 修复了高风险的全局标准化问题  
✅ 为所有45个特征配置了时间纪律  
✅ 创建了特征可用性防护机制  
✅ 增强了特征矩阵的时间字段管理  
✅ 提供了完整的测试验证脚本  

现在系统已具备专业级的数据泄漏防护能力！
