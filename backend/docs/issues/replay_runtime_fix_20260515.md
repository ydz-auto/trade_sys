# Replay Service 重构记录

## 问题概述

`replay-runtime` 服务设计不合理：回放任务是一次性任务，不应该作为长期运行的 Runtime，也不需要单独部署微服务。

---

## 架构问题：Runtime vs Service vs API Endpoint

### 问题描述
1. `replay-runtime` 完成回放任务后就停止了，这不符合 Runtime 的设计理念
2. 回放服务不需要单独部署微服务，可以作为 API Server 的一个端点

### 架构对比

| 类型 | 特点 | 示例 |
|------|------|------|
| **Runtime** | 长期运行的进程，持续处理数据流 | ingestion, signal, execution, projection |
| **Service** | 按需调用，后台任务 | backtest, repair |
| **API Endpoint** | HTTP 请求触发，无需独立部署 | replay |

### 解决方案
将回放功能集成到 `api-server` 中，作为 REST API 端点提供。

---

## 最终架构

```
api/
  routers/
    replay.py           # REST API 端点
  services/
    replay_service.py   # 服务逻辑
  schemas/
    replay.py           # 数据模型
```

---

## REST API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/replay` | POST | 创建回放任务 |
| `/replay/{id}` | GET | 获取回放状态 |
| `/replay` | GET | 列出所有回放任务 |
| `/replay/{id}` | DELETE | 取消回放任务 |
| `/replay/{id}/delete` | DELETE | 删除回放记录 |

---

## 使用示例

### 创建回放任务

```bash
curl -X POST http://localhost:8000/replay \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "2024-01-01T00:00:00",
    "end_time": "2024-01-02T00:00:00",
    "mode": "fast",
    "symbols": ["BTCUSDT"]
  }'
```

### 查询回放状态

```bash
curl http://localhost:8000/replay/{replay_id}
```

### 列出所有回放任务

```bash
curl http://localhost:8000/replay
```

### 取消回放任务

```bash
curl -X DELETE http://localhost:8000/replay/{replay_id}
```

---

## 修改文件汇总

| 文件 | 操作 | 描述 |
|------|------|------|
| `api/routers/replay.py` | 新建 | REST API 端点 |
| `api/services/replay_service.py` | 新建 | 服务逻辑 |
| `api/schemas/replay.py` | 新建 | 数据模型 |
| `api/routers/__init__.py` | 修改 | 添加 replay router |
| `deploy/docker-compose.yml` | 修改 | 删除 replay-service |
| `docker/Dockerfile` | 修改 | 删除 replay-service target |
| `runtime/replay_runtime/` | 删除 | 旧目录已删除 |
| `services/replay_service/` | 删除 | 独立服务已删除 |

---

## 验证

```bash
# 启动 API Server
cd /Users/yangdezeng/00_crypto/00_trade_agent/20260506/backend/deploy
docker-compose up -d api-server

# 测试回放 API
curl http://localhost:8000/replay \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"start_time": "2024-01-01T00:00:00", "end_time": "2024-01-02T00:00:00"}'
```

---

## 其他已修复问题

### 问题 1: ClickHouseManager.fetch() 不支持参数化查询

**错误信息**
```
TypeError: ClickHouseManager.fetch() takes 2 positional arguments but 3 were given
```

**解决方案**
修改 `ClickHouseClient.fetch()` 和 `ClickHouseManager.fetch()` 方法，添加 `params` 参数。

**相关文件**
- `infrastructure/database/clickhouse.py`

---

### 问题 2: 缺少 clickhouse-driver 依赖

**错误信息**
```
ModuleNotFoundError: No module named 'clickhouse_driver'
```

**解决方案**
在 `requirements.txt` 中添加 `clickhouse-driver>=0.2.6`。

**相关文件**
- `requirements.txt`

---

### 问题 3: ClickHouse 配置不从环境变量读取

**错误信息**
```
Connection refused (localhost:9000)
```

**解决方案**
修改 `shared/config/defaults/infrastructure/database.py`，从环境变量读取配置。

**相关文件**
- `shared/config/defaults/infrastructure/database.py`

---

### 问题 4: ClickHouse 只允许本地连接

**错误信息**
```
Code: 516. DB::Exception: Authentication failed
```

**解决方案**
创建 `deploy/clickhouse/users.xml` 允许远程连接。

**相关文件**
- `deploy/clickhouse/users.xml`

---

### 问题 5: 物化视图 SQL 嵌套聚合函数错误

**错误信息**
```
Code: 184. DB::Exception: Aggregate function sum(volume) AS volume is found inside another aggregate function
```

**解决方案**
使用子查询将聚合计算与别名定义分离。

**相关文件**
- `infrastructure/data_lake/schemas.py`
