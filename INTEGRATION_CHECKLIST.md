
## 前端和后端集成状态 - 集成报告
---

### 📋 完整架构状态检查

### 🟢 **后端** - 完整
- ✅ API 网关 (api_server.py): 端口 **8001** - 提供 dashboard/prices/news 等接口
- ✅ Execution Service (http_server.py): 端口 **8000** - 提供执行/健康检查/指标
- ✅ 风险引擎 (8个检查器): 回撤/订单大小/交易对黑名单/止损检查/持仓/杠杆/亏损/冷却时间
- ✅ 交易所适配器: Binance/Binance Futures/OKX/Mock
- ✅ 持久化: 内存 + PostgreSQL ORM
- ✅ 指标: Prometheus 导出

### 🟡 **前端** - 完整 UI
- ✅ React/Vite/TypeScript
- ✅ 所有页面: Dashboard/Positions/Execution/Risk/Regime/WeightConfig
- ✅ API 调用框架

### 📝 需要整合的服务
---

#### 前端需要访问执行服务的API:
- 1️⃣ 执行订单: `/api/v1/orders/execute` (POST)
- 2️⃣ 订单列表: `/api/v1/orders` (GET)
- 3️⃣ 持仓列表: `/api/v1/positions` (GET)
- 4️⃣ 平仓: `/api/v1/positions/{symbol}/close` (POST)
- 5️⃣ 健康检查: `/health`
- 6️⃣ 指标: `/metrics`

### 🔌 连接方案
---
#### 方案 A: 分开服务, 前端代理两个服务 (推荐)
  - 前端开发: 前端通过 vite 代理到两个后端
  - 前端直接调用:  `/api/v1/ → 网关8001 , `/execution/` → 执行服务8000

#### 方案 B: 统一 API 网关包含执行服务
  - 执行服务路由挂载到网关

### 启动方式
---
启动命令:
```bash
# 1. 终端1: 启动 API Gateway (主数据接口, 8001)
cd backend
python api_server.py

# 2. 终端2: 启动 Execution Service (执行/风控, 8000)
cd backend/services/execution_service
python http_server.py

# 3. 终端3: 启动 Frontend
cd frontend
npm run dev
```

### 前端配置 Vite proxy (可选)
---
更新 vite.config.ts:
```typescript
proxy: {
  '/api/v1': {
    target: 'http://localhost:8001',
    changeOrigin: true
  },
  '/execution': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/execution/, '')
  }
}
```
