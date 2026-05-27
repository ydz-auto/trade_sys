# Engines Compute Module
这是项目核心的无状态计算层。

## 架构边界
```
domain/ (领域模型和事件)
   ↓
engines/ (无状态计算)
   ↓
runtime/ (有状态执行)
```

## 目录结构

### feature/
- **职责**: 无状态特征计算
- **边界**: 纯函数计算，特征窗口状态由 runtime 管理
- **包含**: 特征矩阵、历史特征材料化、GPU 加速计算

### strategy/
- **职责**: 纯策略逻辑计算
- **边界**: 策略实现应是无状态的，所有状态由 runtime/strategy_runtime 管理
- **包含**: 策略实现、策略注册表、行为策略

### signal/
- **职责**: 信号生成和融合逻辑
- **边界**: 融合引擎应接收完整输入并产生输出，不维护内部状态
- **包含**: 信号缓冲区、融合引擎、融合处理器、打分器

### risk/
- **职责**: 风险计算和检查
- **边界**: 纯风险计算函数
- **包含**: 风险计算器、各类风险检查器

### scoring/
- **职责**: 策略和信号打分
- **边界**: 纯打分函数
- **包含**: LLM 打分器

### aggregation/ & correlation/
- **职责**: 数据聚合和相关性计算
- **边界**: 纯统计计算

### models/ & schemas/
- **职责**: 计算所需的数据模型
- **边界**: 定义数据结构，不包含业务逻辑

## 严格禁止在本目录中

1. **任何有状态对象**
   - 不要维护 `self._prev_*` 等历史状态变量
   - 不要在策略类中存储 `self._enabled` 等可变状态

2. **跨层调用**
   - compute 层不能调用 runtime 层
   - 不能直接访问数据库或消息队列
   - 所有外部依赖通过参数传入

3. **副作用**
   - 不能修改全局状态
   - 不能进行 I/O 操作
   - 确定性输出

## 正确的架构示例

### 错误: 在 compute 中管理状态
```python
class BadStrategy:
    def __init__(self):
        self._prev_price = None  # 错误: 状态在 compute 中
    
    def generate_signal(self, price):
        if self._prev_price is not None:
            # 使用状态
        self._prev_price = price
```

### 正确: 状态由 runtime 管理
```python
class GoodStrategy:
    @staticmethod
    def generate_signal(price, prev_price):  # 状态作为参数传入
        # 纯计算逻辑
        return signal

# runtime 层管理状态
class StrategyRuntime:
    def __init__(self):
        self._prev_price = None
    
    def process(self, price):
        signal = GoodStrategy.generate_signal(price, self._prev_price)
        self._prev_price = price
        return signal
```

## 与 domain/ 的边界
- **domain/**: 定义领域模型、事件、核心业务概念
- **engines/compute/**: 实现领域模型的无状态计算逻辑
- **避免重复**: domain 定义"是什么"，compute 定义"怎么算"

## 当前问题与待重构
1. `strategy/strategies.py` 中存在大量状态变量需要迁移到 runtime
2. `MultiStrategyOrchestrator` 状态过重，应重构为轻量计算逻辑
3. 需要清理 strategy 模块与 domain/strategy/ 的重复定义
