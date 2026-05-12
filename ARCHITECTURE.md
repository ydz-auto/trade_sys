# 架构设计文档 - 内部自由，外部稳定

## 核心理念

### 两类 Schema 的严格区分

| 类别 | 存放位置 | 特点 | 修改频率 | 示例 |
|------|----------|------|----------|------|
| **内部 Schema** | 各服务内部的 `schemas/` 目录 | 可以随意修改，仅影响该服务 | 高 | `OdailyRawArticle`, `BinanceTicker` |
| **共享合约** | `shared/contracts/` | 系统公共语言，必须保持稳定！ | 低 | `StandardEvent`, `MarketEvent` |


## 目录结构

```
trade_agent/
│
├── shared/
│   ├── contracts/              # 系统公共合约，必须稳定！
│   │   ├── __init__.py         # StandardEvent 协议在此
│   │   │
│   │   └── (未来扩展)
│   │       ├── intelligence.py  # 情报层事件合约
│   │       ├── market.py        # 市场数据合约
│   │       └── risk.py          # 风控事件合约
│   │
│   ├── config/
│   ├── state/
│   └── ...
│
├── services/
│   │
│   ├── data_service/             # 数据服务
│   │   ├── schemas/              # 内部 Schema（可自由修改）
│   │   │   ├── odaily.py         # Odaily 原始数据结构
│   │   │   ├── binance.py        # Binance API 响应结构
│   │   │   └── twitter.py        # Twitter API 响应结构
│   │   │
│   │   ├── adapters/             # 适配器层
│   │   │   └── skill_adapter.py  # 转换：OdailyRaw → StandardEvent
│   │   │
│   │   ├── collectors/
│   │   ├── event_bus/
│   │   ├── intelligence/
│   │   ├── market/
│   │   └── ...
│   │
│   ├── strategy_service/
│   │   ├── schemas/              # 策略服务内部 Schema
│   │   └── ...
│   │
│   ├── risk_service/
│   │   ├── schemas/              # 风控服务内部 Schema
│   │   └── ...
│   │
│   └── execution_service/
│       ├── schemas/              # 执行服务内部 Schema
│       └── ...
│
└── infrastructure/
```


## 核心原则

### 1. 内部自由
- **各服务的 `schemas/` 目录**：可以随意修改，仅影响该服务内部
- **示例**：`data_service/schemas/odaily.py` 中定义的 `OdailyRawArticle` 可以随时重构
- **修改方式**：直接修改该服务内部文件，无需考虑其他服务


### 2. 外部稳定
- **`shared/contracts/` 目录**：系统公共语言，修改需谨慎！
- **特点**：
  - 所有跨服务通信必须使用合约
  - 合约变更需要版本管理
  - 合约必须支持向后兼容


## 示例数据流

### Odaily Skill 数据流程

```
ClawHub Odaily Skill (Python脚本)
      ↓
data_service/schemas/odaily.py
      ↓
  OdailyRawArticle (内部 Schema - 可随意改)
      ↓
  Skill Adapter 转换
      ↓
shared/contracts/__init__.py
      ↓
  StandardEvent (公共合约 - 必须稳定)
      ↓
  Event Bus
      ↓
  ├───→ strategy_service (订阅 StandardEvent)
  ├───→ risk_service     (订阅 StandardEvent)
  └───→ llm_service      (订阅 StandardEvent)
```


## Import 规范

### 导入共享合约（推荐所有服务使用）

```python
# ✅ 正确：从 shared 导入公共合约
from shared.contracts import StandardEvent, EventType, Source, create_news_event
```

### 导入服务内部 Schema（仅该服务内部使用）

```python
# ✅ 正确：在 data_service 内部导入
from services.data_service.schemas.odaily import OdailyRawArticle
```


## 合约版本管理（未来规划）

当需要修改 `shared/contracts` 时：

```
shared/contracts/
├── v1/               # v1 版本（保持兼容）
│   └── __init__.py
├── v2/               # v2 版本（新特性）
│   └── __init__.py
└── latest/           # 当前版本（稳定）
    └── __init__.py
```


## FAQ

### Q: 什么时候应该把东西放进 shared/contracts？
A: 只有当**多个服务需要共享**这个数据结构时，才应该放到 `shared/contracts`。

### Q: 什么时候应该把东西放进服务内部的 schemas？
A: 当这个数据结构**仅在该服务内部使用**时。

### Q: 我想加个新字段到 StandardEvent，怎么办？
A: 先确认是否真的需要，尽量通过 `metadata` 字段扩展，避免修改核心合约结构。


## 测试结果

✅ **重构成功！**
- 所有模块正常工作
- ClawHub Odaily Skill 集成正常
- `shared/contracts` 中的 `StandardEvent` 正常使用
- 服务内部 `schemas/odaily.py` 正常工作
