# Engines 目录架构分析与重构建议

## 概述

基于对 `engines/` 目录的详细分析，本报告提供当前架构状态评估、存在的问题，以及详细的重构建议。

---

## 一、当前架构评估

### 1.1 整体结构评价

✅ **优点**:
- 清晰的分层架构（domain → engines → runtime → infrastructure）
- 职责划分明确，符合 Clean Architecture 原则
- engines 目录已有明确的 README 定义边界

⚠️ **存在问题**:
- `compute/strategy/` 模块存在大量状态管理逻辑，违反无状态原则
- 与 `domain/` 存在一定程度的重复定义
- 缺乏明确的模块间依赖规范

### 1.2 各模块详细分析

#### adapters/
| 模块 | 内容 | 评价 |
|------|------|------|
| data/ | 数据源适配器 | ✅ 合理，职责单一 |
| exchange/ | 交易所交互适配器 | ✅ 合理，外部 IO 隔离正确 |
| contracts/ | 合约适配器 | ✅ 合理 |

#### compute/
| 模块 | 问题严重度 | 主要问题 |
|------|-----------|---------|
| feature/ | 🟡 中 | 整体良好，但需确认是否有窗口状态管理 |
| strategy/ | 🔴 高 | 大量状态变量，违反无状态原则 |
| signal/ | 🟡 中 | 需检查 buffer 是否管理状态 |
| risk/ | 🟢 低 | 整体合理 |
| scoring/ | 🟢 低 | 合理 |
| aggregation/ | 🟢 低 | 合理 |
| correlation/ | 🟢 低 | 合理 |
| models/ | 🟢 低 | 合理 |
| schemas/ | 🟢 低 | 合理 |

#### ml/
| 模块 | 内容 | 评价 |
|------|------|------|
| lstm 相关 | 机器学习模型 | ✅ 合理，独立于业务逻辑 |

#### optimization/
| 模块 | 内容 | 评价 |
|------|------|------|
| 优化模块 | 参数优化 | ✅ 合理，独立成层正确 |

---

## 二、发现的主要问题

### 2.1 问题一：engines/compute/strategy/ 中存在大量状态逻辑

**位置**: `engines/compute/strategy/strategies.py`

**具体问题**:
1. `BaseStrategy` 类管理 `self._enabled` 状态
2. `RSIStrategy` 管理 `self._rsi_prev`
3. `MACDStrategy` 管理 `self._macd_prev` 和 `self._signal_prev`
4. `TrendFollowingStrategy` 管理 `self._ema_fast_prev` 和 `self._ema_slow_prev`
5. `BBCompressionBreakoutStrategy` 管理 `self._prev_above_middle`
6. `MultiStrategyOrchestrator` 包含大量状态：
   - `self._strategies`
   - `self._symbol_strategies`
   - `self._symbol_data`
   - `self._symbol_configs`
   - `self._regime_runtime`
   - `self._confluence_engine`
7. `DynamicStrategySelector` 管理 `self._all_strategies` 等

**影响**:
- 违反了 `engines/README.md` 中定义的无状态原则
- 状态分散管理，难以追踪和测试
- 难以实现确定性回放和审计

### 2.2 问题二：与 domain/ 存在边界模糊

**位置**: 
- `engines/compute/strategy/` vs `domain/strategy/`

**具体问题**:
- `domain/strategy/` 主要定义数据模型和配置
- `engines/compute/strategy/` 有策略实现，但也包含一些配置管理
- 职责划分需要进一步明确

### 2.3 问题三：跨层依赖

**发现**:
- `engines/compute/strategy/strategies.py` 中的 `create_default_strategies` 函数尝试导入 `runtimes/regime_runtime`
- 这违反了分层原则，engines 层不应依赖 runtime 层

---

## 三、重构建议

### 3.1 第一优先级：迁移 compute/strategy 中的状态逻辑

#### 重构方案

**步骤 1**: 识别需要迁移的状态

| 策略类 | 当前状态变量 | 迁移位置 |
|--------|------------|---------|
| BaseStrategy | `self._enabled` | runtime/strategy_runtime |
| RSIStrategy | `self._rsi_prev` | runtime/strategy_runtime |
| MACDStrategy | `self._macd_prev`, `self._signal_prev` | runtime/strategy_runtime |
| TrendFollowingStrategy | `self._ema_fast_prev`, `self._ema_slow_prev` | runtime/strategy_runtime |
| BBCompressionBreakoutStrategy | `self._prev_above_middle` | runtime/strategy_runtime |
| MultiStrategyOrchestrator | 全部状态变量 | runtime/strategy_orchestrator |
| DynamicStrategySelector | 全部状态变量 | runtime/strategy_selector |

**步骤 2**: 重构策略类为纯计算类

重构示例:

```python
# 重构前 - 有状态
class RSIStrategy(BaseStrategy):
    def __init__(self):
        self._rsi_prev = None  # 状态在 compute 层
    
    def generate_signal(self, features):
        if self._rsi_prev is None:
            self._rsi_prev = features['rsi_14']
            return None
        # 使用 self._rsi_prev
        signal = ...
        self._rsi_prev = features['rsi_14']
        return signal

# 重构后 - 无状态
class RSIStrategy:
    @staticmethod
    def generate_signal(features, prev_rsi=None):  # 状态作为参数
        if prev_rsi is None:
            return None, features['rsi_14']  # 返回信号和新状态
        # 纯计算逻辑
        signal = ...
        return signal, features['rsi_14']
```

