# TradeAgent 交易系统产品功能文档

## 📋 概述

TradeAgent 是一个专业的加密货币量化交易系统，支持实盘交易、回测分析、信号生成和风险管理。

**技术栈**
- 后端: Python + FastAPI + Redis + Kafka
- 前端: React + TypeScript + TailwindCSS
- 数据库: Redis (缓存/投影) + PostgreSQL (持久化)
- 消息队列: Kafka

---

## 🎯 核心功能模块

### 1. 实盘交易

#### 1.1 交易所支持

| 交易所 | 现货 | USDT合约 | 币本位合约 | 状态 |
|--------|------|----------|------------|------|
| Binance | ✅ | ✅ | ✅ | 已支持 |
| OKX | ✅ | ✅ | ✅ | 已支持 |

#### 1.2 订单类型

| 订单类型 | 说明 | 状态 |
|----------|------|------|
| 市价单 (Market) | 以当前市场价格立即成交 | ✅ |
| 限价单 (Limit) | 指定价格成交 | ✅ |
| 止损单 (Stop) | 价格触发后下单 | ✅ |
| 止损市价单 (Stop Market) | 触发后以市价成交 | ✅ |
| 止盈市价单 (Take Profit Market) | 触发后以市价成交 | ✅ |

#### 1.3 合约功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 杠杆交易 | 1-125x 杠杆 | ✅ |
| 逐仓/全仓 | 持仓模式选择 | ✅ |
| 止盈止损 | 百分比/价格触发 | ✅ |
| 自动平仓 | 价格触发自动平仓 | ✅ |
| 仓位调整 | 修改持仓数量/杠杆 | ✅ |

#### 1.4 杠杆收益计算

```
实际收益 = 价格变动% × 杠杆倍数

示例：
- 开多 5x 杠杆
- 买入价: $50,000
- 价格上涨 2% → $51,000
- 实际收益: 2% × 5 = 10%
- 1个BTC收益: $500 (而非$100)
```

---

### 2. 回测系统

#### 2.1 支持的策略

| 策略 | 说明 | 状态 |
|------|------|------|
| SMA Crossover | 简单移动平均线交叉 | ✅ |
| RSI | 相对强弱指标 | ✅ |
| Momentum | 动量策略 | ✅ |

#### 2.2 回测参数

| 参数 | 类型 | 说明 |
|------|------|------|
| symbol | string | 交易对，如 "BTC/USDT" |
| start_date | date | 开始日期 "YYYY-MM-DD" |
| end_date | date | 结束日期 "YYYY-MM-DD" |
| initial_capital | float | 初始资金 |
| strategy | string | 策略类型 |
| leverage | int | 杠杆倍数 (1-125) |
| position_size | float | 仓位比例 (0-1) |
| stop_loss | float | 止损率 |
| take_profit | float | 止盈率 |
| commission | float | 手续费率 |
| slippage | float | 滑点率 |

#### 2.3 绩效指标

| 指标 | 说明 | 状态 |
|------|------|------|
| 总收益率 | 收益/初始资金 | ✅ |
| 夏普比率 | 风险调整后收益 | ✅ |
| 最大回撤 | 最大跌幅 | ✅ |
| 胜率 | 盈利交易占比 | ✅ |
| 盈亏比 | 平均盈利/平均亏损 | ✅ |
| 交易次数 | 总交易数 | ✅ |
| 权益曲线 | 每日权益变化 | ✅ |
| 回撤曲线 | 每日回撤变化 | ✅ |

---

### 3. 交易模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| AUTO (自动) | 全自动执行信号 | 实盘交易 |
| MANUAL (手动) | 全部人工审批 | 保守策略 |
| HYBRID (混合) | 小额自动，大额审批 | 平衡风险 |

---

### 4. 风控引擎

#### 4.1 风控规则

| 规则 | 说明 | 默认值 |
|------|------|--------|
| 持仓数量限制 | 最大持仓币种数 | 10 |
| 持仓价值限制 | 单笔最大价值 | $10,000 |
| 杠杆限制 | 最大杠杆倍数 | 10x |
| 每日亏损限制 | 日亏损比例 | 10% |
| 冷却期 | 交易间隔 | 5分钟 |

#### 4.2 风控检查流程

```
信号生成 → 风险评估 → 审批决策 → 执行交易
    ↓          ↓           ↓           ↓
  事件分析   风险等级    AUTO/MANUAL  交易所下单
```

---

### 5. 信号系统

#### 5.1 信号来源

