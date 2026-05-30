# Compute — 无状态纯计算层

`engines/compute/` 是项目的无状态纯计算层，所有函数必须是确定性的、无副作用的。

## 架构边界

```
domain/          → 定义领域模型、事件、核心业务概念（"是什么"）
  ↑
engines/compute/ → 实现无状态计算逻辑（"怎么算"）
  ↑
runtime/         → 持有可变状态，编排计算调用
```

## 子目录职责

### aggregation/
- **职责**：K 线聚合与事件分组
- **边界**：纯统计计算，输入 K 线序列，输出聚合结果

### context/
- **职责**：MarketContext 构建与校验
- **包含**：builder、feature_map、leakage_guard、schema、validators
- **边界**：接收原始数据，输出 MarketContext，不维护内部状态

### correlation/
- **职责**：相关性计算
- **边界**：纯统计计算，输入特征序列，输出相关系数

### feature/
- **职责**：特征计算与特征矩阵管理
- **包含**：core_calculators、feature_engine、feature_matrix、matrix_builder、torch_calculator、unified_calculator、feature_aligner、historical_materializer、trade_flow_engine
- **边界**：纯函数计算，特征窗口状态由 runtime 管理

### risk/
- **职责**：风险计算与检查
- **包含**：compute（纯计算）、engine（编排）、checkers/（各类检查器：blacklist、cooldown、daily_loss、drawdown、leverage、order_size、position、stop_loss）
- **边界**：纯风险计算函数，输入当前状态，输出风险判定

### scoring/
- **职责**：LLM 打分
- **边界**：纯打分函数，输入待评分内容，输出分数

### signal/
- **职责**：信号生成、融合与打分
- **包含**：buffer、confluence_engine、fusion_engine、fusion_handlers、scorer
- **边界**：融合引擎接收完整输入并产生输出，不维护内部状态

### strategy/
- **职责**：策略计算器（纯计算）
- **包含**：calculators/（arbitrage、behavioral、bollinger、macd、microstructure、rsi、technical、trend）
- **边界**：纯函数，所有状态由 runtime/strategy_runtime 管理

### strategy_v2/
- **职责**：策略 V2（MarketContext 驱动）
- **包含**：base、metadata、registry、strategies/（funding_extreme_reversal、liquidation_cascade、oi_behavior、short_squeeze、trade_pressure_bounce）
- **边界**：策略实现应是无状态的，所有状态由 runtime 管理

### trade_flow/
- **职责**：交易流计算与材料化管道
- **边界**：纯计算，输入交易数据，输出材料化结果

## 严格禁止

1. **任何有状态对象**
   - 不要维护 `self._prev_*` 等历史状态变量
   - 不要在策略类中存储 `self._enabled` 等可变状态
   - 需要状态的逻辑应将状态作为参数传入，由 runtime 管理

2. **跨层调用 runtime**
   - compute 层不能调用 runtime 层
   - 不能直接访问数据库或消息队列
   - 所有外部依赖通过参数传入

3. **副作用 / IO**
   - 不能修改全局状态
   - 不能进行 IO 操作
   - 确定性输出（相同输入 → 相同输出）

4. **全局单例**
   - 不要使用模块级可变全局变量
   - 不要使用单例模式持有状态

## 已完成的迁移

| 原位置 | 迁移目标 | 说明 |
|--------|----------|------|
| `compute/models/` | 已删除 | 数据模型已由 `domain/` 统一定义 |
| `compute/schemas/` | `domain/` | 信号模式定义已迁移到领域层 |
| `compute/feature/kline_loader.py` | `infrastructure/repositories/` | K 线数据加载已迁移到基础设施层 |
| `compute/feature/funding_loader.py` | `infrastructure/repositories/` | 资金费率加载已迁移到基础设施层 |

## 正确的架构示例

### 错误：在 compute 中管理状态

```python
class BadStrategy:
    def __init__(self):
        self._prev_price = None

    def generate_signal(self, price):
        if self._prev_price is not None:
            pass
        self._prev_price = price
```

### 正确：状态由 runtime 管理

```python
class GoodStrategy:
    @staticmethod
    def generate_signal(price, prev_price):
        return signal

class StrategyRuntime:
    def __init__(self):
        self._prev_price = None

    def process(self, price):
        signal = GoodStrategy.generate_signal(price, self._prev_price)
        self._prev_price = price
        return signal
```

## 与 domain/ 的边界

- **domain/**：定义领域模型、事件、核心业务概念（"是什么"）
- **engines/compute/**：实现领域模型的无状态计算逻辑（"怎么算"）
- 避免重复：domain 定义数据结构和语义，compute 实现计算过程
