# Binance API 配置指南

## 概述

本文档说明如何为 TradeAgent 系统配置 Binance API。

## 获取 Binance API Keys

### 1. 登录 Binance

访问 https://www.binance.com 并登录你的账户。

### 2. 进入 API 管理

1. 点击右上角头像
2. 选择 "API Management"
3. 或直接访问: https://www.binance.com/en/my/settings/api-management

### 3. 创建 API Key

1. 点击 "Create API"
2. 选择密钥类型（推荐 "System generated"）
3. 输入标签名称（如 "TradeAgent"）
4. 完成安全验证（2FA）
5. **重要**：记录显示的 API Key 和 Secret Key
   - API Key 可随时查看
   - **Secret Key 只显示一次，务必立即保存！**

### 4. 配置 API 权限

根据你的使用场景配置权限：

**仅读取（推荐用于数据采集）：**
- Enable Spot & Margin Trading: ❌
- Enable Futures: ❌
- Enable Withdrawal: ❌

**交易权限：**
- Enable Spot & Margin Trading: ✅（如需现货交易）
- Enable Futures: ✅（如需合约交易）
- Enable Withdrawal: ❌（**永远不要勾选！**）

## 配置到 .env

在 `backend/.env` 中添加：

```env
# ==================== 交易所配置 ====================
# 启用哪些交易所（逗号分隔）
ENABLED_EXCHANGES=binance,okx

# Binance API Keys
# 注意：这是测试网 API Key，从 https://testnet.binancefuture.com/ 获取
BINANCE_API_KEY=your_binance_testnet_api_key
BINANCE_SECRET_KEY=your_binance_testnet_secret_key
```

## 测试网 vs 主网

### Testnet（测试网）

- **用途**：开发测试，不使用真实资金
- **API**: `https://testnet.binancefuture.com`
- **WebSocket**: `wss://stream.binancefuture.com/ws`
- **获取测试资金**: https://testnet.binancefuture.com/

### Mainnet（主网）

- **用途**：真实交易
- **API**: `https://fapi.binance.com`
- **WebSocket**: `wss://stream.binancefuture.com/ws`

### 切换方式

在代码中通过 `testnet` 参数控制：

```python
from services.execution_service.adapters.binance_futures_adapter import BinanceFuturesAdapter

# Testnet
adapter = BinanceFuturesAdapter(
    api_key="your_testnet_key",
    api_secret="your_testnet_secret",
    testnet=True  # True = 测试网
)

# Mainnet
adapter = BinanceFuturesAdapter(
    api_key="your_mainnet_key",
    api_secret="your_mainnet_secret",
    testnet=False  # False = 主网
)
```

或在 `.env` 中设置：

```env
# Testnet
EXECUTION_TESTNET=true

# Mainnet
EXECUTION_TESTNET=false
```

## 验证连接

运行测试脚本：

```bash
cd backend
python scripts/test_binance_connection.py
```

预期输出：
```
Binance Futures Testnet Connection Test
✓ Account: ...
✓ BTCUSDT Price: ...
✓ Balance: ...
✓ Positions: []
```

## 权限说明

### 合约交易权限

| 权限 | 说明 | 是否需要 |
|------|------|----------|
| Enable Futures | 允许合约交易 | ✅（如需交易合约）|
| Enable Withdrawal | 允许提币 | ❌（危险！）|

### 建议的安全设置

1. **IP 白名单**：限制 API 只能从特定 IP 调用
2. **权限最小化**：只启用需要的权限
3. **定期轮换**：定期更换 API Key
4. **监控**：定期检查 API 使用记录

## Binance 适配器

项目中已经包含两个 Binance 适配器：

### 1. `BinanceFuturesAdapter` (推荐)

- **文件**: `services/execution_service/adapters/binance_futures_adapter.py`
- **支持**: USDT-M 合约
- **特点**:
  - 自定义实现，更轻量
  - WebSocket 实时更新
  - 支持杠杆设置
  - 支持 reduce_only 订单
  - 支持市价/限价/止损单

### 2. `BinanceAdapter`

- **文件**: `services/execution_service/adapters/binance_adapter.py`
- **支持**: 现货和合约
- **特点**:
  - 使用 ccxt 库
  - 更通用的实现

## API 端点

### 现货

**Testnet:**
- API: `https://testnet.binance.vision`
- WebSocket: `wss://testnet.binance.vision/ws`

**Mainnet:**
- API: `https://api.binance.com`
- WebSocket: `wss://stream.binance.com:9443/ws`

### 合约

**Testnet:**
- API: `https://testnet.binancefuture.com`
- WebSocket: `wss://stream.binancefuture.com/ws`

**Mainnet:**
- API: `https://fapi.binance.com`
- WebSocket: `wss://stream.binancefuture.com/ws`

## 测试网资金

Binance 测试网提供虚拟资金用于测试：

1. 访问: https://testnet.binancefuture.com/
2. 登录你的 Binance 账户
3. 点击 "Wallet" -> "Futures USDT"
4. 点击 "Transfer" 添加虚拟资金
5. 输入金额（建议 1000-10000 USDT）

**注意**：测试网资金是独立的，与主网资金无关。

## 常见问题

### Q: API Key 无效？

检查：
- API Key 是否正确复制
- Secret Key 是否正确
- 是否启用了相应权限
- 网络连接是否正常

### Q: 连接超时？

可能原因：
- 网络问题（VPN/防火墙）
- API 频率限制
- 测试网服务器不稳定

### Q: 订单下单失败？

检查：
- API Key 权限（Enable Futures）
- 账户余额是否足够
- 持仓数量是否在限制内

### Q: Secret Key 忘记了？

**无法找回！** 只能：
1. 删除旧的 API Key
2. 创建新的 API Key
3. 重新配置

## 安全提示

⚠️ **永远不要提交 .env 文件到版本控制！**

添加以下内容到 `.gitignore`：
```gitignore
.env
.env.local
.env.production
.env.*.local
```

⚠️ **保护好 Secret Key！**
- Secret Key 只在创建时显示一次
- 不要通过邮件/聊天发送
- 存储在安全的地方（如密码管理器）

⚠️ **最小权限原则：**
- 只启用需要的权限
- **永远不要启用 Withdrawal！**
- 设置 IP 白名单

## 官方文档

- Binance API 文档: https://developers.binance.com/docs
- 测试网文档: https://developers.binance.com/docs/binance-spot-api-docs/demo-mode/general-info
- 合约文档: https://developers.binance.com/docs/derivatives
