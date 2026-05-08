# Config Service（配置中心）设计文档

# 🧠 1. 模块定位

# 1.1 核心作用

统一管理交易系统的**所有配置参数**，包括：
- 因子权重
- 风险参数
- 策略开关
- 交易限制
- API密钥配置

# 1.2 设计目标

```
✅ 集中管理 → 避免配置散落各处
✅ 运行时可调 → 无需重启修改参数
✅ 版本可控 → 配置变更可追溯
✅ 环境隔离 → 回测/模拟/实盘配置分离
```

# 📁 2. 配置分类

# 2.1 Factor Config（因子配置）

```json
{
  "factors": {
    "trend": {
      "enabled": true,
      "weight": 0.30,
      "params": {
        "momentum_window": 20,
        "ma_short": 5,
        "ma_long": 20
      }
    },
    "flow": {
      "enabled": true,
      "weight": 0.25,
      "params": {
        "etf_scale": 100000000,
        "acceleration_alpha": 0.3
      }
    },
    "sentiment": {
      "enabled": true,
      "weight": 0.20,
      "params": {
        "llm_model": "minimax",
        "decay_lambda": 0.1
      }
    },
    "macro": {
      "enabled": true,
      "weight": 0.15,
      "params": {
        "gold_weight": 0.6,
        "oil_weight": 0.4
      }
    },
    "behavioral": {
      "enabled": false,
      "weight": 0.10,
      "params": {}
    },
    "historical": {
      "enabled": true,
      "weight": 0.05,
      "params": {
        "vector_top_k": 5
      }
    }
  }
}
```

# 2.2 Risk Config（风险配置）

```json
{
  "risk": {
    "limits": {
      "max_position_single": 0.30,
      "max_position_total": 0.50,
      "max_leverage": 3,
      "max_drawdown": 0.10,
      "max_daily_loss": 0.05
    },
    "thresholds": {
      "risk_low": 30,
      "risk_medium": 60,
      "risk_high": 80,
      "risk_extreme": 90
    },
    "weights": {
      "vol": 0.25,
      "flow": 0.20,
      "sentiment": 0.20,
      "macro": 0.15,
      "behavioral": 0.10,
      "portfolio": 0.10
    },
    "actions": {
      "high_risk_leverage": 1,
      "medium_risk_leverage": 2,
      "low_risk_leverage": 3,
      "consecutive_loss_limit": 3,
      "stop_trading_risk_index": 80
    }
  }
}
```

# 2.3 Position Config（仓位配置）

```json
{
  "position": {
    "base": {
      "max_position": 0.30,
      "default_leverage": 2,
      "stop_loss_k": 2.0,
      "take_profit_rr": 2.5
    },
    "calculation": {
      "confidence_weight": true,
      "volatility_adjustment": true,
      "risk_factor_adjustment": true
    },
    "conflict": {
      "same_direction": "ADD",
      "opposite_direction": "CLOSE_THEN_OPEN",
      "max_position_check": true
    }
  }
}
```

# 2.4 Strategy Config（策略配置）

```json
{
  "strategy": {
    "decision": {
      "buy_threshold": 0.30,
      "sell_threshold": -0.30,
      "hold_confidence_min": 0.3
    },
    "regime_adjustments": {
      "RISK_ON": {
        "buy_threshold": 0.25,
        "sell_threshold": -0.35
      },
      "RISK_OFF": {
        "buy_threshold": 0.40,
        "sell_threshold": -0.25
      }
    },
    "limits": {
      "max_signals_per_day": 10,
      "min_signal_interval_seconds": 300
    }
  }
}
```

# 2.5 System Config（系统配置）

```json
{
  "system": {
    "mode": "LIVE",
    "execution": {
      "mode": "DRY_RUN",
      "retry_times": 3,
      "retry_interval_seconds": 5
    },
    "data": {
      "default_timeframe": "5m",
      "cache_ttl_seconds": 60
    },
    "services": {
      "heartbeat_interval_seconds": 30,
      "graceful_shutdown_timeout": 10
    }
  }
}
```

# 2.6 API Config（API配置）

```json
{
  "api": {
    "binance": {
      "api_key": "xxx",
      "secret_key": "xxx",
      "testnet": false
    },
    "okx": {
      "api_key": "xxx",
      "secret_key": "xxx",
      "testnet": true
    },
    "llm": {
      "provider": "minimax",
      "api_key": "xxx",
      "model": "minimax-01",
      "temperature": 0.3
    }
  }
}
```

# 🏗️ 3. 配置存储结构

# 3.1 分层存储

```
config/
├── base/
│   ├── factor.json
│   ├── risk.json
│   ├── position.json
│   └── strategy.json
├── env/
│   ├── backtest.json
│   ├── simulation.json
│   └── live.json
├── secrets/
│   └── api.json (加密存储)
└── overrides/
    └── custom.json (运行时覆盖)
```

# 3.2 数据库表设计

