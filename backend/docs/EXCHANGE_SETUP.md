# 交易所环境配置指南

## 三种交易模式

系统支持三种交易环境，通过 `MODE` 环境变量配置：

| 模式 | 市场数据 | 订单执行 | 推荐用途 |
|------|---------|---------|----------|
| **demo** | Testnet | Testnet | 初期开发、API 测试 |
| **paper** | Real (真实) | Local Matching (本地撮合) | **策略验证首选** |
| **prod** | Real (真实) | Real Execution | 实盘交易 |

### 为什么 Paper Trading 最重要？

相比 Testnet，Paper Trading 有巨大优势：

- ✅ **真实市场流动性** - 无需假订单填充
- ✅ **真实订单簿** - 深度更精确
- ✅ **真实成交** - 更准确的策略验证
- ✅ **本地模拟撮合** - 无需真实资金，零风险

这是机构级策略验证的标准做法！

---

## 快速配置

### 1. 创建 .env 配置

```env
# ==================== 交易模式配置 ====================
# 可选值: demo, paper, prod
MODE=paper

# ==================== 交易所配置 ====================
# 启用哪些交易所（逗号分隔）
ENABLED_EXCHANGES=binance,okx

# Binance API Keys (从 Binance 获取)
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key

# OKX API Keys (从 OKX 获取)
OKX_API_KEY=your_okx_api_key
OKX_API_SECRET=your_okx_secret_key
OKX_PASSPHRASE=your_okx_passphrase

# 市场类型 (spot, usdt_futures, coin_futures, swap)
EXECUTION_MARKET_TYPE=usdt_futures
```

### 2. 获取 API Keys

#### Binance

1. 访问 https://www.binance.com/en/support/faq/how-to-create-api-keys-on-binance-115000894493
2. 登录 Binance 账户
3. 进入 API Management
4. 创建 API Key（选择 "System generated"）
5. 设置权限：Enable Spot & Margin Trading（现货）或 Enable Futures（合约）
6. **重要**：记录 API Key 和 Secret Key（Secret 只显示一次！）

#### OKX

1. 访问 https://www.okx.com/account/my-api
2. 点击 "Demo Trading" (模拟交易) 标签
3. 创建 API Key
4. 权限选择：
   - Read
   - Trade
   - (不选 Withdraw)
5. 保存三个信息：
   - API Key
   - Secret Key
   - Passphrase

### 3. 测试连接

```bash
cd backend

# 测试所有交易所
python scripts/test_exchanges.py

# 仅测试 Paper Trading
python scripts/test_paper_trading.py
```

---

## 三种模式详解

### Demo 模式

**配置：**
```env
MODE=demo
```

**行为：**
- Binance: 使用 `https://testnet.binancefuture.com`（测试网）
- OKX: 使用真实 API 端点，但 `OK-ACCESS-FLAG: 1`（Demo 标识）
- 订单发送到交易所测试环境
- 虚拟资金，不影响真实账户

**适用场景：**
- 初期开发
- API 功能测试
- 基础交易流程验证

**注意：** Testnet 流动性差，订单簿不真实，不适合策略验证！

---

### Paper Trading 模式 ⭐

**配置：**
```env
MODE=paper
```

**行为：**
- 获取真实市场数据（实时价格、订单簿）
- 订单在本地撮合引擎执行
- 模拟资金管理（初始 100,000 USDT）
- 计算手续费（0.02% Maker, 0.04% Taker）
- 模拟滑点（0.1%）

**架构：**
```
┌─────────────────────────────────────────────┐
│         Real Market Data Feed               │
│     (真实 WebSocket，实盘行情)               │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│       Paper Trading Adapter                 │
│  ┌─────────────────────────────────────────┐│
│  │     Local Order Matching Engine         ││
│  │         (本地模拟撮合引擎)               ││
│  └─────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────┐│
│  │     Position & Balance Manager         ││
│  │       (仓位与资金管理)                   ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

**适用场景：**
- ✅ 策略回测与验证
- ✅ 高频交易测试
- ✅ 真实市场条件下的策略评估
- ✅ 交易员培训

**优势：**
- 真实流动性，不依赖假数据
- 真实价格波动
- 精确的策略表现评估
- 零资金风险

---

### Prod 模式

**配置：**
```env
MODE=prod
ALLOW_TRADING=true
```

**行为：**
- 真实市场数据
- 真实订单发送到交易所
- 真实资金变动

**⚠️ 警告：**
- 使用真实资金！
- 务必充分测试后再启用
- 建议流程：
  1. Demo 环境测试 24-48 小时
  2. Paper 环境运行 1-2 周
  3. Prod 环境小资金试运行

---

## 前端模式切换

前端右上角提供了模式切换器：

1. **当前模式指示器** - 显示当前启用的模式
2. **下拉菜单** - 选择其他模式
3. **模式说明** - 每个模式的描述
4. **确认对话框** - 切换到实盘时需要确认

**注意：** 前端切换只是通知后端，实际模式切换需要：
1. 修改 `MODE` 环境变量
2. 重启后端服务

---

## API 端点

### OKX

**Demo Trading:**
- REST API: `https://www.okx.com` (需要 `OK-ACCESS-FLAG: 1`)
- Public WS: `wss://wspap.okx.com:8443/ws/public?brokerId=9999`
- Private WS: `wss://wspap.okx.com:8443/ws/private?brokerId=9999`

**Production:**
- REST API: `https://www.okx.com` (需要 `OK-ACCESS-FLAG: 0`)
- Public WS: `wss://ws.okx.com:8443/ws/public`
- Private WS: `wss://ws.okx.com:8443/ws/private`

### Binance

**Testnet:**
- REST API: `https://testnet.binancefuture.com`
- WebSocket: `wss://stream.binancefuture.com/ws`

**Production:**
- REST API: `https://fapi.binance.com`
- WebSocket: `wss://stream.binancefuture.com/ws`

---

## 安全注意事项

⚠️ **永远不要提交 .env 文件到 Git！**

添加 `.gitignore`：
```gitignore
.env
.env.local
.env.production
```

⚠️ **API Key 权限最小化：**
- 只选需要的权限
- 不要选 Withdraw (提币)
- 设置 IP 白名单
- 定期轮换密钥

⚠️ **安全检查清单：**
- [ ] API Key 已添加到 .env
- [ ] .env 已添加到 .gitignore
- [ ] API Key 权限已最小化
- [ ] 已在 Demo 模式测试
- [ ] 已在 Paper 模式验证策略

---

## 故障排除

### 连接失败

1. 检查 API Key 是否正确
2. 检查网络连接
3. 验证 API Key 权限
4. 查看日志：
```bash
cd backend
python -c "from dotenv import load_dotenv; load_dotenv(); from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter; import asyncio; asyncio.run(BinanceFuturesAdapter('test', 'test').connect())"
```

### Paper Trading 不工作

1. 确认 MODE=paper
2. 检查日志输出
3. 运行测试脚本：
```bash
python scripts/test_paper_trading.py
```

---

## 相关文档

- [Paper Trading 架构](services/execution_service/adapters/paper_trading_adapter.py)
- [Trading Mode 配置](domain/execution/trading_mode.py)
- [Binance 适配器](../services/execution_service/adapters/binance_futures_adapter.py)
- [OKX 适配器](../services/execution_service/adapters/okx_adapter.py)
