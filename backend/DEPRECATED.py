"""
DEPRECATED - 已废弃的代码模块

本文件记录了已废弃的代码模块及其替代方案。
请在新代码中使用替代方案，并逐步迁移旧代码。

## 核心原则

所有路径都走统一的 Runtime Pipeline：

    ingestion_runtime / replay_runtime
        ↓
    feature_runtime / domain/feature/unified_calculator.py
        ↓
    feature_matrix
        ↓
    signal_runtime
        ↓
    execution_runtime
        ↓
    projection_runtime

## 已废弃模块

### 1. scripts/ 目录（已删除）

所有 scripts 已迁移到对应模块：

| 已删除的脚本 | 替代方案 |
|-------------|----------|
| scripts/generate_features.py | domain/feature/generation_service.py |
| scripts/generate_orderbook_features.py | domain/feature/generation_service.py |
| scripts/generate_market_structure_features.py | domain/feature/generation_service.py |
| scripts/extract_orderbook_features.py | domain/feature/generation_service.py |
| scripts/quick_feature_extraction.py | domain/feature/generation_service.py |
| scripts/run_backtest.py | application/backtest_service.py |
| scripts/run_full_backtest.py | application/backtest_service.py |
| scripts/run_quick_backtest.py | application/backtest_service.py |
| scripts/backtest_all_strategies.py | application/backtest_service.py |
| scripts/backtest_strategies.py | application/backtest_service.py |
| scripts/strategy_optimization_backtest.py | application/backtest_service.py |
| scripts/strategy_optimization_backtest_fast.py | application/backtest_service.py |
| scripts/download_binance_klines.py | runtime/ingestion_runtime/download_service.py |
| scripts/download_binance_funding.py | runtime/ingestion_runtime/download_service.py |
| scripts/download_binance_oi.py | runtime/ingestion_runtime/download_service.py |
| scripts/download_binance_trades.py | runtime/ingestion_runtime/download_service.py |
| scripts/download_okx_*.py | runtime/ingestion_runtime/download_service.py |
| scripts/data_lake_download.py | runtime/ingestion_runtime/download_service.py |
| scripts/train_lstm_strategy.py | domain/ml/lstm_dataset_builder.py |
| scripts/train_ml_strategy.py | domain/ml/lstm_dataset_builder.py |

### 2. 参数优化

| 已废弃 | 替代方案 |
|--------|----------|
| scripts/strategy_optimization_backtest.py | application/optimization_service/engine.py |
| scripts/strategy_optimization_backtest_fast.py | application/optimization_service/engine.py |
| pandas 向量化回测 | shared/replay/market_event_emitter.py + engine.py |

### 3. 特征计算

| 已废弃 | 替代方案 |
|--------|----------|
| scripts/generate_features.py (独立实现) | domain/feature/unified_calculator.py |
| df["rsi"] 直接计算 | UnifiedFeatureCalculator.compute() |
| 离线特征脚本 | UnifiedFeatureCalculator.compute_from_parquet() |

### 4. 回测

| 已废弃 | 替代方案 |
|--------|----------|
| research/backtest/ | shared/replay/ + runtime/replay_runtime/ |
| backtest_service (独立实现) | runtime/execution_runtime/ |
| equity *= return | OptimizationBacktestEngine |

### 5. 数据加载

| 已废弃 | 替代方案 |
|--------|----------|
| pd.read_parquet() 直接读取 | shared/replay/market_event_emitter.py |
| dataframe 风格处理 | MarketEventEnvelope 事件流 |

## 迁移指南

### 优化迁移

旧代码：
```python
df = pd.read_parquet(path)
for combo in param_combinations:
    df['signal'] = compute_signal(df, combo)
    equity = compute_equity(df)
```

新代码：
```python
from application.optimization_service.engine import OptimizationBacktestEngine

engine = OptimizationBacktestEngine(config)
result = await engine.run(
    symbol="BTCUSDT",
    strategy_id="rsi_oversold",
    params={"period": 14, "oversold": 30},
    start_time=1704067200000,
    end_time=1735689600000,
)
```

### 特征计算迁移

旧代码：
```python
df["rsi_14"] = compute_rsi(df["close"], 14)
df["sma_20"] = df["close"].rolling(20).mean()
```

新代码：
```python
from domain.feature.unified_calculator import get_feature_calculator

calculator = get_feature_calculator()
features = calculator.compute(
    symbol="BTCUSDT",
    open_price=open_price,
    high=high,
    low=low,
    close=close,
    volume=volume,
)
```

### 回测迁移

旧代码：
```python
df = pd.read_parquet(path)
df["returns"] = df["close"].pct_change()
df["equity"] = (1 + df["returns"]).cumprod()
```

新代码：
```python
from shared.replay.market_event_emitter import MarketEventEmitter

emitter = MarketEventEmitter()
async for event in emitter.emit_from_feature_parquet(path, symbol, exchange):
    await signal_runtime.process(event)
    await execution_runtime.process(event)
```

## 统一架构

```
application/
├── optimization_service/
│   ├── engine.py          # 回测引擎（走 Runtime Pipeline）
│   ├── service.py         # 优化服务
│   └── models.py          # 数据模型

domain/
├── feature/
│   ├── unified_calculator.py  # 统一特征计算器
│   └── materializer/          # 特征材料化器
├── execution/
│   └── models/                # 执行模型

runtime/
├── replay_runtime/        # 回放运行时
├── signal_runtime/        # 信号运行时
├── execution_runtime/     # 执行运行时
├── projection_runtime/    # 投影运行时
└── orchestrator/          # 编排器

shared/
├── replay/
│   ├── market_event_emitter.py  # 事件发射器
│   ├── orchestrator.py          # 回放协调器
│   └── feature_availability_guard.py  # 防泄漏守卫
└── contracts/             # 统一合约
```

## 时间线

- 2026-05: 标记废弃
- 2026-06: 完成迁移
- 2026-07: 删除废弃代码
"""

import warnings


def deprecated(message: str):
    """废弃装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated: {message}",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator


DEPRECATED_MODULES = {
    "scripts.strategy_optimization_backtest": "use application.optimization_service.engine",
    "scripts.strategy_optimization_backtest_fast": "use application.optimization_service.engine",
    "scripts.generate_features": "use domain.feature.unified_calculator",
    "research.backtest": "use shared.replay + runtime.replay_runtime",
}
