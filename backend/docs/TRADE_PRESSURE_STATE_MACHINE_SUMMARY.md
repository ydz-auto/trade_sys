# Trade Pressure 与 Market State Machine 实现总结

## 概述

本次实现完成了您建议的架构优化，主要包括：

1. **统一配置类型** - 解决了参数管理问题
2. **Trade Pressure 事件体系** - 将 detect 方法转换为事件检测器
3. **Market State Machine** - 完整的市场状态管理系统

## 1. 统一配置类型 (`domain/config/`)

### 文件结构
```
domain/config/
├── __init__.py
├── strategy_config.py       # 策略配置
├── feature_config.py        # 特征配置
├── runtime_config.py        # 运行时配置
└── execution_config.py      # 执行配置
```

### 主要特性
- **类型安全** - 所有配置都是强类型的 dataclass
- **不可变** - 支持 `frozen=True` 防止运行时篡改
- **序列化** - `to_dict()` 和 `from_dict()` 支持存储和传输
- **验证** - `__post_init__` 自动验证参数合法性

### 使用示例
```python
from domain.config.strategy_config import StrategyConfigV2, EntryParams, ExitParams

config = StrategyConfigV2(
    strategy_id="reversal_strategy",
    strategy_name="均值回归",
    entry_params=EntryParams(signal_threshold=0.6),
    exit_params=ExitParams(stop_loss_pct=0.02),
)
```

## 2. Trade Pressure 事件体系 (`domain/event/` 和 `domain/feature/indicators/`)

### 新增事件类型
扩展了 `EventType` 枚举：
- `TRADE_PRESSURE_FLUSH` - 压力释放
- `TRADE_PRESSURE_EXHAUSTION` - 压力耗尽
- `TRADE_PRESSURE_ABSORPTION` - 压力吸收
- `TRADE_PRESSURE_DIVERGENCE` - 压力背离
- `TRADE_PRESSURE_SQUEEZE` - 挤压
- `TRADE_PRESSURE_BUILDUP` - 压力积累
- `LIQUIDITY_VACUUM` / `LIQUIDITY_FLOOD` - 流动性事件
- `ORDERBOOK_SWEEP` / `ORDERBOOK_SPOOF` - 订单簿事件

### 新增检测器 (`trade_pressure.py`)
- `TradePressureDetector` - 专门检测交易压力事件
- `TradePressureEvent` - 完整的事件数据结构
- 集成到 `BehaviourDetector` 中使用

### 事件检测逻辑
每个事件基于多个维度综合判断：
- 买卖不平衡
- 成交量变化
- 波动率
- 价格运动
- 订单簿不平衡

## 3. Market State Machine (`domain/market_state/`)

### 文件结构
```
domain/market_state/
├── __init__.py
├── state.py         # 状态定义
├── machine.py       # 状态机实现
└── examples.py      # 使用示例
```

### 状态维度
1. **RegimeType** - 整体市场状态
   - `TRENDING_UP`, `TRENDING_DOWN`, `MEAN_REVERTING`
   - `CRASH`, `SQUEEZE`, `QUIET`, `AUCTION`, `UNKNOWN`

2. **LiquidityState** - 流动性状态
   - `NORMAL`, `THIN`, `VACUUM`, `FLOODED`, `DRYING`

3. **PressureState** - 压力状态
   - `BUILDUP`, `EXHAUSTED`, `FLUSHED`, `ABSORBED`, `DIVERGENCE`, `NEUTRAL`

4. **VolatilityState** - 波动率状态
   - `LOW`, `NORMAL`, `ELEVATED`, `EXTREME`

5. **TrendState** - 趋势状态
   - `STRONG_UP`, `WEAK_UP`, `SIDEWAYS`, `WEAK_DOWN`, `STRONG_DOWN`

### MarketState 特性
- **完全不可变** - 使用 `frozen=True` 防止副作用
- **便捷查询方法** - `is_exhausted()`, `is_liquid_vacuum()` 等
- **特征快照** - 记录状态转换时的特征值
- **完整历史** - 所有状态变更都有历史记录

### MarketStateMachine 特性
- **事件驱动更新** - 通过 `update(event_type, features)` 推进状态
- **状态转换规则** - 基于事件和特征计算新状态
- **信心度计算** - 评估状态转换的可靠性
- **历史查询** - 支持获取任意时刻的状态

## 4. 如何使用

### 基础流程
```python
# 1. 初始化组件
from domain.market_state.machine import MarketStateMachine
from domain.feature.indicators.trade_pressure import TradePressureDetector

state_machine = MarketStateMachine(symbol="BTCUSDT")
detector = TradePressureDetector()

# 2. 检测事件
tp_event = detector.detect(
    current_price=50000.0,
    volume=300,
    buy_volume=80,
    sell_volume=220,
    orderbook_imbalance=-0.4,
    price_change_5min=-0.03,
    price_change_15min=-0.05,
    symbol="BTCUSDT",
)

# 3. 更新市场状态
if tp_event.event_type:
    features = {
        "pressure_zscore": -2.5,
        "volatility_zscore": 2.0,
        "trend_strength": -0.6,
    }
    new_state = state_machine.update(tp_event.event_type, features)

# 4. 使用状态做决策
if new_state.is_exhausted() and new_state.is_high_confidence():
    # 做反转交易决策
    pass
```

### 策略使用示例
```python
def generate_signal(state: MarketState, event):
    """基于 MarketState 的策略"""
    if (
        state.is_exhausted()
        and state.is_liquid_vacuum()
        and state.confidence > 0.7
    ):
        return Signal(direction=LONG, reason="Pressure Exhaustion + Liquidity Vacuum")
    return None
```

## 5. 优势总结

### 解决的问题
1. **参数管理** - 不再是散 params，统一配置类型
2. **事件 vs 信号** - 检测器现在生成事件，而不是直接信号
3. **状态管理** - MarketState 提供了单一事实来源
4. **可追溯性** - 完整的状态历史，支持回测和回放
5. **类型安全** - 大量使用类型提示和 dataclass

### 架构优势
1. **解耦** - 事件、状态、策略完全分离
2. **可测试** - 每个组件可以独立测试
3. **可扩展** - 新增状态或事件类型很容易
4. **可回放** - 状态历史支持完整的回放验证

### 与现有系统集成
- `BehaviourDetector` 已集成 `TradePressureDetector`
- `EventType` 保持向后兼容
- 支持与现有的 backtest/replay 系统配合使用

## 6. 运行示例

查看并运行示例：
```bash
cd backend
python -m domain.market_state.examples
```

## 7. 后续建议

1. **配置管理** - 将配置与 config 系统集成
2. **持久化** - 支持 MarketState 持久化存储
3. **更多状态** - 逐步完善状态转换规则
4. **真实数据** - 在实际数据流中验证状态机
5. **策略迁移** - 将现有策略逐步迁移到使用 MarketState
