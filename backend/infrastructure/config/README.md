# Config 配置系统

## 目录结构

```
shared/config/
├── __init__.py          # 统一导出
├── enums.py             # 枚举定义
├── schemas.py           # 配置Schema定义
├── manager.py           # ConfigManager 实现
└── defaults/            # 默认配置值
    ├── __init__.py      # 合并导出
    ├── core.py          # 系统级配置
    ├── index.py         # 配置合并索引
    │
    ├── infrastructure/  # 基础设施配置（所有服务共用）
    │   ├── cache.py         # Redis 缓存配置
    │   ├── logging.py       # 日志配置
    │   ├── middleware.py    # Kafka 等中间件配置
    │   ├── monitoring.py    # 监控指标配置
    │   ├── alerting.py       # 告警规则配置
    │   └── api_gateway.py   # API网关路由配置
    │
    └── business/        # 业务配置（跟业务逻辑相关）
        ├── trading.py       # 交易相关配置
        ├── risk.py          # 风控相关配置
        ├── strategy.py       # 策略参数配置
        ├── market.py        # 市场数据配置
        ├── datasource.py    # 数据源配置
        └── notification.py  # 通知配置
```

## 配置分类

| 分类 | 说明 | 示例 |
|------|------|------|
| **infrastructure** | 基础设施配置，所有服务共用 | Redis连接、日志级别、Kafka主题 |
| **business** | 业务配置，跟业务逻辑相关 | 交易杠杆、风控阈值、策略权重 |

## 使用方式

### 1. 导入配置

```python
# 方式一：从 shared.config 直接导入（推荐）
from shared.config import (
    TRADING_CONFIGS,
    CACHE_CONFIGS,
    LOGGING_CONFIGS,
)

# 方式二：从具体子模块导入
from shared.config.defaults.infrastructure import CACHE_CONFIGS
from shared.config.defaults.business import TRADING_CONFIGS
```

### 2. 读取配置

```python
# 使用 ConfigManager（支持运行时修改）
from shared.config import get_config_manager

config = get_config_manager()
log_level = config.get("logging.system_level")  # 从 Redis 读取，没有则用默认值

# 直接读取默认配置（只读）
from shared.config import CACHE_CONFIGS
redis_url = CACHE_CONFIGS.get("cache.redis_url")
```

### 3. 修改配置（运行时）

```python
from shared.config import get_config_manager

config = get_config_manager()
config.set(
    "trading.default_leverage",
    value=5,
    changed_by="admin",
    reason="调整杠杆"
)
```

## 配置持久化

配置有三级存储，优先级从高到低：

```
┌─────────────────────────────────────┐
│  Memory (_memory_config)           │  ← 最高优先级，服务重启丢失
│  进程内缓存                          │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Redis (config:{key})              │  ← 持久化存储
│  服务重启后仍保留                     │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Python 文件 (defaults/*.py)        │  ← 最低优先级，代码级兜底
│  DEFAULT_CONFIGS                     │
└─────────────────────────────────────┘
```

**读取顺序**: Memory → Redis → Python文件默认值

**写入顺序**: Memory + Redis（同时写入）

## 环境变量覆盖

可以通过环境变量覆盖默认配置：

```bash
export REDIS_URL="redis://prod:6379/0"
export LOG_LEVEL="DEBUG"
export TRADING_DEFAULT_LEVERAGE="5"
```

## 添加新配置

### 1. 基础设施配置

在 `defaults/infrastructure/` 对应文件中添加，例如 `cache.py`：

```python
CACHE_CONFIGS = {
    # ... 现有配置 ...
    "cache.new_option": "default_value",
}
```

### 2. 业务配置

在 `defaults/business/` 对应文件中添加，例如 `trading.py`：

```python
TRADING_CONFIGS = {
    # ... 现有配置 ...
    "trading.new_option": "default_value",
}

TRADING_SCHEMAS = {
    "trading.new_option": {
        "value_type": "string",
        "default": "default_value",
        "description": "新配置项说明",
    },
}
```

### 3. 更新 index.py

`defaults/index.py` 会自动合并所有配置，无需手动修改。

## 配置命名规范

- 使用点分隔符层级命名：`{category}.{subcategory}.{name}`
- 示例：`cache.redis_url`、`trading.default_leverage`、`logging.system_level`

## 相关模块

- [infrastructure/logging](../../infrastructure/logging) - 日志系统
- [infrastructure/cache](../../infrastructure/cache) - 缓存系统
- [infrastructure/monitoring](../../infrastructure/monitoring) - 监控系统
