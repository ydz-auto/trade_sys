# Kafka & Redis 配置审计与修复报告

**日期**: 2026-05-16  
**版本**: 1.0  
**状态**: 已完成

---

## 📊 审计概览

| 类别 | 发现问题数 | 严重 | 高 | 中 | 低 |
|------|-----------|------|---|---|---|
| **Kafka** | 15 | 2 | 5 | 5 | 3 |
| **Redis** | 12 | 4 | 3 | 3 | 2 |
| **总计** | **27** | **6** | **8** | **8** | **5** |

---

## 🚨 严重问题 (已修复)

### 1. Redis 无安全配置

**问题描述**: Redis 容器没有配置内存限制、持久化和健康检查。

**影响**: 
- 可能导致 Redis OOM
- 重启后数据丢失
- 无法监控健康状态

**修复方案**:

```yaml
# deploy/docker-compose.yml
redis:
  image: redis:7-alpine
  command: >
    redis-server
    --maxmemory 2gb
    --maxmemory-policy allkeys-lru
    --save 60 1000
    --appendonly yes
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
```

**修复文件**: `deploy/docker-compose.yml`

---

### 2. 使用 KEYS 命令

**问题描述**: `delete_pattern` 方法使用 `KEYS` 命令，在生产环境会阻塞 Redis。

**影响**: 
- KEYS 是 O(N) 操作，会阻塞 Redis 主线程
- 大量 key 时可能导致服务不可用

**修复方案**:

```python
# infrastructure/cache/redis_client.py
async def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
    """使用 SCAN 替代 KEYS，避免阻塞"""
    deleted = 0
    cursor = 0
    while True:
        cursor, keys = await self.client.scan(cursor, match=pattern, count=batch_size)
        if keys:
            deleted += await self.client.delete(*keys)
        if cursor == 0:
            break
    return deleted
```

**修复文件**: `infrastructure/cache/redis_client.py`

---

### 3. CacheManager 内存缓存无限制

**问题描述**: `_memory_cache` 字典无大小限制，可能导致应用 OOM。

**影响**: 
- 内存持续增长
- 可能导致应用崩溃

**修复方案**:

```python
# infrastructure/cache/cache_manager.py
class LRUMemoryCache:
    """LRU 内存缓存，自动淘汰最少使用的条目"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size

    def set(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)  # 淘汰最旧的
```

**修复文件**: `infrastructure/cache/cache_manager.py`

---

### 4. Topic 定义混乱

**问题描述**: 存在两套 Topic 定义系统，代码中大量硬编码。

**影响**: 
- 维护困难
- 容易出错
- Topic 名称不一致

**修复方案**:

统一使用 `infrastructure/messaging/topics.py` 中的 `Topics` 类：

```python
from infrastructure.messaging import Topics

# ✅ 正确
await producer.publish(Topics.EVENTS, message)

# ❌ 禁止
await producer.publish("tradeagent.events", message)
```

**修复文件**: 
- `infrastructure/messaging/topics.py` - 添加缺失的 Topic
- `shared/config/defaults/infrastructure/middleware.py` - 引用 Topics 类

---

### 5. 配置来源分散

**问题描述**: Kafka 配置定义在 6 个不同位置，Redis 配置定义在 3 个位置。

**影响**: 
- 配置不一致
- 维护困难
- 难以追踪问题

**修复方案**:

创建统一的配置文件 `infrastructure/messaging/kafka_config.py`：

```python
@dataclass
class KafkaConsumerConfig:
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000
    max_poll_records: int = 500
    max_poll_interval_ms: int = 300000
    enable_auto_commit: bool = True
    auto_offset_reset: str = "latest"
    request_timeout_ms: int = 40000
    retry_attempts: int = 10
    retry_delay_ms: int = 3000

@dataclass
class KafkaProducerConfig:
    acks: str = "all"
    retries: int = 3
    batch_size: int = 16384
    linger_ms: int = 5
    compression_type: str = "lz4"  # 新增压缩
    max_in_flight_requests_per_connection: int = 5
```

**修复文件**: `infrastructure/messaging/kafka_config.py` (新建)

---

### 6. Consumer Group ID 不统一

**问题描述**: Consumer Group ID 在多处硬编码，命名不规范。

**影响**: 
- 难以追踪消费者
- 监控困难

**修复方案**:

```python
# infrastructure/messaging/kafka_config.py
class ConsumerGroup:
    """Consumer Group ID 命名规范
    
    格式: tradeagent-{runtime_name}
    """
    NAMESPACE = "tradeagent"
    
    SIGNAL_RUNTIME = "tradeagent-signal"
    EXECUTION_RUNTIME = "tradeagent-execution"
    PROJECTION_RUNTIME = "tradeagent-projection"
    INGESTION_RUNTIME = "tradeagent-ingestion"
    # ...
```

**使用方式**:

```python
from infrastructure.messaging.kafka_config import ConsumerGroup

self.consumer = RuntimeConsumer(ConsumerConfig(
    topics=[Topics.EVENTS],
    group_id=ConsumerGroup.SIGNAL_RUNTIME,  # ✅ 统一命名
))
```

---

## ⚠️ 高优先级问题 (已修复)

### 7. Kafka Consumer 配置不一致

**修复前**:

| 配置项 | infra.yaml | runtime/consumer.py |
|--------|-----------|---------------------|
| `session_timeout_ms` | 30000 | 10000 |
| `max_poll_records` | 1000 | 100 |

**修复后**: 统一使用 `DEFAULT_CONSUMER_CONFIG`

---

### 8. Kafka Producer 无压缩

**修复**: 添加 `compression_type: "lz4"` 配置

