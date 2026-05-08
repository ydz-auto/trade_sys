# TradeAgent 交易系统文档

## 概述

TradeAgent 是一个多资产智能交易信号引擎（Multi-Asset Trading Signal Engine），用于生成可执行的交易决策。

**系统定位**：
- BTC / ETH 现货交易
- BTC / ETH 合约交易（含杠杆）

**核心能力**：
- 市场状态判断（趋势 / 风险）
- 多资产联动分析（BTC + 黄金 + 原油 + ETF + 新闻）
- 输出交易信号（方向 + 仓位 + 杠杆 + 止损止盈）
- 动态风险控制（避免爆仓 / 大回撤）

## 系统输出标准

系统输出必须是"可执行交易指令"：

```json
{
  "symbol": "BTC",
  "action": "OPEN_LONG | OPEN_SHORT | CLOSE | HOLD",
  "position_size": 0.2,
  "leverage": 3,
  "entry_type": "market | limit",
  "stop_loss": 2.0,
  "take_profit": 4.5,
  "confidence": 0.78,
  "risk_level": "low | medium | high"
}
```

## 文档结构

```
交易系统/
├── 00_protocol/          # 通信协议
│   ├── 03_TDP协议设计.md
│   ├── 04_State服务设计.md
│   └── 05_Config服务设计.md
│
├── 01_Core/              # 核心基础设施
│   ├── 01_架构文档.md
│   ├── 01.5_简化架构图.md
│   ├── 01.6_技术选型文档.md
│   └── 02_需求.md
│
├── 02_Trading/           # 核心交易模块
│   ├── 06_因子系统.md
│   ├── 07_风险模型设计.md
│   ├── 07.5_交易系统数据流设计.md
│   ├── 08_仓位引擎设计.md
│   └── 09_决策系统.md
│
├── 03_Advanced/          # 进阶模块
│   ├── 10_Regime引擎设计.md
│   ├── 10.1_regime_service实现方案.md
│   ├── 11_Portfolio风险引擎设计.md
│   ├── 12_信号质量评分设计.md
│   ├── 13_策略版本系统设计.md
│   ├── 14_反馈闭环系统设计.md
│   └── 14.5_MultiAgent架构设计.md
│
├── 04_Execution/         # 执行与验证
│   ├── 15_执行服务设计.md
│   ├── 16_Feature服务设计.md
│   ├── 16.1_feature_service实现方案.md
│   ├── 17_回测系统设计.md
│   ├── 18_回测实盘隔离机制.md
│   └── 19_数据大盘设计.md
│
├── 05_Data/              # 数据层
│   ├── 05_数据采集模块设计.md
│   ├── 05.1_价格数据采集设计.md
│   ├── 05.2_ETF数据采集设计.md
│   ├── 05.4_新闻资讯采集设计.md
│   ├── 05.5_社交媒体采集设计.md
│   ├── 05.5_LLM爬虫技术集成.md
│   ├── 05.6_数据采集全景图.md
│   ├── 05.7_data_service实现方案.md
│   ├── 05.8_交易员数据采集设计.md
│   ├── 05.8_向量数据库设计.md
│   ├── 05.9_链上数据采集设计.md
│   └── 06_Infrastructure/
│
├── 06_Infrastructure/    # 工程基础设施
│   ├── 19_日志系统设计.md
│   ├── 20_监控系统设计.md
│   ├── 21_权限系统设计.md
│   ├── 22_API网关设计.md
│   ├── 23_微服务架构设计.md
│   ├── 24_中间件共享架构设计.md
│   ├── 25_容器化部署设计.md
│   ├── 26_数据库设计.md
│   └── 27_缓存设计.md
│
└── 07_Meta/              # 元文档
    ├── 23_文档结构.md
    ├── 24_设计流程.md
    └── 交易系统.md
```

## 核心模块与功能

### 1. 数据层（Data Layer）

**功能**：
- 多源数据采集（交易所、ETF网站、新闻源）
- 数据清洗与时间对齐
- 数据质量控制
- TDP协议标准化

**支持资产**：
| 类型 | 资产 |
|------|------|
| Crypto | BTC, ETH |
| Commodities | Gold（黄金）, Oil（原油） |
| ETF | BTC ETF资金流 |
| News | 宏观 / 地缘 / 加密行业 |

**时间粒度**：1m / 5m / 1h / 1d（可配置）

### 2. 特征层（Feature Layer）

**输出特征**：
- returns（收益率）
- volatility（波动率）
- momentum（动量）
- ETF资金变化
- 新闻情绪

### 3. 因子层（Factor Layer）

**核心因子**：

| 因子 | 作用 | 类型 |
|------|------|------|
| Trend | 市场方向 | Quant |
| Flow | 资金行为 | Quant |
| Sentiment | 情绪 | Semantic（LLM） |
| Macro | 宏观 | Quant |
| Behavioral | 交易员行为 | Quant |
| Historical | 历史相似度 | Context |

