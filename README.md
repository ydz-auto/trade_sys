# TradeAgent - AI 量化交易平台

基于 Runtime-Oriented Architecture 的加密货币交易代理平台。

---

## ⚠️ 重要说明

### 关于数据安全

| 环境 | 操作 | 风险 |
|------|------|------|
| **开发环境** | 可以删除数据卷 | 数据丢失可以接受 |
| **生产环境** | **绝对不要删除数据卷** | 数据丢失是灾难 |

#### 删除数据卷的后果

- ❌ **Kafka 历史消息全部丢失**
- ❌ **消费者组偏移量丢失**（需要重新从头消费）
- ❌ **ZooKeeper 元数据丢失**
- ❌ **Redis 缓存和投影数据全部丢失**
- ❌ **系统状态完全重置**

---

## 🚀 快速开始

### 一键启动（推荐）

```bash
# 启动所有服务（包含前端）
./start.sh --mixed

# 查看状态
./start.sh --status

# 查看日志
./start.sh --logs

# 停止服务
./start.sh --stop
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | Vue 开发服务器 |
| API Server | http://localhost:8001 | FastAPI 服务 |
| API Docs | http://localhost:8001/docs | Swagger 文档 |
| Kafka UI | http://localhost:8080 | Kafka 管理界面 |

---

## 🏗️ 架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Frontend                                │
│                          (Vue.js + Vite)                            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            API Server                               │
│                         (FastAPI + Uvicorn)                         │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Signal Runtime  │  │ Projection       │  │ Execution        │
│                  │  │ Runtime          │  │ Runtime          │
└────────┬─────────┘  └────────┬─────────┘  └──────────────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌──────────────────┐
         │    Redis         │
         │  (Projections)   │
         └──────────────────┘
                    ▲
                    │
         ┌──────────────────┐
         │  Ingestion       │
         │  Runtime         │
         │  (Data Source)   │
         └──────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Binance │  │  Bybit  │  │ Coinbase│
│ WebSocket│  │   REST  │  │   REST  │
└─────────┘  └─────────┘  └─────────┘
                    │
                    ▼
         ┌──────────────────┐
         │     Kafka        │
         │  (Event Stream)  │
         └──────────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │    ZooKeeper     │
         └──────────────────┘
```

### 分层架构

```
backend/
├── api/                # API 网关 (Presentation Layer)
├── services/           # 业务逻辑层 (Service Layer)
│   └── data_service/   # 数据收集服务
│       └── collectors/ # 数据收集器（Binance WebSocket）
├── runtime/            # 运行时层 (Runtime Layer)
│   ├── ingestion_runtime/    # 数据摄入
│   ├── signal_runtime/       # 信号生成
│   ├── projection_runtime/   # 状态投影
│   └── execution_runtime/    # 执行下单
├── application/        # 业务用例层 (Application Layer)
├── domain/             # 领域模型层 (Domain Layer)
├── infrastructure/     # 基础设施层 (Infrastructure Layer)
│   └── resilience/     # 弹性基础设施（多通道降级）
├── config/             # 配置治理
├── deploy/             # 部署治理
├── docker/             # Docker 相关
├── docs/               # 文档
└── research/           # 研究层
```

---

## 📋 核心功能

### 多通道数据降级

系统实现了专业的多数据源降级架构：

| 优先级 | 通道 | 类型 | 状态 |
|--------|------|------|------|
| 10 | Binance WebSocket | 实时 | ✅ |
| 20 | Binance REST | 轮询 | ✅ |
| 30 | Bybit REST | 轮询 | ✅ |
| 40 | OKX REST | 轮询 | ⚠️ |
| 50 | Gate.io REST | 轮询 | ⚠️ |
| 60 | Coinbase REST | 轮询 | ✅ |
| 70 | CoinGecko REST | 轮询 | ✅ |

**特点**:
- WebSocket 断开时自动切换到 REST
- 多通道按优先级依次尝试
- Mock 仅用于开发（默认关闭）

### Kafka 自动修复

系统会自动检测并修复 Kafka 集群ID不匹配问题：

