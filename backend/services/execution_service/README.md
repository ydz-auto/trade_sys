# Execution Service

专业的订单执行服务，支持现货和合约交易，包含完整的风控体系。

## 功能特性

- ✅ **多交易所支持** - Binance 现货、USDT 合约
- ✅ **完整领域模型** - OrderIntent、Order、Position
- ✅ **风控引擎** - 持仓限制、杠杆限制、每日亏损、冷却期
- ✅ **持久化存储** - 基于 StateManager 的 Redis 支持
- ✅ **WebSocket 实时同步** - Binance User Data Stream
- ✅ **Kafka 消息驱动** - 事件驱动架构

## 快速开始

### 1. 配置环境

```bash
cd services/execution_service
cp .env.example .env
# 编辑 .env 文件配置 API 密钥
```

### 2. 运行服务

```bash
# 开发模式（使用 Mock 适配器）
python main_kafka.py

# 合约测试网模式
EXECUTION_MOCK=false EXECUTION_MARKET_TYPE=usdt_futures python main_kafka.py
```

### 3. 代码示例

#### 基本使用

```python
import asyncio
from domain.execution.models import (
    OrderIntent, OrderSide, Exchange, MarketType
)
from services.execution_service.engine import get_execution_engine
from services.execution_service.adapters import MockAdapter

async def main():
    engine = get_execution_engine()
    engine.register_adapter(MockAdapter())
    await engine.connect_all()

    # 使用 OrderIntent 执行
    intent = OrderIntent(
        intent_id="test_001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=0.001,
        exchange=Exchange.BINANCE,
        market_type=MarketType.SPOT,
    )
    result = await engine.execute_intent(intent)
    print(f"Result: {result}")

asyncio.run(main())
```

#### 合约交易

```python
# 快速合约下单
result = await engine.execute_futures_order(
    symbol="BTCUSDT",
    side="buy",
    quantity=0.001,
    leverage=5,
    reduce_only=False,
)

# 平仓
result = await engine.close_position(
    symbol="BTCUSDT",
    market_type=MarketType.USDT_FUTURES,
)
```

## 目录结构

```
services/execution_service/
├── __init__.py
├── main_kafka.py              # Kafka 消费者入口
├── fill_sync.py               # 成交同步管理器
│
├── adapters/                  # 交易所适配器
│   ├── base.py
│   ├── binance_adapter.py
│   ├── binance_futures_adapter.py
│   └── mock_adapter.py
│
├── engine/                    # 执行引擎
│   ├── execution_engine.py
│   ├── order_manager.py
│   └── position_manager.py
│
├── storage/                   # 持久化存储
│   ├── order_repository.py
│   └── position_repository.py
│
├── risk/                      # 风控引擎
│   ├── risk_engine.py
│   ├── position_limit.py
│   ├── leverage_limit.py
│   ├── daily_loss_limit.py
│   └── cooldown_checker.py
│
├── consumers/                 # 消费者
│   └── signal_consumer.py
│
└── publishers/                # 发布者
    └── order_publisher.py

domain/execution/
├── config.py
└── models/
    ├── enums.py
    ├── order.py
    ├── position.py
    └── events.py
```

## 架构说明

### 执行流程

```
Signal → SignalConsumer 
         ↓
    OrderIntent (执行意图)
         ↓
    RiskEngine (风控检查)
         ↓
    ExecutionEngine
         ↓
    Adapter (Binance/Mock)
         ↓
    Position/Order 更新
```

### 领域模型

- **OrderIntent** - 执行意图，包含风控参数
- **Order** - 订单实体
- **Position** - 持仓实体
- **MarketType** - 市场类型（SPOT/FUTURES/SWAP）

### 风控检查

| 检查器 | 说明 | 默认配置 |
|--------|------|----------|
| PositionLimitChecker | 持仓数量/价值限制 | 最多 10 个，价值 ≤ 10,000 |
| LeverageLimitChecker | 杠杆限制 | 最大 10 倍，警告 5 倍 |
| DailyLossLimitChecker | 每日亏损限制 | ≤ 初始资金 10% |
| CooldownChecker | 交易冷却期 | 默认 5 分钟 |

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| EXECUTION_MOCK | 使用 Mock 适配器 | true |
| BINANCE_API_KEY | Binance API Key | - |
| BINANCE_API_SECRET | Binance API Secret | - |
| BINANCE_TESTNET | 使用测试网 | true |
| EXECUTION_MARKET_TYPE | 市场类型 | spot |
| RISK_MAX_POSITION_VALUE | 最大持仓价值 | 10000 |
| RISK_MAX_POSITION_COUNT | 最大持仓数 | 10 |
| RISK_MAX_LEVERAGE | 最大杠杆 | 10 |
| RISK_MAX_DAILY_LOSS_PCT | 日亏损比例 | 0.1 (10%) |

## 下一步

1. 接入真实 Binance Testnet 测试合约
2. 配置 Redis 持久化
3. 添加更多风控规则
4. 接入 OKX Swap
