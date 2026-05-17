# 交易模式使用指南

## 概述

系统支持三种交易模式，每种模式有不同的市场数据来源和订单执行方式：

| 模式 | 市场数据来源 | 订单执行方式 | 推荐用途 |
|------|------------|------------|--------|
| **Demo** | 测试环境 | 测试环境 | 初期开发、API连接测试 |
| **Paper** | 真实环境 | 本地撮合 | 策略验证（推荐！） |
| **Prod** | 真实环境 | 真实交易 | 实盘交易 |

## 快速开始

### 1. 配置 .env 文件

```env
# 选择交易模式
MODE=paper

# 交易所API密钥
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key

OKX_API_KEY=your_okx_api_key
OKX_API_SECRET=your_okx_secret_key
OKX_PASSPHRASE=your_okx_passphrase
```

### 2. 启动服务

```bash
# 方法1：混合模式（推荐）
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506
./start.sh --mixed

# 方法2：使用backend的dev脚本
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend
./dev.sh menu
```

### 3. 访问前端

```
http://localhost:3000
```

在右上角的交易模式选择器中可以查看和切换当前模式。

## 模式详解

### Demo 模式

**特点：**
- Binance使用Testnet端点
- OKX使用Demo Trading API（设置 `OK-ACCESS-FLAG: 1`）
- 不影响真实资金
- 流动性较差，不适合策略验证

**适用场景：**
- API连接测试
- 基础交易流程验证
- 功能开发和调试

### Paper Trading 模式（⭐推荐）

**特点：**
- ✅ 使用真实市场数据（实时价格、订单簿）
- ✅ 本地撮合，不消耗真实资金
- ✅ 模拟滑点和手续费
- ✅ 实时盈亏计算

**优势：**
- 真实的市场流动性
- 真实的价格波动
- 精确的策略表现评估
- 零资金风险

**适用场景：**
- 策略回测与验证
- 高频交易测试
- 策略表现评估
- 交易员培训

### Prod 模式

**⚠️ 警告：使用真实资金，请谨慎！**

**特点：**
- 真实市场数据
- 真实订单发送到交易所
- 真实资金变动

**安全检查清单：**
- [ ] 已充分在Demo模式测试
- [ ] 已充分在Paper模式验证
- [ ] 已设置API Key IP白名单
- [ ] 已限制API Key权限（不含提币权限）
- [ ] 已设置止损阈值

## 完整信号到交易流程

```
┌─────────────────────────────────────────────────────────────┐
│                    1. 数据采集层                            │
│   Ingestion Runtime - 从交易所、新闻源、社交媒体采集数据      │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    2. 信号生成层                            │
│   Signal Runtime - 融合事件、运行策略、生成决策信号            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. 人工审批层（可选）                     │
│   Decision Gate - 根据交易模式决定是否需要人工确认          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    4. 风控检查层                            │
│   Risk Engine - 检查仓位限制、杠杆限制、止损止盈等          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    5. 订单执行层                            │
│   Execution Runtime - 根据交易模式选择执行方式：             │
│   - Demo: 测试环境执行                                     │
│   - Paper: 本地撮合                                        │
│   - Prod: 真实环境执行                                      │
└─────────────────────────────────────────────────────────────┘
```

## API 接口

### 获取当前模式

```http
GET /api/v1/config/trading-mode
```

响应示例：
```json
{
  "mode": "paper",
  "description": "真实市场数据 + 本地撮合引擎 - 最适合策略验证，机构首选",
  "market_data_source": "real",
  "order_execution": "mock",
  "show_warning": false,
  "config": {
    "initial_balance": {"USDT": 100000},
    "slippage": 0.001,
    "fee": {"maker": 0.0002, "taker": 0.0004}
  }
}
```

### 获取可用模式列表

```http
GET /api/v1/config/trading-mode/options
```

## 测试验证

### 运行 Paper Trading 测试

```bash
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend
python scripts/test_paper_trading.py
```

### 运行双交易所测试

```bash
python scripts/test_dual_exchanges.py
```

### 运行单个交易所测试

```bash
# Binance测试
python scripts/test_binance_connection.py

# OKX测试
python scripts/test_okx_demo.py
```

## 常见问题

### Q: Paper Trading 模式真的使用真实价格吗？

是的！Paper Trading 模式会连接真实交易所的市场数据接口（WebSocket和REST），获取实时价格和订单簿信息。只有订单执行是在本地模拟的。

### Q: Paper Trading 模式会消耗API调用额度吗？

是的。但是获取市场数据的API调用通常是免费的，或者有很高的频率限制。

### Q: 如何在前端切换交易模式？

前端右上角有交易模式选择器。注意：切换模式需要修改 `.env` 文件中的 `MODE` 变量并重启服务。

### Q: 两种交易所可以同时使用吗？

可以！系统支持同时配置和使用 Binance 和 OKX。订单执行时会根据信号中的 `exchange` 字段选择对应的适配器。

### Q: 如何确保不意外进入Prod模式？

可以在代码中设置双重确认，或者在 .env 中设置 `ALLOW_TRADING=false` 来彻底禁用真实交易。