```sql
CREATE TABLE config_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL,
    config_value JSON NOT NULL,
    version INT NOT NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comment TEXT,
    UNIQUE KEY uk_config_key_version (config_key, version)
);

CREATE TABLE config_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL,
    old_value JSON,
    new_value JSON NOT NULL,
    action VARCHAR(20) NOT NULL,
    changed_by VARCHAR(50),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE config_secrets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    secret_key VARCHAR(100) NOT NULL UNIQUE,
    encrypted_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

# 🔄 4. 配置加载与更新

# 4.1 配置加载

```python
class ConfigService:
    def __init__(self, env: str):
        self.env = env
        self.configs = {}
        self.secrets = {}

    def load_all(self):
        self.configs["base"] = self.load_json("config/base")
        self.configs["env"] = self.load_json(f"config/env/{self.env}")
        self.configs["overrides"] = self.load_json("config/overrides/custom") or {}
        self.secrets = self.load_secrets()
        self.merge_configs()

    def merge_configs(self):
        self.final_config = {}
        self.final_config.update(self.configs["base"])
        self.final_config.update(self.configs["env"])
        self.final_config.update(self.configs["overrides"])
        self.final_config.update(self.secrets)
```

# 4.2 配置热更新

```python
def update_config(key: str, value: dict, comment: str = ""):
    with db.transaction():
        old_value = get_config(key)
        new_version = get_next_version(key)

        insert_config_history(key, old_value, value, "UPDATE")

        set_config(key, value, new_version)

        notify_config_change(key, value)
```

# 4.3 配置验证

```python
CONFIG_SCHEMA = {
    "factors": {
        "type": "object",
        "required": ["trend", "flow", "sentiment"],
        "properties": {
            "weight": {"type": "number", "min": 0, "max": 1},
            "enabled": {"type": "boolean"}
        }
    },
    "risk": {
        "type": "object",
        "required": ["limits", "thresholds"],
        "properties": {
            "max_position_single": {"type": "number", "max": 1}
        }
    }
}

def validate_config(config: dict, schema: dict) -> bool:
    for key, rules in schema.items():
        if key not in config and rules.get("required"):
            raise ConfigValidationError(f"Missing required: {key}")
        if key in config:
            if not isinstance(config[key], rules["type"]):
                raise ConfigValidationError(f"Invalid type for: {key}")
    return True
```

# 📤 5. 配置查询接口

# 5.1 获取配置

```python
GET /api/v1/config/{category}
GET /api/v1/config/factors
GET /api/v1/config/risk
GET /api/v1/config/position
```

# 5.2 更新配置

```python
PUT /api/v1/config/{category}
Body: {"key": "value", "comment": "原因"}

POST /api/v1/config/factors/trend/weight
Body: {"value": 0.35, "comment": "提高趋势权重"}
```

# 5.3 版本查询

```python
GET /api/v1/config/versions/{key}
GET /api/v1/config/history/{key}
```

# 🔐 6. 敏感信息管理

# 6.1 加密存储

```python
from cryptography.fernet import Fernet

class SecretManager:
    def __init__(self):
        self.cipher = Fernet(settings.ENCRYPTION_KEY)

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

    def save_secret(self, key: str, value: str):
        encrypted = self.encrypt(value)
        db.execute("INSERT INTO config_secrets VALUES (?, ?)", [key, encrypted])

    def get_secret(self, key: str) -> str:
        encrypted = db.query("SELECT encrypted_value FROM config_secrets WHERE secret_key = ?", [key])
        return self.decrypt(encrypted)
```

# 6.2 环境变量覆盖

```python
import os

def resolve_config_value(key: str, config_value):
    env_key = f"TRADEAGENT_{key.upper().replace('.', '_')}"
    if env_key in os.environ:
        return os.environ[env_key]
    return config_value
```

# 🏗️ 7. 架构设计

```
ConfigService
├── ConfigLoader
│   ├── JSONLoader
│   ├── DatabaseLoader
│   └── EnvLoader
├── ConfigMerger
├── ConfigValidator
├── ConfigStore
│   ├── FileStore
│   ├── DatabaseStore
│   └── SecretStore
├── ConfigVersionManager
│   ├── VersionRecorder
│   └── VersionRollback
├── ConfigChangeNotifier
│   └── WebSocket / MQTT
└── ConfigCache
```

# 🔗 8. 与其他模块对接

```python
class ConfigService:
    def get_factor_config(self) -> dict:
        return self.final_config["factors"]

    def get_risk_config(self) -> dict:
        return self.final_config["risk"]

    def get_position_config(self) -> dict:
        return self.final_config["position"]

    def get_strategy_config(self) -> dict:
        return self.final_config["strategy"]

    def subscribe_changes(self, callback):
        self.notifier.subscribe("config_changed", callback)
```

# 🚨 9. 配置变更通知机制

# 9.1 变更事件

```python
CONFIG_CHANGE_EVENTS = [
    "factor_weight_changed",
    "risk_threshold_changed",
    "position_limit_changed",
    "strategy_threshold_changed",
    "api_key_rotated"
]
```

# 9.2 自动通知

```python
def notify_config_change(key: str, new_value):
    event = {
        "type": "config_changed",
        "key": key,
        "value": new_value,
        "timestamp": time.time()
    }
    for subscriber in subscribers:
        subscriber(event)
```

# ✅ 10. 配置回滚

```python
def rollback_config(key: str, target_version: int):
    version_data = db.query("SELECT * FROM config_versions WHERE config_key = ? AND version = ?", [key, target_version])

    old_current = get_current_config(key)
    insert_config_history(key, old_current, version_data, "ROLLBACK")

    set_config(key, version_data["config_value"], target_version)

    notify_config_change(key, version_data["config_value"])
```

# 🚀 11. 扩展方向

- 配置模板管理
- A/B测试配置
- 配置对比工具
- 配置影响分析
- 自动化配置优化