| 来源 | 说明 | 状态 |
|------|------|------|
| 新闻采集 | RSS/API新闻抓取 | ✅ |
| 社交媒体 | Twitter/Telegram | ✅ |
| 链上数据 | Whale Alert | ✅ |
| ETF数据 | ETF流入/流出 | ✅ |
| 交易员追踪 | 机构持仓变化 | ✅ |
| 宏观数据 | 美联储/CPI | ✅ |

#### 5.2 信号类型

| 类型 | 说明 |
|------|------|
| 事件驱动 | ETF批准、黑客攻击、机构采用 |
| 趋势信号 | 买入/卖出/持有 |
| 风险等级 | LOW / MEDIUM / HIGH / EXTREME |

---

### 6. 配置管理

#### 6.1 新闻源配置

| 配置项 | 说明 |
|--------|------|
| 名称 | 新闻源名称 |
| URL | RSS/API地址 |
| 启用状态 | 是否启用 |
| 类型 | RSS/API/Custom |

#### 6.2 API Keys配置

| 配置项 | 说明 |
|--------|------|
| 交易所 | Binance/OKX |
| API Key | 密钥 |
| API Secret | 密钥 |
| 用途 | 现货/合约 |

#### 6.3 LLM配置

| 配置项 | 说明 |
|--------|------|
| 提供商 | OpenAI/智谱/DeepSeek |
| 模型 | 模型名称 |
| 降级链 | 多级LLM降级 |
| API Key | 密钥 |

---

### 7. 数据投影 (CQRS)

系统采用运行时导向架构，数据投影存储在Redis中：

| 投影类型 | 说明 |
|----------|------|
| Dashboard | 综合大盘数据 |
| 风险状态 | 实时风险指标 |
| 持仓状态 | 当前持仓快照 |
| 订单状态 | 订单追踪 |

---

## 🌐 前端页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 数据大盘 | / | 综合仪表盘 |
| 因子面板 | /factors | 因子配置 |
| Regime状态 | /regime | 市场状态 |
| 风险引擎 | /risk | 风控面板 |
| 决策信号 | /decision | 信号追踪 |
| 权重配置 | /weights | 因子权重 |
| 版本历史 | /versions | 配置变更 |
| 控制中心 | /control | 系统控制 |
| 仓位管理 | /positions | 持仓查看 |
| 实盘交易 | /trading | 交易执行 |
| 设置 | /settings | 系统设置 |
| 数据配置 | /data-config | 新闻源/API Keys |
| 回测 | /backtest | 回测分析 |

---

## 🔌 API 文档

### 基础信息

- 基础URL: `http://localhost:8001/api/v1`
- Swagger: `http://localhost:8001/docs`

### 交易 API

#### 下单
```http
POST /trading/order
Content-Type: application/json

{
  "symbol": "BTC/USDT",
  "side": "buy",
  "quantity": 0.01,
  "exchange": "binance",
  "market_type": "usdt_futures",
  "leverage": 5,
  "stop_loss_pct": 2,
  "take_profit_pct": 5
}
```

#### 获取持仓
```http
GET /trading/positions
```

#### 获取账户
```http
GET /trading/accounts
```

#### 设置杠杆
```http
POST /trading/leverage
{
  "symbol": "BTC/USDT",
  "leverage": 10,
  "exchange": "binance",
  "market_type": "usdt_futures"
}
```

#### 设置止盈止损
```http
POST /trading/stop-loss-take-profit
{
  "symbol": "BTC/USDT",
  "stop_loss_pct": 2,
  "take_profit_pct": 5
}
```

### 回测 API

#### 运行回测
```http
POST /backtest-api/backtest
{
  "config": {
    "symbol": "BTC/USDT",
    "start_date": "2024-01-01",
    "end_date": "2024-06-30",
    "initial_capital": 100000,
    "strategy": "sma_crossover",
    "leverage": 5,
    "stop_loss": 0.02,
    "take_profit": 0.05
  }
}
```

#### 获取回测列表
```http
GET /backtest-api/backtest
```

#### 获取回测详情
```http
GET /backtest-api/backtest/{id}
```

### 配置 API

#### 新闻源管理
```http
GET    /config/news-sources     # 获取列表
GET    /config/news-sources/{id} # 获取单个
POST   /config/news-sources     # 创建
PUT    /config/news-sources/{id} # 更新
DELETE /config/news-sources/{id} # 删除
```

#### API Keys管理
```http
GET    /config/api-keys
POST   /config/api-keys
PUT    /config/api-keys/{id}
DELETE /config/api-keys/{id}
```

---

## 📁 项目结构