**步骤 3**: 在 runtime 层创建状态管理器

创建新文件 `runtime/strategy_state.py` (或类似位置):

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class StrategyState:
    """单个策略的状态"""
    strategy_id: str
    enabled: bool = True
    # 策略特定的状态
    prev_rsi: Optional[float] = None
    prev_macd: Optional[float] = None
    prev_signal: Optional[float] = None
    prev_ema_fast: Optional[float] = None
    prev_ema_slow: Optional[float] = None
    prev_above_middle: Optional[bool] = None

class StrategyStateManager:
    """策略状态管理器"""
    def __init__(self):
        self._states: Dict[str, StrategyState] = {}
    
    def get_or_create(self, strategy_id: str) -> StrategyState:
        if strategy_id not in self._states:
            self._states[strategy_id] = StrategyState(strategy_id=strategy_id)
        return self._states[strategy_id]
```

### 3.2 第二优先级：明确 domain 与 engines 的边界

| 内容 | 应放置位置 |
|------|-----------|
| 策略参数定义 (如 `RSIStrategyParams`) | domain/strategy/models/ |
| 策略实现逻辑 | engines/compute/strategy/ |
| 策略注册表 | engines/compute/strategy/ |
| 策略配置管理 | domain/strategy/ 或 application/ |
| 策略执行状态 | runtime/ |

**建议重构**:
- 将 `domain/strategy/symbol_config.py` 保持不变，继续负责配置管理
- `engines/compute/strategy/` 只保留纯策略计算逻辑和注册表
- 将 `MultiStrategyOrchestrator` 的职责拆分：
  - 配置部分 → `application/strategy_service.py`
  - 状态管理 → `runtime/strategy_orchestrator.py`
  - 纯编排逻辑 → `engines/compute/strategy/orchestrator.py` (无状态)

### 3.3 第三优先级：清理跨层依赖

**当前问题**: `create_default_strategies` 函数导入 `runtimes/regime_runtime`

**重构方案**:
1. 将 `create_default_strategies` 移动到 `application/strategy_service.py`
2. 或者通过依赖注入的方式传入 regime runtime，而不是直接导入

---

## 四、详细的重构执行计划

### Phase 1: 准备 (1-2天)
- [ ] 创建 `runtime/strategy_state.py` 状态管理模块
- [ ] 创建 `runtime/strategy_runtime.py` 骨架
- [ ] 编写单元测试框架

### Phase 2: 逐个重构策略类 (3-5天)
- [ ] 重构 RSIStrategy
- [ ] 重构 MACDStrategy
- [ ] 重构 TrendFollowingStrategy
- [ ] 重构 BBCompressionBreakoutStrategy
- [ ] 重构其他策略类
- [ ] 每步都运行测试确保功能不变

### Phase 3: 重构 MultiStrategyOrchestrator (2-3天)
- [ ] 将状态迁移到 runtime
- [ ] 提取纯计算逻辑到 engines
- [ ] 更新调用方代码

### Phase 4: 边界清理 (1-2天)
- [ ] 清理 domain 与 engines 的重复定义
- [ ] 移除跨层依赖
- [ ] 更新文档

### Phase 5: 验证与测试 (2-3天)
- [ ] 运行所有现有测试
- [ ] 回测验证
- [ ] 性能测试

---

## 五、架构最佳实践（长期）

### 5.1 分层依赖规则
```
infrastructure/
    ↓
application/
    ↓
runtime/ ← 有状态执行
    ↓
engines/ ← 无状态计算 ⬅ 我们在这里
    ↓
domain/ ← 领域模型
```

**依赖方向**: 上层可以依赖下层，下层不能依赖上层

### 5.2 模块开发检查清单
创建新模块时，请确认:
- [ ] 是否管理任何可变状态？如是，应在 runtime 层
- [ ] 是否有 I/O 操作？如是，应在 adapters 或 infrastructure 层
- [ ] 是否是纯函数/无状态计算？如是，适合在 engines 层
- [ ] 是否定义领域概念？如是，适合在 domain 层
- [ ] 是否有跨层依赖？如有，需要重新考虑设计

### 5.3 代码审查要点
审查 engines 层代码时检查:
- [ ] 没有 `self._*` 状态变量（除了只读配置）
- [ ] 所有函数都是确定性的
- [ ] 不直接访问数据库、消息队列等外部资源
- [ ] 不依赖 runtime 层

---

## 六、总结

当前架构整体设计合理，但需要在以下方面进行优化:

1. **紧急**: 迁移 `engines/compute/strategy/` 中的状态逻辑到 runtime 层
2. **重要**: 进一步明确 domain 与 engines 的边界
3. **优化**: 清理跨层依赖，确保分层清晰

通过这些重构，系统将获得:
- ✅ 更好的可测试性（无状态逻辑易于单元测试）
- ✅ 更好的可回放性（状态集中管理）
- ✅ 更清晰的架构边界
- ✅ 更容易并行开发
