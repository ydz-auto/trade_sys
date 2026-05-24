# State Service（状态管理）设计文档

# 🧠 1. 模块定位

# 1.1 核心作用

管理交易系统的**所有运行时状态**，包括：
- 当前仓位
- 账户余额
- 风险状态
- 策略状态
- 订单状态

它是**系统的状态中枢**，所有模块共享同一个状态源。

# 1.2 为什么必须独立

```
❌ 不要让每个模块自己管理状态
✅ 统一状态管理 → 所有模块读取同一份状态
```

好处：
- 数据一致性
- 状态可追溯
- 便于回测和审计

# 🏗️ 2. 状态分类

# 2.1 Account State（账户状态）

```json
{
  "mode": "LIVE",
  "balance": 10000.0,
  "available_balance": 8500.0,
  "frozen_balance": 1500.0,
  "total_pnl": 500.0,
  "total_pnl_percent": 5.0,
  "last_update": 1710000000
}
```

# 2.2 Position State（仓位状态）

```json
{
  "positions": [
    {
      "symbol": "BTC",
      "direction": "LONG",
      "size": 0.3,
      "entry_price": 68000.0,
      "current_price": 70000.0,
      "leverage": 3,
      "pnl": 600.0,
      "pnl_percent": 2.94,
      "stop_loss": 66000.0,
      "take_profit": 72000.0,
      "opened_at": 1709990000,
      "order_id": "order_12345"
    }
  ],
  "total_exposure": 0.45,
  "max_exposure": 0.5
}
```

# 2.3 Risk State（风险状态）

```json
{
  "risk_index": 65,
  "risk_level": "MEDIUM",
  "allow_trading": true,
  "max_position": 0.25,
  "max_leverage": 2,
  "consecutive_losses": 0,
  "drawdown": 0.03,
  "max_drawdown_limit": 0.1,
  "risk_triggered": false,
  "risk_triggered_at": null
}
```

# 2.4 Strategy State（策略状态）

```json
{
  "signal": "BUY",
  "confidence": 0.75,
  "composite_score": 0.35,
  "regime": "RISK_ON",
  "factors": {
    "trend": 0.55,
    "flow": -0.2,
    "sentiment": -0.6,
    "macro": 0.3
  },
  "last_signal_at": 1710000000,
  "signal_count_today": 5
}
```

# 2.5 Order State（订单状态）

```json
{
  "orders": [
    {
      "order_id": "order_12345",
      "symbol": "BTC",
      "type": "OPEN_LONG",
      "size": 0.3,
      "price": 68000.0,
      "status": "FILLED",
      "filled_at": 1709990000,
      "filled_price": 68000.0
    }
  ],
  "pending_orders": [],
  "failed_orders": []
}
```

# 2.6 System State（系统状态）

```json
{
  "mode": "LIVE",
  "status": "RUNNING",
  "last_heartbeat": 1710000000,
  "services": {
    "data_service": "OK",
    "factor_service": "OK",
    "risk_service": "OK",
    "execution_service": "OK"
  },
  "errors": []
}
```

# 🔄 3. 状态转换规则

# 3.1 仓位状态机

```
IDLE → OPENING → OPEN → CLOSING → CLOSED
         ↓
       FAILED
```

# 3.2 风险状态机

```
LOW_RISK ←→ MEDIUM_RISK ←→ HIGH_RISK ←→ EXTREME
                ↓               ↓           ↓
           REDUCING       CLOSING_ALL    STOPPED
```

# 3.3 订单状态机

```
PENDING → SUBMITTED → FILLED
    ↓         ↓
  REJECTED  PARTIAL
      ↓         ↓
   FAILED    CANCELLED
```

# 🛡️ 4. 状态隔离（回测 vs 实盘）

# 4.1 状态存储分离

```python
class StateStore:
    def __init__(self, mode: str):
        if mode == "BACKTEST":
            self.storage = InMemoryStateStore()
        else:
            self.storage = RedisStateStore()  # 或 PostgreSQL

    def get_state(self, key: str) -> dict:
        return self.storage.get(key)

    def set_state(self, key: str, value: dict):
        self.storage.set(key, value)
```

# 4.2 回测状态快照

```json
{
  "snapshot_id": "backtest_20240101_001",
  "timestamp": 1704067200,
  "initial_balance": 10000.0,
  "positions": [],
  "orders": []
}
```

# 📤 5. 状态更新机制

# 5.1 乐观锁更新

