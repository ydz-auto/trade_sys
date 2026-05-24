# Execution Runtime 启动失败修复

**日期**: 2026-05-16  
**问题级别**: Critical  
**影响范围**: execution-runtime 及所有依赖 Kafka 的 runtime 服务

---

## 问题描述

### 错误信息

```
2026-05-16 01:39:15 ERROR [consumer.execution-runtime] ❌ Start attempt 10 failed: 
AIOKafkaConsumer.__init__() got an unexpected keyword argument 'api_version'

2026-05-16 01:39:15 ERROR [execution_runtime] Runtime error: Failed to start consumer after 10 attempts
```

### 影响服务

- execution-runtime
- ingestion-runtime
- signal-runtime
- projection-runtime
- 所有使用 `RuntimeConsumer` 的服务

---

## 根本原因分析

### 1. 代码版本不一致

Docker 容器中的代码是构建时复制的旧版本，而本地代码已更新。

**容器路径**: `/app/runtime/shared/consumer.py`  
**本地路径**: `/Users/yangdezeng/.../backend/runtime/shared/consumer.py`

### 2. aiokafka API 变更

旧版本代码使用了 `api_version` 参数：

```python
# 旧代码（容器中）
self._consumer = AIOKafkaConsumer(
    ...
    api_version='auto',  # 此参数在新版已移除
)
```

新版 `aiokafka>=0.10.0` 已移除 `api_version` 参数，导致初始化失败。

### 3. Docker 构建机制

Dockerfile 使用 `COPY` 指令复制代码，没有挂载本地卷：

```dockerfile
FROM quant-base AS runtime-base
COPY runtime/ ./runtime/
```

这意味着只有重新构建镜像才能更新容器中的代码。

---

## 解决方案

### 步骤 1: 重新构建 Docker 镜像

```bash
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/deploy
./start.sh restart
```

或手动执行：

```bash
docker compose build --no-cache
docker compose up -d
```

### 步骤 2: 清理 Kafka 数据卷（如遇到集群 ID 不匹配）

如果 Kafka 启动失败并出现以下错误：

```
InconsistentClusterIdException: The Cluster ID doesn't match stored clusterId in meta.properties
```

执行：

```bash
docker compose down -v
docker volume rm deploy_kafka_data deploy_zookeeper_data
docker compose up -d
```

### 步骤 3: 验证服务状态

```bash
docker compose ps
docker compose logs execution-runtime --tail 30
```

预期输出：

```
✅ Consumer started successfully: ['tradeagent.decisions']
Execution Runtime initialized successfully
Runtime state changed: running
```

---

## 验证结果

### 修复前

```
❌ Start attempt 10 failed: AIOKafkaConsumer.__init__() got an unexpected keyword argument 'api_version'
Runtime error: Failed to start consumer after 10 attempts
```

### 修复后

```
✅ Consumer started successfully: ['tradeagent.decisions']
Publisher started: tradeagent.orders
Execution engine initialized
Order manager initialized
Risk engine initialized
Execution Runtime initialized successfully
Runtime state changed: running
```

---

## 预防措施

### 1. 开发环境使用卷挂载

修改 `docker-compose.yml` 添加开发模式卷挂载：

```yaml
services:
  execution-runtime:
    volumes:
      - ../runtime:/app/runtime:ro  # 开发模式
    environment:
      - DEV_MODE=true
```

### 2. 添加版本检查

在 `requirements.txt` 中锁定 aiokafka 版本：

```
aiokafka>=0.10.0,<1.0.0
```

### 3. 添加启动前检查

在 `RuntimeConsumer.start()` 中添加参数验证：

```python
import inspect

async def start(self) -> None:
    # 检查 AIOKafkaConsumer 支持的参数
    sig = inspect.signature(AIOKafkaConsumer.__init__)
    supported_params = sig.parameters.keys()
    
    # 过滤不支持的参数
    config = {...}  # 配置字典
    valid_config = {k: v for k, v in config.items() if k in supported_params}
    
    self._consumer = AIOKafkaConsumer(**valid_config)
```

---

## 相关文件

- `backend/runtime/shared/consumer.py` - Kafka 消费者实现
- `backend/docker/Dockerfile` - Docker 镜像构建
- `backend/deploy/docker-compose.yml` - 服务编排
- `backend/requirements.txt` - Python 依赖

---

## 参考资料

- [aiokafka 文档](https://aiokafka.readthedocs.io/)
- [aiokafka 更新日志](https://github.com/aio-libs/aiokafka/blob/main/CHANGES.rst)
