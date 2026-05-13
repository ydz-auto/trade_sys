# 快速开始指南

本文档帮助你快速启动完整的交易系统。

## 目录

1. [系统要求](#系统要求)
2. [环境配置](#环境配置)
3. [快速启动](#快速启动)
4. [完整流程模拟](#完整流程模拟)

## 系统要求

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- ClickHouse 23+
- Kafka 3.4+

## 环境配置

### 1. 复制配置文件

```bash
cd backend
cp .env.example .env
```

### 2. 配置密钥

**生成强密钥：**
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

**编辑 `.env`：**
```env
ENV=development
JWT_SECRET_KEY=这里放你的强密钥
ALLOW_DEFAULT_ADMIN=false  # 生产环境必须为 false
```

### 3. 配置数据库连接

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=tradeagent
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=你的密码

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DATABASE=tradeagent
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=
```

## 快速启动

### 启动基础设施

**Docker（推荐）：**
```bash
cd infra
docker-compose up -d
```

**本地安装：**
分别启动 PostgreSQL、Redis、ClickHouse、Kafka。

### 运行完整模拟流程

```bash
cd backend
python -m scripts.simulate_pipeline
```

这个脚本会：
1. 模拟信号产生
2. 运行策略决策
3. 执行风控检查
4. 模拟订单执行
5. 显示完整流程和结果

### 逐个启动服务

```bash
# 窗口 1: Data Service
cd backend && python -m services.data_service.main

# 窗口 2: Event Service
cd backend && python -m services.event_service.main

# 窗口 3: Fusion Service
cd backend && python -m services.fusion_service.main_kafka

# 窗口 4: Strategy Service
cd backend && python -m services.strategy_service.main_kafka

# 窗口 5: Risk Service
cd backend && python -m services.risk_service.main_kafka

# 窗口 6: Execution Service
cd backend && python -m services.execution_service.main_kafka
```

## 完整流程模拟

运行模拟脚本：
```bash
cd backend
python -m scripts.simulate_pipeline
```

示例输出：
```
======================================================================
完整交易流程模拟
======================================================================

[1] 产生信号...
✅ 信号: BTC_BULLISH (bullish, 0.85)

[2] 策略决策...
✅ 决策: LONG BTCUSDT (0.01)

[3] 风控检查...
✅ 风控: LOW RISK - 批准

[4] 订单执行...
✅ 订单: LONG BTCUSDT @ 50,000.00 (0.01)
   订单 ID: test_order_001

======================================================================
流程完成!
======================================================================
```

## 下一步

1. 阅读 `docs/ARCHITECTURE_COMPLETION.md` 了解完整架构
2. 运行集成测试：`python -m tests.integration.test_pipeline`
3. 查看策略：`services/strategy_service/strategies.py`
4. 配置实时交易（谨慎操作！）