```python
def update_state(key: str, update_fn, expected_version: int):
    current = state_store.get(key)
    if current["version"] != expected_version:
        raise OptimisticLockError("State modified by others")

    new_state = update_fn(current)
    new_state["version"] = expected_version + 1
    state_store.set(key, new_state)
```

# 5.2 事件驱动更新

```python
class StateManager:
    def __init__(self):
        self.subscribers = defaultdict(list)

    def subscribe(self, event_type: str, callback):
        self.subscribers[event_type].append(callback)

    def emit(self, event_type: str, data: dict):
        for callback in self.subscribers[event_type]:
            callback(data)
```

# 5.3 状态变更事件

```python
STATE_CHANGE_EVENTS = [
    "position_opened",
    "position_closed",
    "position_updated",
    "order_submitted",
    "order_filled",
    "order_failed",
    "risk_triggered",
    "risk_recovered",
    "balance_changed"
]
```

# 🗄️ 6. 存储设计

# 6.1 Redis结构

```
state:account                    → Account State
state:positions                  → Position State
state:risk                       → Risk State
state:strategy                   → Strategy State
state:orders                     → Order State
state:system                     → System State
state:version                    → 全局版本号
```

# 6.2 数据库表设计

```sql
CREATE TABLE state_snapshots (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    state_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    state_data JSON NOT NULL,
    version INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_state_type (state_type),
    INDEX idx_created_at (created_at)
);

CREATE TABLE state_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    state_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    action VARCHAR(20) NOT NULL,
    old_state JSON,
    new_state JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_state_type_action (state_type, action),
    INDEX idx_created_at (created_at)
);
```

# 🔒 7. 状态一致性保证

# 7.1 ACID保证

```python
def atomic_state_update(key: str, updates: dict):
    with db.transaction():
        current = db.get(key)
        new_state = {**current, **updates, "version": current["version"] + 1}
        db.set(key, new_state)
        db.insert_history(key, current, new_state)
```

# 7.2 状态恢复机制

```python
def recover_state():
    last_valid = db.query("SELECT * FROM state_snapshots ORDER BY id DESC LIMIT 1")
    for state_type, state_data in last_valid["state_data"].items():
        state_store.set(state_type, state_data)
```

# 📊 8. 状态查询接口

# 8.1 查询当前状态

```python
GET /api/v1/state/{state_type}
GET /api/v1/state/positions
GET /api/v1/state/risk
```

# 8.2 查询历史状态

```python
GET /api/v1/state/history/{state_type}?from=timestamp&to=timestamp
GET /api/v1/state/snapshot/{snapshot_id}
```

# 🏗️ 9. 架构设计

```
StateService
├── StateStore（抽象存储层）
│   ├── InMemoryStateStore（回测用）
│   ├── RedisStateStore（实盘用）
│   └── PostgreSQLStateStore（持久化用）
├── StateManager（状态管理核心）
│   ├── AccountManager
│   ├── PositionManager
│   ├── RiskManager
│   ├── StrategyManager
│   └── OrderManager
├── StateEventBus（事件总线）
│   └── EventPublisher / EventSubscriber
├── StateSnapshot（快照管理）
│   ├── SnapshotCreator
│   └── SnapshotRestorer
└── StateHistory（历史记录）
    ├── HistoryRecorder
    └── HistoryQuery
```

# 🔗 10. 与其他模块对接

# 10.1 数据流

```
Position Engine → StateService.update_position()
Risk Engine → StateService.get_risk_state()
Decision Engine → StateService.get_strategy_state()
Execution Service → StateService.update_order()
Monitoring Service → StateService.subscribe_state_change()
```

# 10.2 接口示例

```python
class StateService:
    def update_position(self, position: dict, action: str):
        if action == "OPEN":
            self.position_manager.add_position(position)
        elif action == "CLOSE":
            self.position_manager.close_position(position)
        elif action == "UPDATE":
            self.position_manager.update_position(position)

        self.event_bus.emit(f"position_{action.lower()}", position)
        self.snapshot.create_snapshot()

    def check_risk_limits(self) -> bool:
        risk_state = self.get_risk_state()
        position_state = self.get_position_state()

        if risk_state["risk_index"] > 80:
            return False
        if position_state["total_exposure"] > 0.5:
            return False
        return True
```

# 🚀 11. 扩展方向

- 分布式状态管理（多实例）
- 状态变更自动告警
- 状态版本对比工具
- 状态模拟器（用于测试）