**效果**: 
- 减少网络带宽使用
- 提高吞吐量
- 降低存储成本

---

## 📁 修改的文件列表

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `deploy/docker-compose.yml` | 修改 | Redis 安全配置 |
| `infrastructure/cache/redis_client.py` | 修改 | KEYS → SCAN |
| `infrastructure/cache/cache_manager.py` | 修改 | LRU 缓存 |
| `infrastructure/messaging/topics.py` | 修改 | 添加缺失 Topic |
| `infrastructure/messaging/kafka_config.py` | **新建** | 统一 Kafka 配置 |
| `shared/config/defaults/infrastructure/middleware.py` | 修改 | 引用 Topics 类 |
| `runtime/shared/consumer.py` | 修改 | 使用统一配置 |
| `runtime/shared/publisher.py` | 修改 | 添加压缩配置 |
| `runtime/signal_runtime/runtime.py` | 修改 | 使用 Topics/ConsumerGroup |
| `runtime/execution_runtime/runtime.py` | 修改 | 使用 Topics/ConsumerGroup |
| `runtime/projection_runtime/runtime.py` | 修改 | 使用 Topics/ConsumerGroup |

---

## 📖 使用指南

### 获取 Topic 名称

```python
from infrastructure.messaging import Topics

# 基础 Topic
topic = Topics.EVENTS          # "tradeagent.events"
topic = Topics.DECISIONS       # "tradeagent.decisions.all"
topic = Topics.ORDERS          # "tradeagent.orders"

# 动态 Topic
topic = Topics.kline_1m("binance", "BTCUSDT")  # "kline.binance.1m.BTCUSDT"
```

### 获取 Consumer Group ID

```python
from infrastructure.messaging.kafka_config import ConsumerGroup

group_id = ConsumerGroup.SIGNAL_RUNTIME      # "tradeagent-signal"
group_id = ConsumerGroup.EXECUTION_RUNTIME   # "tradeagent-execution"
group_id = ConsumerGroup.for_runtime("custom")  # "tradeagent-custom"
```

### 使用统一配置

```python
from infrastructure.messaging.kafka_config import (
    DEFAULT_CONSUMER_CONFIG,
    DEFAULT_PRODUCER_CONFIG,
)

# Consumer 配置
config = ConsumerConfig(
    bootstrap_servers="localhost:9092",
    topics=[Topics.EVENTS],
    group_id=ConsumerGroup.SIGNAL_RUNTIME,
    # 其他配置使用默认值
)

# Producer 配置
config = PublisherConfig(
    bootstrap_servers="localhost:9092",
    topic=Topics.DECISIONS,
    # 其他配置使用默认值（包含 lz4 压缩）
)
```

### 使用 Redis 缓存

```python
from infrastructure.cache.cache_manager import CacheManager, get_cache_manager

# 创建缓存管理器（默认 1000 条内存缓存）
cache = CacheManager(max_memory_items=1000)

# 使用缓存
await cache.set("key", {"data": "value"}, ttl=60)
result = await cache.get("key")

# 删除匹配的 key（使用 SCAN，不会阻塞）
await cache.delete_pattern("prefix:*")
```

---

## ✅ 验证结果

```bash
$ python -c "
from infrastructure.messaging.topics import Topics
from infrastructure.messaging.kafka_config import ConsumerGroup, DEFAULT_CONSUMER_CONFIG, DEFAULT_PRODUCER_CONFIG
from infrastructure.cache.cache_manager import CacheManager, LRUMemoryCache

print('✅ Topics:', Topics.EVENTS, Topics.DECISIONS, Topics.ORDERS)
print('✅ ConsumerGroup:', ConsumerGroup.SIGNAL_RUNTIME, ConsumerGroup.EXECUTION_RUNTIME)
print('✅ ConsumerConfig:', DEFAULT_CONSUMER_CONFIG.session_timeout_ms, DEFAULT_CONSUMER_CONFIG.max_poll_records)
print('✅ ProducerConfig:', DEFAULT_PRODUCER_CONFIG.compression_type, DEFAULT_PRODUCER_CONFIG.batch_size)
print('✅ LRUMemoryCache test:', len(LRUMemoryCache(max_size=100)._cache))
print('All imports successful!')
"

✅ Topics: tradeagent.events tradeagent.decisions.all tradeagent.orders
✅ ConsumerGroup: tradeagent-signal tradeagent-execution
✅ ConsumerConfig: 30000 500
✅ ProducerConfig: lz4 16384
✅ LRUMemoryCache test: 0
All imports successful!

$ docker-compose config --quiet && echo "✅ Docker Compose config valid"
✅ Docker Compose config valid
```

---

## 🔄 后续改进建议

### 短期 (1周内)

1. **添加 Redis 密码认证**: 生产环境必须配置密码
2. **完善监控**: 添加 Kafka/Redis 指标监控
3. **添加告警**: 配置 Lag 和内存使用告警

### 中期 (1个月内)

1. **Kafka Exporter**: 部署 kafka-exporter 进行详细监控
2. **Redis Exporter**: 部署 redis-exporter 进行详细监控
3. **Schema Registry**: 考虑引入 Schema Registry 进行消息验证

### 长期

1. **Kafka 集群**: 生产环境部署多节点集群
2. **Redis 集群**: 考虑 Redis Sentinel 或 Cluster
3. **消息追踪**: 实现全链路消息追踪

---

## 📚 参考资料

- [Kafka Best Practices](https://kafka.apache.org/documentation/#producerconfigs)
- [Redis Best Practices](https://redis.io/docs/management/optimization/)
- [aiokafka Documentation](https://aiokafka.readthedocs.io/)
- [FastStream Documentation](https://faststream.airt.ai/)