**因子融合**：
```
composite_score = Σ (factor_i × weight_i)
```

**推荐权重**：
```json
{
  "trend": 0.3,
  "flow": 0.25,
  "sentiment": 0.2,
  "macro": 0.15,
  "behavioral": 0.1,
  "historical": 0.05
}
```

### 4. 市场状态（Regime Engine）

**状态识别**：
- RISK_ON：趋势向上 + 资金流入 + 情绪正向
- RISK_OFF：情绪负面 + 宏观下行 + 趋势向下
- NEUTRAL：其他情况

**判断规则**：
```
RISK_ON:  trend > 0 && flow > 0 && sentiment > 0
RISK_OFF: sentiment < -0.5 && macro < 0 && trend < 0
```

### 5. 风险引擎（Risk Engine）

**核心问题**：判断"现在能不能交易？能的话，风险有多大？"

**风险来源（分层）**：

| 风险类型 | 输入 | 说明 |
|----------|------|------|
| 波动风险 | ATR、实际波动率 | 高波动 → 高风险 |
| 资金风险 | ETF资金流 | 持续流出 → 高风险 |
| 情绪风险 | 新闻情绪（LLM） | 极端负面 → 风险上升 |
| 宏观风险 | 黄金、原油 | 同步上涨 → 风险上升 |
| 行为风险 | 多空比、爆仓数据 | 散户极端一致 → 高风险 |
| 组合风险 | 当前仓位、杠杆 | 仓位越重 → 风险越高 |

**风险指数计算**：
```
risk_index = w1×vol_risk + w2×flow_risk + w3×sentiment_risk + w4×macro_risk + w5×behavioral_risk + w6×portfolio_risk
```

**风险等级**：
| 范围 | 等级 | 交易限制 |
|------|------|----------|
| 0-30 | LOW | 正常交易 |
| 30-60 | MEDIUM | 仓位受限 |
| 60-80 | HIGH | 降低杠杆 |
| 80-100 | EXTREME | 禁止开仓 |

**风控硬规则**：
- 单资产仓位 ≤ 30%
- 总仓位 ≤ 50%
- 每单必须设置止损
- 最大回撤 > 10% → 停止交易

### 6. 决策引擎（Decision Engine）

**输入**：因子评分 + 风险指数 + 市场状态

**输出**：BUY / SELL / HOLD + 置信度

**组成**：
- 规则模型（主）
- LLM（解释 + 优化）

### 7. 仓位引擎（Position Engine）

**输入**：
- 信号（方向 / 置信度）
- 风险指数
- 当前仓位
- 市场波动（ATR）

**核心计算**：

| 步骤 | 公式 |
|------|------|
| 基础仓位 | base_size = confidence × max_position |
| 风险调整 | adjusted_size = base_size × (1 - risk_index/100) |
| 波动调整 | final_size = adjusted_size × (target_vol / atr) |

**杠杆规则**：
```
risk_index > 70 → leverage = 1
confidence > 0.8 → leverage = 3
else → leverage = 2
```

**止损止盈**：
```
stop_loss = entry_price × (1 - k × atr)  # k = 1.5~2
take_profit = stop_loss × RR  # RR = 2~3
```

### 8. 执行引擎（Execution Engine）

**功能**：
- 模拟执行（回测/模拟盘）
- 实盘订单隔离执行
- 订单状态跟踪
- 对接 Binance / OKX 交易所

**风控约束**：
- 无止损 → 不允许下单
- 高风险禁止开仓

### 9. 反馈闭环（Feedback Loop）

**四大反馈机制**：

| 反馈类型 | 说明 | 影响 |
|----------|------|------|
| PnL Feedback | 连续亏损 → 降低仓位 | 立即影响仓位 |
| Risk Feedback | 高风险低回报 → 收紧风险 | 调整风险参数 |
| Signal Feedback | B级信号不准 → 提高门槛 | 调整质量阈值 |
| Regime Feedback | Regime预测不准 → 调整权重 | 调整策略权重 |

**反馈规则**：
| 触发条件 | 响应动作 |
|----------|----------|
| 连续亏损3次 | 降低仓位50% |
| 连续亏损5次 | 降低仓位70% |
| 单日亏损5% | 停止交易 |
| 回撤10% | 紧急止损 |
| B级信号准确率<40% | 提高质量阈值 |

### 10. 组合风险管理（Portfolio Risk）

**功能**：
- 多资产（BTC/ETH）相关性分析
- 组合敞口计算
- 多样化分析
- 动态资产配置

### 11. 系统控制（Control Service）

**控制指令**：
| 指令 | 说明 |
|------|------|
| PAUSE_ALL | 暂停所有交易 |
| RESUME_ALL | 恢复所有交易 |
| EMERGENCY_EXIT | 紧急平仓所有仓位 |
| REDUCE_RISK | 降低风险敞口 |
| CIRCUIT_BREAK | 熔断（基于波动率/流动性） |