```
backend/
├── api/
│   ├── routers/          # API 路由
│   ├── schemas/         # 数据模型
│   └── services/         # 业务服务
├── application/
│   └── services/         # 应用服务
├── config/               # 配置文件
├── domain/               # 领域模型
├── infrastructure/       # 基础设施
│   ├── cache/           # Redis
│   ├── database/        # PostgreSQL
│   ├── messaging/       # Kafka
│   └── websocket/       # WebSocket
├── research/             # 研究模块
│   ├── backtest/        # 回测
│   ├── factor/          # 因子研究
│   └── correlation/     # 相关性分析
├── runtime/             # 运行时
│   ├── signal_runtime/ # 信号运行时
│   └── execution_runtime/ # 执行运行时
├── services/            # 核心服务
│   ├── backtest_service/ # 回测引擎
│   ├── execution_service/ # 执行服务
│   └── data_service/   # 数据服务
└── scripts/            # 脚本工具

frontend/
├── src/
│   ├── pages/           # 页面组件
│   ├── components/      # 通用组件
│   ├── services/       # API服务
│   └── store/          # 状态管理
└── public/
```

---

## 🚀 快速开始

### 1. 启动基础设施
```bash
cd backend/deploy
docker-compose up -d
```

### 2. 启动后端
```bash
cd backend
uvicorn api_server:app --reload --port 8001
```

### 3. 启动前端
```bash
cd frontend
npm run dev
```

### 4. 访问系统
- 前端: http://localhost:3003
- API文档: http://localhost:8001/docs

---

## ⚙️ 环境变量

### 交易所 API Keys
```bash
BINANCE_API_KEY=
BINANCE_API_SECRET=
OKX_API_KEY=
OKX_API_SECRET=
OKX_PASSPHRASE=
```

### LLM API Keys
```bash
ZHIPU_API_KEY=
DEEPSEEK_API_KEY=
BAIDU_API_KEY=
OPENAI_API_KEY=
```

### Redis
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
```

---

## 📊 数据流架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据采集层                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 新闻采集 │ │ 社交媒体 │ │ 链上数据 │ │ 交易所   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │                 │
│       └────────────┴────────────┴────────────┘                 │
│                          │                                     │
│                          ▼                                     │
│                   ┌─────────────┐                              │
│                   │   Kafka    │                              │
│                   └──────┬──────┘                              │
│                          │                                     │
└──────────────────────────┼────────────────────────────────────┘
                           │
┌──────────────────────────┼────────────────────────────────────┐
│                   事件处理层                                    │
│                          ▼                                     │
│  ┌─────────────────────────────────────────────────┐           │
│  │              Signal Runtime                     │           │
│  │  EventDetector → SignalFusion → Decision       │           │
│  └────────────────────────┬────────────────────────┘           │
│                           │                                     │
│  ┌────────────────────────┼────────────────────────────────┐   │
│  │              LLM 增强层 │  (降级链支持)                  │   │
│  └────────────────────────┼────────────────────────────────┘   │
│                           │                                     │
└───────────────────────────┼────────────────────────────────────┘
                            │
┌───────────────────────────┼────────────────────────────────────┐
│                    执行层                                       │
│                           ▼                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │              Execution Runtime                   │           │
│  │   Risk Check → Decision Gate → Exchange Adapter│           │
│  └────────────────────────┬────────────────────────┘           │
│                           │                                     │
│              ┌────────────┼────────────┐                      │
│              ▼            ▼            ▼                      │
│         ┌────────┐  ┌────────┐  ┌────────┐                   │
│         │Binance │  │  OKX   │  │  Mock  │                   │
│         └────────┘  └────────┘  └────────┘                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    存储层                                       │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  Redis   │  │PostgreSQL│  │ ClickHouse│  │   OSS   │     │
│  │ 投影/缓存│  │ 持久化   │  │ 时序数据 │  │ 文件存储│     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔐 安全说明

1. **API Keys 存储**: 使用环境变量，不提交到代码仓库
2. **敏感数据**: API Keys 在存储时自动哈希
3. **降级机制**: LLM 七级降级，确保服务可用性
4. **审批流程**: 混合模式，大额交易需人工审批

---

## 📝 更新日志

### v2.1.0 (2024-05-15)
- ✅ 完整实盘交易系统
- ✅ 回测引擎
- ✅ 多交易所支持 (Binance/OKX)
- ✅ 合约交易 (现货/USDT合约/币本位合约)
- ✅ 杠杆交易 (1-125x)
- ✅ 止盈止损自动执行
- ✅ 前端交易页面
- ✅ 配置管理 (新闻源/API Keys)
- ✅ REST API 完整实现

---

## 📞 支持

如有问题，请查看：
- API文档: http://localhost:8001/docs
- 项目README: /backend/README.md
