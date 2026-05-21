# 测试套件指南

## 测试文件列表

已创建以下测试文件：

### 1. domain/signal/ 测试
- **文件**: [tests/test_signal_domain.py](file:///e:/00_crypto/00_code/backend/tests/test_signal_domain.py)
- **覆盖**: 信号模型、融合、生命周期、注册表
- **测试类**:
  - `TestSignalModels` - 信号模型测试
  - `TestSignalFusion` - 信号融合测试
  - `TestSignalLifecycle` - 生命周期测试
  - `TestSignalRegistry` - 注册表测试

### 2. runtime/portfolio_runtime/ 测试
- **文件**: [tests/test_portfolio_runtime.py](file:///e:/00_crypto/00_code/backend/tests/test_portfolio_runtime.py)
- **覆盖**: 组合管理、资金分配、信号集成
- **测试类**:
  - `TestPortfolioRuntime` - 组合运行时测试
  - `TestSignalRegistryIntegration` - 信号注册表集成测试
  - `TestCapitalAllocation` - 资金分配测试

### 3. runtime/regime_runtime/ 测试
- **文件**: [tests/test_regime_runtime.py](file:///e:/00_crypto/00_code/backend/tests/test_regime_runtime.py)
- **覆盖**: 市场状态分类、策略选择、状态转换
- **测试类**:
  - `TestMarketRegime` - 市场状态枚举测试
  - `TestRegimeClassification` - 状态分类测试
  - `TestRegimeState` - 状态数据测试
  - `TestStrategySelection` - 策略选择测试
  - `TestRegimeRuntimeLogic` - 运行时逻辑测试
  - `TestRegimeTransition` - 状态转换测试

### 4. domain/execution/intelligence/ 测试
- **文件**: [tests/test_execution_intelligence.py](file:///e:/00_crypto/00_code/backend/tests/test_execution_intelligence.py)
- **覆盖**: 滑点预测、市场冲击、流动性估计、执行优化
- **测试类**:
  - `TestSlippagePredictor` - 滑点预测器测试
  - `TestImpactModel` - 市场冲击模型测试
  - `TestLiquidityEstimator` - 流动性估计器测试
  - `TestExecutionOptimizer` - 执行优化器测试
  - `TestIntegration` - 集成测试

### 5. 验证脚本
- **文件**: [tests/verify_modules.py](file:///e:/00_crypto/00_code/backend/tests/verify_modules.py)
- **用途**: 手动验证模块导入和基本功能

## 运行测试

### 方法 1: 使用 pytest（推荐）

```bash
cd e:\00_crypto\00_code\backend

# 运行所有新模块测试
python -m pytest tests/test_signal_domain.py -v
python -m pytest tests/test_portfolio_runtime.py -v
python -m pytest tests/test_regime_runtime.py -v
python -m pytest tests/test_execution_intelligence.py -v

# 运行所有测试
python -m pytest tests/test_*.py -v
```

### 方法 2: 使用验证脚本

```bash
cd e:\00_crypto\00_code\backend
python tests/verify_modules.py
```

## 测试覆盖

### Signal Domain (domain/signal/)
- ✅ Signal 模型创建和状态管理
- ✅ 信号激活/停用/过期
- ✅ 投票融合 (VotingFusion)
- ✅ 混合融合 (BlendingFusion)
- ✅ 共识融合 (ConsensusFusion)
- ✅ 信号衰减 (SignalDecay)
- ✅ 信号冷却 (SignalCooldown)
- ✅ 信号生成 (SignalGenerator)
- ✅ 注册表增删改查
- ✅ 信号查询

### Portfolio Runtime (runtime/portfolio_runtime/)
- ✅ 组合创建和权益更新
- ✅ 仓位更新和关闭
- ✅ 敞口计算（总敞口/净敞口）
- ✅ 多仓位管理
- ✅ 信号注册和查询
- ✅ 信号生命周期管理
- ✅ 策略信号过滤
- ✅ 资金分配逻辑

### Regime Runtime (runtime/regime_runtime/)
- ✅ 市场状态枚举
- ✅ 高波动检测
- ✅ 爆仓潮检测
- ✅ 叙事爆发检测
- ✅ 趋势检测
- ✅ 横盘检测
- ✅ 流动性枯竭检测
- ✅ 策略注册表映射
- ✅ 策略启用判断
- ✅ 价格历史管理
- ✅ 波动率计算
- ✅ 趋势强度计算
- ✅ 状态转换检测
- ✅ 状态历史记录

### Execution Intelligence (domain/execution/intelligence/)
- ✅ 基本滑点预测
- ✅ Maker vs Taker 滑点差异
- ✅ 大单滑点预测
- ✅ 预测因素分析
- ✅ 基本冲击计算
- ✅ 临时 vs 永久冲击
- ✅ 大单冲击计算
- ✅ 最优规模估算
- ✅ 优秀流动性估计
- ✅ 差流动性估计
- ✅ 流动性评级
- ✅ 执行建议生成
- ✅ 基本执行优化
- ✅ 激进策略选择
- ✅ 被动策略选择
- ✅ 计划属性验证
- ✅ 完整优化流程集成

## 预期测试结果

所有测试应该通过：
- Signal Domain: 12 个测试 ✅
- Portfolio Runtime: 9 个测试 ✅
- Regime Runtime: 15 个测试 ✅
- Execution Intelligence: 14 个测试 ✅

**总计**: 50+ 个测试用例

## 故障排查

### 问题: ImportError
**解决方案**: 确保所有依赖模块已正确导入
```python
from domain.signal.models import Signal
from domain.execution.intelligence import ExecutionOptimizer
```

### 问题: pytest 未找到
**解决方案**: 安装 pytest
```bash
pip install pytest
```

### 问题: 模块导入失败
**解决方案**: 检查 PYTHONPATH 设置
```bash
set PYTHONPATH=e:\00_crypto\00_code\backend
```

## 下一步

测试通过后，可以：
1. 集成到 CI/CD 流程
2. 添加更多边界测试
3. 添加性能测试
4. 添加压力测试
