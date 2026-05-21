# Data Leakage Protection - 数据泄漏防护修复

## 问题描述

系统中存在多处严重的数据泄漏问题，可能导致回测结果虚高、模型过拟合。

## 发现的泄漏点

### 1. 全局标准化泄漏 ⭐⭐⭐⭐⭐

**位置**: `services/strategy_service/feature_matrix.py`

**问题**: 使用全局 mean/std 进行标准化，包含了未来所有数据。

```python
# 修复前
return (self.df[feature_name] - self.df[feature_name].mean()) / self.df[feature_name].std()
```

**影响**: 模型在训练时"看到"了未来数据的分布特征。

### 2. Scaler 在完整数据集上 fit ⭐⭐⭐⭐⭐

**位置**: 
- `scripts/train_lstm_strategy.py`
- `scripts/train_ml_strategy.py`
- `data_loader.py`

**问题**: 在完整数据集上 fit scaler，验证集数据参与了训练集的标准化。

```python
# 修复前
scaler.fit_transform(df[features])  # 包含验证集
```

**影响**: 验证集信息泄漏到训练过程，导致验证结果虚高。

### 3. Future Return 混入 DataFrame ⭐⭐⭐⭐⭐

**位置**: `scripts/train_ml_strategy.py`

**问题**: `future_return_1h` 被添加到 DataFrame 中，可能被误用作特征。

```python
# 修复前
df['future_return_1h'] = df['return_5m'].shift(-12).rolling(12).sum()
df['target'] = (df['future_return_1h'] > 0).astype(int)
# df 可能被用于特征提取
```

**影响**: 如果 future_return 被误加入特征列表，会导致严重泄漏。

### 4. Context Engine 全局 Quantile ⭐⭐⭐⭐

**位置**: `services/research_service/context_engine.py`

**问题**: 使用全局 quantile 计算波动率和市场状态阈值。

```python
# 修复前
q_high = vol.quantile(0.8)
```

**影响**: 当前时刻可以"知道"未来数据的分布。

### 5. 多周期聚合特征可用性检查缺失 ⭐⭐⭐⭐

**问题**: 生成的多周期特征没有记录 `available_at` 时间戳。

**影响**: 例如 1h volatility 在 10:15 就可以访问，但应该等到 11:00 周期结束。

## 修复方案

### 修复 1: Rolling 标准化

```python
# 修复后
rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
rolling_std = series.rolling(window=window, min_periods=min_periods).std()
return (series - rolling_mean) / (rolling_std + 1e-8)
```

### 修复 2: Scaler 只在训练集 fit

```python
# 修复后
train_size = int(0.8 * len(X))
scaler.fit(X_train)  # 只在训练集上 fit
X_train_scaled = scaler.transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

### 修复 3: Future Return 严格隔离

```python
# 修复后
target = df['return_5m'].shift(-12).rolling(12).sum()
y = (target > 0).astype(int)  # y 是独立的，不加入 df
```

### 修复 4: Rolling Quantile

```python
# 修复后
q_high = vol.rolling(window=288, min_periods=20).quantile(0.8)
```

### 修复 5: 新增 Feature Availability Guard

新增 `shared/replay/feature_availability_guard.py`，提供：

- `check_availability()`: 检查特征在当前时间是否可用
- `filter_available_features()`: 过滤出可用的特征
- `validate_dataframe()`: 验证 DataFrame 中的时间因果关系

## 修改的文件

| 文件 | 修改类型 |
|------|----------|
| `services/strategy_service/feature_matrix.py` | 修复标准化方法 |
| `scripts/train_lstm_strategy.py` | 修复 scaler 使用 |
| `scripts/train_ml_strategy.py` | 修复 scaler 和 target 隔离 |
| `data_loader.py` | 修复 scaler 使用 |
| `services/research_service/context_engine.py` | 修复 quantile 计算 |
| `shared/replay/feature_availability_guard.py` | 新增特征可用性守卫 |
| `shared/replay/__init__.py` | 导出新模块 |
| `scripts/verify_leakage_fix.py` | 新增验证脚本 |

## 验证方法

运行验证脚本：

```bash
python scripts/verify_leakage_fix.py
```

## 影响评估

- **回测结果**: 之前的高收益可能是数据泄漏导致的虚高
- **模型性能**: 修复后模型性能可能下降，但更真实
- **策略可靠性**: 修复后的策略在实盘中表现会更可靠

## 建议

1. 重新训练所有 ML/LSTM 模型
2. 重新运行所有回测
3. 在 Replay Runtime 中集成 Feature Availability Guard
4. 定期审计特征工程代码的时间因果关系

## 相关 Issue

- #数据泄漏审计
- #回测系统可靠性
- #ML模型训练流程

---

**Labels**: bug, critical, data-leakage, ml-training, backtesting