**触发条件**：
```
单日亏损 > 5% → PAUSE_ALL
回撤 > 10% → EMERGENCY_EXIT
波动率 > 3x均值 → CIRCUIT_BREAK
连续亏损 > 5次 → 降低仓位70%
```

## 系统运行节奏

| 模块 | 频率 |
|------|------|
| 价格 | 实时 |
| 决策 | 每5-15分钟 |
| ETF | 每日 |
| 新闻 | 实时/分钟级 |

## 系统模式

| 模式 | 说明 |
|------|------|
| 建议 | 人工执行 |
| 半自动（推荐） | 人工确认 |
| 自动 | 系统执行 |

## 技术栈

### 前端

| 模块/功能 | 技术选型 |
|-----------|----------|
| 核心框架 | React 18+ |
| 状态管理 | Redux Toolkit |
| UI 组件库 | Ant Design |
| 样式 | Tailwind CSS（可选） |
| 数据可视化 | ECharts / Recharts |
| 实时数据 | WebSocket |
| 路由 | React Router |
| 构建工具 | Vite / Webpack |

### 后端

| 模块/功能 | 技术选型 |
|-----------|----------|
| 核心语言 | Python 3.10+ |
| 高性能模块 | C++（可选） |
| 数据处理 | Pandas / NumPy |
| 异步任务 | Celery / Asyncio |
| API 框架 | FastAPI / Flask |
| 消息队列 | Kafka / RabbitMQ |
| 交易接口 | CCXT / 官方交易所 API |
| 回测框架 | backtrader / zipline |

### 数据库与存储

| 类型 | 技术选型 |
|------|----------|
| 关系型数据库 | PostgreSQL |
| 列式数据库 | ClickHouse |
| 缓存 | Redis |
| 时序数据库 | InfluxDB |
| 对象存储 | MinIO / 本地存储 |

### 基础设施

| 模块 | 技术选型 |
|------|----------|
| 容器化 | Docker |
| 编排 | Kubernetes（可选） |
| 日志收集 | ELK Stack |
| 监控 | Prometheus + Grafana |
| CI/CD | GitHub Actions / GitLab CI |
| 证书/安全 | Let's Encrypt |

## 微服务列表（18个）

| 服务 | 功能 | 数据库/存储 |
|------|------|-------------|
| **api-gateway** | 前端统一接口、路由、负载均衡 | - |
| **auth_service** | 用户认证、KYC、权限管理 | PostgreSQL |
| **data_service** | 数据采集 + ETL（行情、ETF、新闻、宏观） | ClickHouse / Redis |
| **feature_service** | 特征计算（收益率、波动率、动量、资金流、情绪） | ClickHouse |
| **factor_service** | 因子计算（Trend、Flow、Sentiment、Macro、Behavioral） | ClickHouse |
| **regime_service** | 市场状态判断、趋势识别 | ClickHouse / Redis |
| **risk_service** | 风险指数计算、杠杆控制、止损止盈 | PostgreSQL / Redis |
| **portfolio_service** | 组合风险管理、相关性分析 | PostgreSQL / Redis |
| **decision_service** | 决策引擎、多资产交易逻辑、信号输出 | PostgreSQL / Redis |
| **position_service** | 仓位计算、动态调整 | PostgreSQL / Redis |
| **execution_service** | 模拟执行 / 实盘下单隔离 | PostgreSQL / Redis |
| **llm_service** | LLM 情绪分析、爬虫增强、策略解释 | Redis |
| **feedback_service** | 反馈闭环、PnL分析、策略调整 | PostgreSQL / ClickHouse |
| **state_service** | 全局状态管理（仓位/账户/风险/策略状态） | Redis / PostgreSQL |
| **config_service** | 配置中心、因子权重、风险参数、版本管理 | PostgreSQL |
| **monitor_service** | 系统监控、健康检查、告警 | Redis |
| **notification_service** | 邮件/短信/推送通知 | Redis |
| **control_service** | 系统控制、暂停/恢复/紧急止损 | Redis / PostgreSQL |

## 数据流

```
市场数据 → Data Service → TDP标准化 → Feature Service → Factor Engine
    ↓
Regime Engine（判断市场状态）
    ↓
Risk Engine（计算风险）
    ↓
Decision Engine（给出买卖决策）
    ↓
Position Engine（算仓位/杠杆）
    ↓
Execution（真实下单）
    ↓
PnL 追踪 → Feedback Loop → 调整 Risk / Decision
```

## 相关文档

- [架构文档](01_Core/01_架构文档.md)
- [技术选型文档](01_Core/01.6_技术选型文档.md)
- [微服务架构设计](06_Infrastructure/23_微服务架构设计.md)
- [因子系统](02_Trading/06_因子系统.md)
- [仓位引擎设计](02_Trading/08_仓位引擎设计.md)
- [风险模型设计](02_Trading/07_风险模型设计.md)
- [决策系统](02_Trading/09_决策系统.md)
- [反馈闭环系统](03_Advanced/14_反馈闭环系统设计.md)
