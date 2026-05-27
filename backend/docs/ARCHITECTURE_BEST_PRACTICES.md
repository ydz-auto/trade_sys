# 项目架构最佳实践

## 目录
1. [分层架构原则](#分层架构原则)
2. [各层职责详解](#各层职责详解)
3. [代码组织规范](#代码组织规范)
4. [依赖管理规则](#依赖管理规则)
5. [常见错误示例](#常见错误示例)
6. [检查清单](#检查清单)

---

## 分层架构原则

### 架构图
```
┌─────────────────────────────────────────┐
│         api/ (对外接口层)               │
├─────────────────────────────────────────┤
│      application/ (应用层)              │
├─────────────────────────────────────────┤
│      runtime/ (有状态执行层)            │ ← 状态管理在这里
├─────────────────────────────────────────┤
│      engines/ (无状态计算层)            │ ← 纯计算在这里
├─────────────────────────────────────────┤
│      domain/ (领域模型层)               │ ← 核心概念在这里
├─────────────────────────────────────────┤
│  infrastructure/ (基础设施层)           │
└─────────────────────────────────────────┘
```

### 核心原则
1. **依赖方向**: 上层依赖下层，下层不能依赖上层
2. **状态隔离**: 所有可变状态集中在 runtime 层
3. **计算纯度**: engines 层只包含无状态纯函数
4. **边界清晰**: 每层都有明确的职责，不越界

---

## 各层职责详解

### domain/ - 领域模型层
**职责**: 定义核心业务概念和数据结构

**应包含**:
- ✅ 领域模型定义（dataclass, pydantic models）
- ✅ 领域事件定义
- ✅ 领域服务接口
- ✅ 值对象
- ✅ 聚合根
- ✅ 领域异常

**不应包含**:
- ❌ I/O 操作
- ❌ 具体实现逻辑
- ❌ 状态管理
- ❌ 外部依赖

**示例**:
```python
# domain/trade/models.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass(frozen=True)  # 不可变的值对象
class TradingSignal:
    signal_id: str
    symbol: str
    signal_type: SignalType
    confidence: float
    timestamp: datetime
```

---

### engines/ - 无状态计算层
**职责**: 实现纯计算逻辑，无副作用

**应包含**:
- ✅ 特征计算函数
- ✅ 策略逻辑（无状态）
- ✅ 信号融合算法
- ✅ 风险计算
- ✅ 适配器接口

**严格禁止**:
- ❌ 任何 `self._*` 可变状态变量
- ❌ 依赖 runtime 层
- ❌ 直接访问数据库/消息队列
- ❌ 非确定性操作

**正确示例**:
```python
# engines/compute/strategy/rsi_strategy.py
from typing import Optional, Tuple
from domain.trade.models import TradingSignal, SignalType

class RSIStrategy:
    """无状态 RSI 策略"""
    
    @staticmethod
    def calculate_signal(
        rsi_value: float,
        prev_rsi: Optional[float] = None,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0
    ) -> Tuple[Optional[TradingSignal], Optional[float]]:
        """
        纯函数计算信号
        
        Args:
            rsi_value: 当前 RSI 值
            prev_rsi: 前一周期 RSI 值（状态由调用方传入）
            oversold_threshold: 超卖阈值
            overbought_threshold: 超买阈值
            
        Returns:
            (signal, new_rsi_state)
        """
        signal = None
        
        if prev_rsi is not None:
            if prev_rsi >= oversold_threshold and rsi_value < oversold_threshold:
                signal = TradingSignal(...)
            elif prev_rsi <= overbought_threshold and rsi_value > overbought_threshold:
                signal = TradingSignal(...)
        
        return signal, rsi_value  # 返回新状态，由调用方管理
```

---

### runtime/ - 有状态执行层
**职责**: 管理执行状态，协调 engines 层的计算

**应包含**:
- ✅ 状态管理（策略状态、市场状态等）
- ✅ 执行引擎
- ✅ 状态持久化
- ✅ 事件处理循环
- ✅ 生命周期管理

**不应包含**:
- ❌ 复杂的业务计算逻辑（应委托给 engines）
- ❌ 直接对外 API

**示例**:
```python
# runtime/strategy_runtime.py
from typing import Dict, Any
from dataclasses import dataclass
from engines.compute.strategy.rsi_strategy import RSIStrategy

@dataclass
class StrategyInstanceState:
    strategy_id: str
    enabled: bool = True
    prev_rsi: float = None

class StrategyRuntime:
    """策略运行时 - 管理状态"""
    
    def __init__(self):
        self._states: Dict[str, StrategyInstanceState] = {}
    
    def process_tick(self, strategy_id: str, features: Dict[str, Any]):
        # 获取或创建状态
        state = self._get_or_create_state(strategy_id)
        
        if not state.enabled:
            return None
        
        # 委托计算给 engines 层
        signal, new_rsi = RSIStrategy.calculate_signal(
            rsi_value=features['rsi_14'],
            prev_rsi=state.prev_rsi
        )
        
        # 更新状态
        state.prev_rsi = new_rsi
        
        return signal
    
    def _get_or_create_state(self, strategy_id: str) -> StrategyInstanceState:
        if strategy_id not in self._states:
            self._states[strategy_id] = StrategyInstanceState(strategy_id=strategy_id)
        return self._states[strategy_id]
```

---

### application/ - 应用层
**职责**: 编排用例，协调各层完成业务目标

**应包含**:
- ✅ 应用服务
- ✅ 用例编排
- ✅ 命令处理
- ✅ 查询处理
- ✅ DTO 转换

**不应包含**:
- ❌ 核心业务逻辑（应在 domain/engines）
- ❌ 状态管理（应在 runtime）

---

### infrastructure/ - 基础设施层
**职责**: 提供技术能力实现

**应包含**:
- ✅ 数据库实现
- ✅ 消息队列客户端
- ✅ API 客户端
- ✅ 缓存实现
- ✅ 日志实现
- ✅ 配置管理

---

### adapters/ (在 engines 下)
**职责**: 连接外部系统的适配器

**应包含**:
- ✅ 交易所 API 适配器
- ✅ 数据源适配器
- ✅ 合约适配器

---

## 代码组织规范

### 文件命名约定
| 类型 | 命名规则 | 示例 |
|------|---------|------|
| 数据模型 | `*_models.py` 或 `models/*.py` | `trade_models.py` |
| 服务 | `*_service.py` | `strategy_service.py` |
| 计算器 | `*_calculator.py` 或 `*_engine.py` | `rsi_calculator.py` |
| 适配器 | `*_adapter.py` | `binance_adapter.py` |
| 运行时 | `*_runtime.py` | `signal_runtime.py` |

### 目录结构示例
```
backend/
├── domain/
│   ├── trade/
│   │   ├── models.py
│   │   └── events.py
│   └── strategy/
│       └── models.py
├── engines/
│   ├── compute/
│   │   ├── feature/
│   │   ├── strategy/
│   │   └── signal/
│   └── adapters/
│       ├── data/
│       └── exchange/
├── runtime/
│   ├── strategy_runtime.py
│   └── signal_runtime.py
├── application/
│   └── services/
└── infrastructure/
    ├── db/
    └── messaging/
```

---

## 依赖管理规则

### 允许的依赖
```
api → application → runtime → engines → domain
api ← application ← runtime ← engines ← domain
                    ↓
              infrastructure
```

### 禁止的依赖
❌ engines → runtime  
❌ domain → engines  
❌ domain → runtime  
❌ application → domain（仅允许通过接口）  

### 导入检查清单
创建新文件时检查：
- [ ] 没有从 runtime 导入到 engines
- [ ] 没有从 engines 导入到 domain
- [ ] 所有外部依赖都通过接口或参数传入
- [ ] 没有循环依赖

---

## 常见错误示例

### 错误 1: 在 engines 中管理状态
```python
# ❌ 错误
class BadStrategy:
    def __init__(self):
        self._prev_value = None  # 状态不应该在这里
    
    def calculate(self, value):
        result = self._prev_value + value if self._prev_value else value
        self._prev_value = value  # 修改状态
        return result
```

```python
# ✅ 正确
class GoodStrategy:
    @staticmethod
    def calculate(value, prev_value=None):
        result = prev_value + value if prev_value else value
        return result, value  # 返回新状态
```

### 错误 2: 跨层依赖
```python
# ❌ 错误: engines 依赖 runtime
from engines.compute.strategy import MyStrategy
from runtime.some_module import RuntimeThing  # 不应该

class MyStrategy:
    def do_something(self):
        runtime = RuntimeThing()  # 直接依赖
        ...
```

```python
# ✅ 正确: 通过参数注入
class MyStrategy:
    @staticmethod
    def do_something(some_dependency):  # 依赖作为参数传入
        ...
```

### 错误 3: domain 包含实现逻辑
```python
# ❌ 错误
@dataclass
class Trade:
    id: str
    
    def execute(self):  # domain 不应该包含实现
        # 连接数据库...
        # 执行交易...
        pass
```

```python
# ✅ 正确: domain 只定义模型
@dataclass(frozen=True)
class Trade:
    id: str

# 实现在 application 或 infrastructure
class TradeExecutor:
    def execute(self, trade: Trade):
        ...
```

---

## 检查清单

### 代码提交前检查
- [ ] 代码位于正确的层级
- [ ] engines 层没有 `self._*` 可变状态
- [ ] 没有反向依赖
- [ ] 所有新函数都有类型注解
- [ ] 添加了相应的单元测试
- [ ] 更新了相关文档

### Pull Request 审查检查
- [ ] 架构边界是否被尊重
- [ ] 是否有新的状态被错误地放在 engines 层
- [ ] 依赖关系是否清晰
- [ ] 测试是否充分

---

## 工具与自动化

### 推荐的架构检查工具
- 自定义的 lint 规则检查导入依赖
- 架构测试（使用 pytest 验证依赖关系）
- 代码审查 checklists

### 示例架构测试
```python
# tests/architecture/test_dependencies.py
import importlib
import pytest

def test_engines_not_import_runtime():
    """验证 engines 层不导入 runtime 层"""
    with pytest.raises(ImportError):
        importlib.import_module('engines.some_module')  # 如果导入了 runtime 会失败
```

---

## 参考资源
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain Driven Design Reference](https://domainlanguage.com/ddd-reference/)
