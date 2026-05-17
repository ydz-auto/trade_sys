# =============================================================================
# TradeAgent README
# =============================================================================

# TradeAgent - AI 量化交易平台

基于 Runtime-Oriented Architecture 的加密货币交易代理平台。

## 快速开始

```bash
# 启动所有服务
make start

# 查看状态
make status

# 查看日志
make logs-follow
```

## 架构

```
services/   → 业务逻辑（信号融合、风控规则、策略决策）
runtime/    → 运行时编排（Kafka 消费、重试、指标）
application/ → 业务用例编排
config/     → 配置治理
deploy/     → 部署治理
```

## 目录结构

```
backend/
├── api/                # API 网关
├── services/           # 业务逻辑层
├── runtime/            # 运行时层
├── application/        # 业务用例层
├── domain/             # 领域模型层
├── infrastructure/     # 基础设施层
├── config/             # 配置治理
├── deploy/             # 部署治理
└── research/           # 研究层
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `make start` | 启动所有服务 |
| `make stop` | 停止所有服务 |
| `make build` | 构建镜像 |
| `make logs` | 查看日志 |
| `make status` | 查看状态 |

## 访问地址

| 服务 | 地址 |
|---|---|
| Kafka UI | http://localhost:8080 |
| Grafana | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |

## 文档

- [架构文档](doc/系统治理/ARCHITECTURE_V5.md)
- [部署指南](docker/DEPLOYMENT.md)
- [服务职责映射](doc/系统治理/SERVICES_RESPONSIBILITY_MAPPING.md)

## 开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行单个 Runtime
python -m runtime.signal_runtime

# 运行测试
pytest tests/
```

## License

MIT
