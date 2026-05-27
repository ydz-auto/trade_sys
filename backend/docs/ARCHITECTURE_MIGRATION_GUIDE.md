# Engines 架构迁移指南

## 概述

本文档描述了如何将有状态的策略计算从 `engines/compute/strategy/strategies.py` 迁移到无状态的架构中，符合 Clean Architecture 原则。

## 已完成的工作

### 1. 状态管理层 (`runtime/strategy_runtime/strategy_state.py`)

创建了策略状态管理模块，负责：
- `StrategyInstanceState`: 单个策略实例的状态数据类
- `StrategyStateManager`: 状态管理器，提供统一的状态访问和更新接口

### 2. 策略运行时 (`runtime/strategy_runtime/runtime.py`)

更新了策略运行时，支持：
- 新的无状态计算器调用
- 旧策略类的兼容模式（向后兼容）
- 统一的状态管理

### 3. 无状态计算器 (`engines/compute/strategy/calculators/`)

创建了以下无状态策略计算器：
- `rsi_calculator.py`: RSI 策略
- `macd_calculator.py`: MACD 策略
- `trend_calculator.py`: 趋势跟踪策略
- `bollinger_calculator.py`: 布林带压缩突破策略

## 架构原则

### 分层依赖规则

```
┌─────────────────────────────────────┐
│         API / Application           │  ← 应用层
├─────────────────────────────────────┤
│         Runtime (Stateful)          │  ← 状态管理层 ✨
├─────────────────────────────────────┤
│       Engines (Stateless)           │  ← 无状态计算层 ✨
├─────────────────────────────────────┤
│        Domain (Models)              │  ← 领域模型层
├─────────────────────────────────────┤
│      Infrastructure (IO)           │  ← 基础设施层
└─────────────────────────────────────┘
```

**依赖方向**：上层可以依赖下层，但下层不能依赖上层！

### 无状态计算规范

1. **所有状态由 Runtime 层管理**
   - 不能在 engines 层中维护 `self._prev_*` 或类似的状态变量
   - 状态必须作为输入参数传入
   - 新状态必须作为返回值的一部分返回

2. **纯函数设计**
   - 相同的输入必须产生相同的输出
   - 不能有副作用
   - 不能进行 I/O 操作

3. **参数明确化**
   - 所有计算依赖的输入都必须作为函数参数
   - 不能依赖隐式的上下文或全局状态

## 迁移步骤

### 步骤 1: 创建无状态计算器

对于每个策略，创建对应的无状态计算器：

```python
# engines/compute/strategy/calculators/my_strategy_calculator.py
from typing import Optional, Dict, Any, Tuple

def calculate_my_strategy_signal(
    param1: float,
    param2: float,
    prev_state1: Optional[float] = None,
    prev_state2: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    无状态计算策略信号
    
    Args:
        param1, param2: 当前输入特征
        prev_state1, prev_state2: 前一时刻状态（由 Runtime 提供）
        params: 策略参数
        
    Returns:
        (signal_dict, new_state): 信号字典和新状态数据
    """
    params = params or {}
    
    # 准备新状态
    new_state = {
        'prev_state1': param1,
        'prev_state2': param2
    }
    
    # 如果没有前值，只保存状态
    if prev_state1 is None:
        return None, new_state
    
    # 计算信号
    signal = None
    if some_condition(param1, param2, prev_state1):
        signal = {
            'signal_type': 'buy',
            'confidence': 0.7,
            'reason': '...'
        }
    
    return signal, new_state
```

### 步骤 2: 更新状态数据类

在 `StrategyInstanceState` 中添加策略需要的状态字段：

```python
@dataclass
class StrategyInstanceState:
    # ... 现有字段 ...
    
    # 新策略的状态
    prev_state1: Optional[float] = None
    prev_state2: Optional[float] = None
```

### 步骤 3: 更新策略运行时

在 `StrategyRuntime` 中添加新的计算器调用：

```python
# 在 __init__ 中
self._calculator_map = {
    # ... 现有映射 ...
    'my_strategy': self._calculate_using_my_strategy_calculator,
}

# 添加调用方法
def _calculate_using_my_strategy_calculator(
    self,
    strategy_id: str,
    symbol: str,
    features: Dict[str, Any],
    state: StrategyInstanceState,
    params: Dict[str, Any]
):
    """使用新的无状态计算器"""
    param1 = features.get('feature1')
    param2 = features.get('feature2')
    if param1 is None or param2 is None:
        return None, {}
    
    signal_dict, new_state = calculate_my_strategy_signal(
        param1=param1,
        param2=param2,
        prev_state1=state.prev_state1,
        prev_state2=state.prev_state2,
        params=params
    )
    
    return self._build_signal(signal_dict, strategy_id, symbol, features), new_state
```

### 步骤 4: 更新导出

在 `engines/compute/strategy/calculators/__init__.py` 中导出新计算器：

```python
from .my_strategy_calculator import calculate_my_strategy_signal

__all__ = [
    # ... 现有导出 ...
    'calculate_my_strategy_signal',
]
```

### 步骤 5: 在运行时导入

在 `runtime/strategy_runtime/runtime.py` 中导入新计算器：

```python
from engines.compute.strategy.calculators import (
    # ... 现有导入 ...
    calculate_my_strategy_signal,
)
```

## 待迁移策略清单

以下策略还需要迁移到无状态架构：

- [ ] `PanicReversalStrategy` - 恐慌反转策略
- [ ] `LongLiquidationBounceStrategy` - 多头踩踏反弹策略
- [ ] `VolumeClimaxFadeStrategy` - 放量高潮衰竭策略
- [ ] `WeakBounceShortStrategy` - 弱反弹做空策略
- [ ] `DeadCatEchoStrategy` - 死猫回声策略
- [ ] `OIFlushStrategy` - OI 清洗策略
- [ ] `ShortSqueezeStrategy` - 空头挤压策略
- [ ] `FundingExhaustionTrapStrategy` - 资金费率耗尽陷阱策略
- [ ] `ImbalancePressureStrategy` - 订单簿失衡压力策略
- [ ] `SweepDetectionStrategy` - 大单扫盘检测策略
- [ ] `LiquidityVacuumStrategy` - 流动性真空策略
- [ ] `AggressiveFlowStrategy` - 主动成交流策略
- [ ] `BreakoutStrategy` - 突破策略
- [ ] `VolatilityExpansionStrategy` - 波动率扩张策略
- [ ] `MomentumIgnitionStrategy` - 动量点火策略

## 迁移验证

每个策略迁移完成后，需要验证：

1. [ ] 单元测试通过
2. [ ] 回测结果与原策略一致（差异在可接受范围内）
3. [ ] 实时交易功能正常
4. [ ] 性能没有明显下降

## 兼容性说明

在完全迁移之前，系统会保持双重支持：

- **新代码路径**: 使用无状态计算器（优先）
- **旧代码路径**: 使用原来的策略类（降级方案）

这允许我们逐步迁移策略，而不会破坏现有功能。

## 相关文档

- [架构重构报告](./ARCHITECTURE_REFACTORING_REPORT.md)
- [架构最佳实践](./ARCHITECTURE_BEST_PRACTICES.md)
- [Engines README](../engines/compute/README.md)