```bash
# 启动时自动检测
./dev.sh infra-up

# 步骤 1: 启动 ZooKeeper
# 步骤 2: 检查 Kafka 集群ID问题
# 步骤 3: 清理旧数据卷（如需要）
# 步骤 4: 等待 Kafka 健康状态
```

---

## 🔧 开发指南

### 后端开发

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动基础设施
./dev.sh infra-up

# 启动所有 Runtime
./dev.sh start-all

# 启动单个 Runtime
./dev.sh start ingestion

# 查看日志
./dev.sh logs ingestion

# 停止服务
./dev.sh stop-all
```

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

### 测试多通道数据

```bash
cd backend
python -m scripts.test_data_channels
```

---

## 📚 文档

详细文档请参考 `backend/docs/` 目录：

| 文档 | 说明 |
|------|------|
| [MULTI_CHANNEL_DATAFLOW_FIX_20260516.md](backend/docs/MULTI_CHANNEL_DATAFLOW_FIX_20260516.md) | 多通道数据流修复报告 |
| [KAFKA_REDIS_AUDIT_FIX_20260516.md](backend/docs/KAFKA_REDIS_AUDIT_FIX_20260516.md) | Kafka & Redis 配置审计 |
| [API.md](backend/docs/API.md) | API 文档 |

---

## 🛠️ 常用命令

### 使用根目录脚本

```bash
# 启动混合模式（推荐）
./start.sh --mixed

# 启动仅后端
./start.sh --backend

# 启动仅 Docker
./start.sh --docker

# 查看状态
./start.sh --status

# 查看日志
./start.sh --logs

# 停止所有
./start.sh --stop
```

### 使用后端 dev.sh

```bash
cd backend

# 基础设施
./dev.sh infra-up
./dev.sh infra-down

# Runtime
./dev.sh start-all
./dev.sh stop-all
./dev.sh start ingestion
./dev.sh stop ingestion

# 日志
./dev.sh logs
./dev.sh logs ingestion
```

---

## ✅ 验证系统健康

### 检查服务状态

```bash
# 检查 Docker 容器
docker ps --format "table {{.Names}}\t{{.Status}}"

# 检查 Python 进程
ps aux | grep runtime

# 检查前端
curl -I http://localhost:3000

# 检查 API
curl http://localhost:8001/api/v1/trading/dashboard
```

### 检查日志

```bash
# 查看所有日志
tail -f backend/logs/*.log

# 查看特定日志
tail -f backend/logs/ingestion.log
tail -f backend/logs/signal.log
tail -f backend/logs/projection.log
```

---

## 🐛 故障排除

### Kafka 无法启动（集群ID不匹配）

**问题**: Kafka 日志显示 `InconsistentClusterIdException`

**原因**: ZooKeeper 中存储的集群ID与 Kafka 数据卷中的不一致

**开发环境修复**（⚠️ 会删除所有数据）:
```bash
cd backend
./dev.sh fix-kafka-dev  # 需要输入 YES 确认
```

或手动:
```bash
cd backend/deploy
docker-compose down -v  # ⚠️ 删除所有数据卷！
docker-compose up -d
```

**生产环境**: 请不要删除数据卷，需要通过备份恢复

---

### 没有数据

1. 检查 Ingestion Runtime 日志
2. 验证 Kafka 正在运行
3. 验证多通道数据获取正常

```bash
cd backend
python -m scripts.test_data_channels
```

### 前端无法访问

确认前端是否正在运行：

```bash
ps aux | grep vite

# 如果没有运行，手动启动
cd frontend
npm run dev
```

---

## 📖 参考资料

- [Binance API](https://binance-docs.github.io/apidocs/spot/en/)
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue.js Documentation](https://vuejs.org/)

---

## 📝 最新更新

### 2026-05-16
- ✅ **多通道数据降级架构**: 实现真实数据源链（Binance → Bybit → Coinbase → CoinGecko）
- ✅ **Kafka 自动修复**: 自动检测并修复集群ID不匹配问题
- ✅ **前端自动启动**: `--mixed` 模式现在包含前端
- ✅ **数据为空修复**: Runtime 层正确处理 REST fallback 模式

---

## 📄 License

MIT
