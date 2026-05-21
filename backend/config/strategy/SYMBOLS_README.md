# 币种专属策略系统

## 概述

本系统支持为每个加密货币币种配置独立的策略参数，包括：
- 技术指标参数（RSI、MACD等）
- 风险参数（杠杆、止损止盈等）
- 策略触发阈值
- 启用/禁用的策略列表

## 文件结构

```
config/strategy/
├── symbols/                  # 币种专属配置目录
│   ├── btcusdt.yaml         # BTC配置
│   ├── ethusdt.yaml         # ETH配置
│   ├── solusdt.yaml         # SOL配置
│   └── ...
├── SYMBOLS_README.md        # 本说明文档
└── btc_swing.yaml           # 原有的通用策略配置
```

## 配置说明

每个币种的配置文件包含以下部分：

### 基础信息
```yaml
symbol: BTCUSDT              # 交易对
base_currency: BTC           # 基础币种
enabled: true                # 是否启用
description: "描述"
```

### 市场特征
```yaml
volatility_profile: medium   # 波动率特征: low/medium/high
liquidity_profile: high      # 流动性特征: low/medium/high
primary_timeframe: 1h        # 主时间周期
```

### 风险参数
```yaml
risk:
  position_size: 0.025       # 仓位大小
  max_leverage: 25           # 最大杠杆
  min_leverage: 10           # 最小杠杆
  stop_loss_pct: 10.0        # 止损(%)
  take_profit_pct: 20.0      # 止盈(%)
```

### 策略参数
每个策略都有独立的参数配置，例如：
```yaml
rsi_strategy:
  period: 14
  oversold: 28.0
  overbought: 72.0
```

### 因子权重
```yaml
factor_weights:
  momentum: 0.35
  trend: 0.3
  flow: 0.2
  sentiment: 0.15
```

## 使用方法

### 1. 配置管理器
```python
from domain.strategy.symbol_config import get_symbol_config_manager

manager = get_symbol_config_manager()

# 获取币种配置
config = manager.get_config("BTCUSDT")

# 获取所有启用的币种
symbols = manager.get_enabled_symbols()

# 创建默认配置
new_config = manager.create_default_config("AVAXUSDT")
manager.save_config(new_config)
```

### 2. 策略编排器
```python
from services.strategy_service.symbol_strategies import get_symbol_strategy_orchestrator

orchestrator = get_symbol_strategy_orchestrator()

# 更新市场数据
orchestrator.update_market_data("BTCUSDT", market_data)

# 处理单个币种
signals = orchestrator.process_symbol("BTCUSDT")

# 处理所有币种
all_signals = orchestrator.process_all()

# 获取风险配置
risk_config = orchestrator.get_risk_config("BTCUSDT")
```

### 3. 运行测试
```bash
cd backend
python scripts/test_symbol_strategy.py
```

## 币种特性参考

| 币种 | 波动率 | 推荐杠杆 | 周期 |
|------|--------|----------|------|
| BTC | 中等 | 15-25x | 1h/4h |
| ETH | 中高 | 12-22x | 1h/4h |
| SOL | 高 | 8-15x | 30m/2h |
| DOGE | 极高 | 5-10x | 15m/1h |

## 配置参数优化建议

### 高波动币种 (SOL, AVAX)
- 降低仓位大小 (0.01-0.015)
- 降低杠杆 (8-15x)
- 收紧止损 (6-8%)
- 使用更短周期 (30m)

### 低波动币种 (BTC, ETH)
- 提高仓位大小 (0.02-0.025)
- 提高杠杆 (15-25x)
- 普通止损 (10%)
- 使用标准周期 (1h/4h)

## 文件说明

- `domain/strategy/symbol_config.py` - 配置管理核心模块
- `services/strategy_service/symbol_strategies.py` - 币种专属策略服务
- `scripts/generate_symbol_configs.py` - 配置生成脚本
- `scripts/test_symbol_strategy.py` - 系统测试脚本
