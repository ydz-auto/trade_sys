# 迁移指南 - shared/config 到 config/

**创建日期**: 2026-05-14  
**计划完成**: 2026-06-01

---

## 概述

本文档记录从 `shared/config/` 到 `config/` (五层配置治理系统) 的迁移过程。

---

## 迁移状态

| 服务 | 状态 | 文件数 | 说明 |
|---|---|---|---|
| `services/data_service/` | ⏳ 待迁移 | 5 | 数据采集服务 |
| `services/approval_service/` | ⏳ 待迁移 | 3 | 审批服务 |
| `services/aggregation_service/` | ⏳ 待迁移 | 1 | 聚合服务 |
| `services/event_service/` | ⏳ 待迁移 | 1 | 事件服务 |
| `services/repair_service/` | ⏳ 待迁移 | 1 | 修复服务 |
| `services/llm_service/` | ⏳ 待迁移 | 1 | LLM 服务 |
| `infrastructure/` | ⏳ 待迁移 | 8 | 基础设施配置 |
| `shared/` 内部 | ⏳ 待迁移 | 18 | shared 模块内部依赖 |

**总计**: 38 个文件需要迁移

---

## 迁移步骤

### 1. 识别依赖

```bash
# 查找所有使用 shared.config 的文件
grep -r "from shared\.config" backend/ --include="*.py"
grep -r "from shared import.*Config" backend/ --include="*.py"
```

### 2. 更新导入语句

**旧代码**:
```python
from shared.config import ConfigManager, get_config_manager
```

**新代码**:
```python
from config import ConfigManager
```

### 3. 更新配置获取方式

**旧代码**:
```python
from shared.config import get_config_manager

config_manager = get_config_manager()
trading_config = config_manager.get("trading")
```

**新代码**:
```python
from config import ConfigManager

config_manager = ConfigManager.load("dev")  # 或 "prod", "replay"
trading_config = config_manager.get_runtime_config("execution")
```

### 4. 配置文件迁移

| 旧位置 | 新位置 |
|---|---|
| `shared/config/defaults/business/trading.py` | `config/runtime/execution.yaml` |
| `shared/config/defaults/business/risk.py` | `config/runtime/execution.yaml` |
| `shared/config/defaults/business/strategy.py` | `config/strategy/btc_swing.yaml` |
| `shared/config/defaults/infrastructure/cache.py` | `config/infra/infra.yaml` |
| `shared/config/defaults/infrastructure/database.py` | `config/infra/infra.yaml` |

---

## 迁移示例

### services/data_service/main.py

**旧代码**:
```python
from shared.config import get_config_manager

config = get_config_manager()
symbols = config.get("datasource.symbols")
```

**新代码**:
```python
from config import ConfigManager

config = ConfigManager.load("dev")
symbols = config.get_runtime_config("ingestion").symbols
```

### services/approval_service/decision_gate.py

**旧代码**:
```python
from shared.config import TRADING_CONFIGS

approval_config = TRADING_CONFIGS.get("approval", {})
```

**新代码**:
```python
from config import ConfigManager

config = ConfigManager.load("dev")
approval_config = config.get_runtime_config("execution").approval
```

---

## 验证清单

- [ ] 所有 `from shared.config` 导入已更新
- [ ] 所有 `from shared import.*Config` 导入已更新
- [ ] 配置文件已迁移到 `config/` 目录
- [ ] 测试通过
- [ ] 无 DeprecationWarning

---

## 删除计划

完成所有迁移后，删除以下文件：

```bash
rm -rf backend/shared/config/
```

---

## 联系人

如有问题，请联系架构团队。
