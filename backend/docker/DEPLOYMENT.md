# TradeAgent 部署指南

**更新日期**: 2026-05-14

---

## 快速开始

```bash
# 进入部署目录
cd backend/docker

# 启动所有服务
./start.sh

# 查看服务状态
docker-compose ps

# 查看日志
./logs.sh -f signal
```

---

## 部署脚本

| 脚本 | 用途 |
|---|---|
| `start.sh` | 启动服务 |
| `stop.sh` | 停止服务 |
| `build.sh` | 构建镜像 |
| `logs.sh` | 查看日志 |

---

## start.sh 用法

```bash
# 启动所有服务
./start.sh

# 只启动基础设施
./start.sh infra

# 只启动 Runtime 服务
./start.sh runtimes

# 开发模式（前台运行）
./start.sh dev

# 查看状态
./start.sh status
```

---

## stop.sh 用法

```bash
# 停止所有服务
./stop.sh

# 只停止 Runtime 服务
./stop.sh runtimes

# 停止并清理数据卷
./stop.sh clean
```

---

## build.sh 用法

```bash
# 构建所有镜像
./build.sh

# 只构建基础镜像
./build.sh base

# 只构建运行时镜像
./build.sh runtimes

# 不使用缓存
./build.sh --no-cache
```

---

## Docker 镜像架构

### 三层镜像架构 (推荐)

使用 `docker/Dockerfile` 构建的镜像：

```
Layer 1: quant-base       # Python + 常用库 + Telemetry
Layer 2: runtime-base     # 应用代码
Layer 3: runtime-entry    # 仅 CMD
```

构建命令：
```bash
# 构建基础镜像
docker build -f docker/Dockerfile --target quant-base -t quant-base:latest .

# 构建运行时基础镜像
docker build -f docker/Dockerfile --target runtime-base -t runtime-base:latest .

# 构建特定运行时镜像
docker build -f docker/Dockerfile --target ingestion-runtime -t ingestion-runtime:latest .
docker build -f docker/Dockerfile --target signal-runtime -t signal-runtime:latest .
```

### 服务镜像架构 (遗留)

使用 `docker/Dockerfile.services` 构建的镜像：

```bash
# 构建数据服务
docker build -f docker/Dockerfile.services --target data-service -t data-service:latest .

# 构建事件服务
docker build -f docker/Dockerfile.services --target event-service -t event-service:latest .

# 构建融合服务
docker build -f docker/Dockerfile.services --target fusion-service -t fusion-service:latest .

# 构建 LLM 服务
docker build -f docker/Dockerfile.services --target llm-service -t llm-service:latest .

# 构建策略服务
docker build -f docker/Dockerfile.services --target strategy-service -t strategy-service:latest .

# 构建相关性分析服务
docker build -f docker/Dockerfile.services --target correlation-service -t correlation-service:latest .
```

**注意**: 推荐使用三层镜像架构构建 runtime 镜像，服务镜像架构仅用于向后兼容。

---

## logs.sh 用法

```bash
# 查看所有服务日志
./logs.sh

# 查看指定服务日志
./logs.sh signal
./logs.sh execution
./logs.sh api

# 实时查看日志
./logs.sh -f signal
```

---

## 服务清单

### 基础设施服务

| 服务 | 端口 | 说明 |
|---|---|---|
| `zookeeper` | 2181 | Kafka 依赖 |
| `kafka` | 9092 | 消息队列 |
| `kafka-ui` | 8080 | Kafka 管理界面 |
| `redis` | 6379 | 缓存 |
| `clickhouse` | 9000/8123 | 时序数据库 |
| `postgres` | 5432 | 关系数据库 |
| `prometheus` | 9090 | 指标收集 |
| `grafana` | 3000 | 可视化面板 |
| `tempo` | 4317 | 链路追踪 |

### Runtime 服务

| 服务 | 说明 |
|---|---|
| `ingestion-runtime` | 数据采集运行时 |
| `signal-runtime` | 信号生成运行时 |
| `execution-runtime` | 订单执行运行时 |
| `projection-runtime` | CQRS 投影运行时 |
| `correlation-runtime` | 相关性分析运行时 |
| `api-server` | API 网关 |

---

## 访问地址

| 服务 | 地址 |
|---|---|
| **Kafka UI** | http://localhost:8080 |
| **Grafana** | http://localhost:3000 (admin/admin) |
| **Prometheus** | http://localhost:9090 |
| **API Server** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

---

## 分阶段部署

### 阶段 1：基础设施

```bash
./start.sh infra
```

等待 Kafka 健康检查通过后，可以访问 Kafka UI。

### 阶段 2：Runtime 服务

```bash
./start.sh runtimes
```

### 阶段 3：验证

```bash
# 检查服务状态
docker-compose ps

# 检查 API
curl http://localhost:8000/health

# 查看日志
./logs.sh -f signal
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ENVIRONMENT` | dev | 环境名称 |
| `KAFKA_BOOTSTRAP_SERVERS` | kafka:29092 | Kafka 地址 |
| `REDIS_URL` | redis://redis:6379/0 | Redis 地址 |
| `CLICKHOUSE_HOST` | clickhouse | ClickHouse 地址 |
| `CONFIG_DIR` | /app/config | 配置目录 |

---

## Docker Compose 命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart signal-runtime

# 查看日志
docker-compose logs -f signal-runtime

# 进入容器
docker-compose exec signal-runtime /bin/bash

# 查看资源使用
docker-compose top
```

---

## 故障排查

### Kafka 连接失败

```bash
# 检查 Kafka 状态
docker-compose ps kafka

# 查看 Kafka 日志
docker-compose logs kafka

# 重启 Kafka
docker-compose restart kafka
```

### 服务无法启动

```bash
# 查看服务日志
./logs.sh signal

# 重新构建镜像
./build.sh --no-cache

# 重启服务
docker-compose restart signal-runtime
```

### 清理并重新部署

```bash
# 停止所有服务
./stop.sh clean

# 重新构建
./build.sh --no-cache

# 启动
./start.sh
```

---

## 生产环境部署

### 1. 修改配置

```bash
# 复制生产环境配置
cp config/environments/prod.yaml.example config/environments/prod.yaml

# 编辑配置
vim config/environments/prod.yaml
```

### 2. 设置环境变量

```bash
export ENVIRONMENT=prod
export KAFKA_BOOTSTRAP_SERVERS=your-kafka:9092
export REDIS_URL=redis://your-redis:6379/0
```

### 3. 启动服务

```bash
./start.sh
```

---

## 监控

### Prometheus

访问 http://localhost:9090 查看指标。

### Grafana

1. 访问 http://localhost:3000
2. 登录 (admin/admin)
3. 添加 Prometheus 数据源
4. 导入仪表盘

---

## 注意事项

1. **首次启动**需要等待 Kafka 健康检查通过
2. **数据持久化**在 Docker volumes 中
3. **配置文件**在 `backend/config/` 目录
4. **日志文件**在容器内 `/app/logs/` 目录

---

*文档版本: v1.0*
