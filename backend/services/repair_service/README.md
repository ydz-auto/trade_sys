# Repair Service - 数据修复服务

## 📊 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Aggregation Service                              │
│                      (检测到缺失 → 标记 is_complete=False)                  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Repair Service ⭐                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │  Gap          │  │  Repair        │  │  Repair        │           │
│  │  Detector     │  │  Scheduler     │  │  Rebuilder    │           │
│  │               │  │                │  │               │           │
│  │  • 扫描缺口   │  │  • 优先级队列  │  │  • 从低周期   │           │
│  │  • 完整性检查 │  │  • 任务管理   │  │    重建       │           │
│  │  • 报告生成  │  │  • 重试机制  │  │  • 从API恢复  │           │
│  └────────────────┘  └────────────────┘  │  • 插值填充   │           │
│                                           │  • 标记脏数据 │           │
│                                           └────────────────┘           │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          ClickHouse                                      │
│                   (更新 is_complete=True)                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
repair_service/
├── models/
│   ├── repair_models.py         # 修复数据模型
│   │
├── detectors/
│   └── gap_detector.py         # 缺口检测器
│
├── rebuilders/
│   └── candle_rebuilder.py     # K线重建器
│
├── schedulers/
│   └── repair_scheduler.py     # 修复调度器
│
├── main.py                      # 主入口
└── README.md
```

---

## 🎯 核心职责

| 职责 | 说明 |
|------|------|
| 缺口检测 | 扫描 K线数据中的缺失 |
| 完整性检查 | 生成完整性报告 |
| 自动回补 | 从低周期/ API 重建 |
| 任务调度 | 优先级队列 + 重试机制 |
| 历史修复 | 回溯修复历史数据 |
| 标记脏数据 | 无法修复时标记 |

---

## 🔧 修复策略

| 策略 | 适用场景 | 说明 |
|------|----------|------|
| `RESTORE` | 缺失 < 60 根 | 从 API 恢复 |
| `REBUILD` | 缺失 > 60 根 | 从低周期聚合重建 |
| `INTERPOLATE` | 缺失 <= 5 根 | 插值填充 |
| `MARK_DIRTY` | 无法修复 | 标记脏数据 |

---

## 📊 数据模型

### GapInfo - 缺口信息

```python
@dataclass
class GapInfo:
    exchange: str           # 交易所
    symbol: str            # 交易对
    timeframe: Timeframe  # 时间周期
    gap_start: int         # 缺口开始时间
    gap_end: int          # 缺口结束时间
    missing_count: int     # 缺失数量

    status: GapStatus     # 状态
    detected_at: int      # 检测时间
    repaired_at: int      # 修复时间
```

### RepairTask - 修复任务

```python
@dataclass
class RepairTask:
    task_id: str
    gap: GapInfo

    strategy: RepairStrategy  # 修复策略
    priority: int            # 优先级

    status: GapStatus
    retry_count: int
    max_retries: int
```

---

## 🔌 使用示例

### 1. 检测缺口

```python
from services.repair_service.detectors import get_gap_detector

detector = await get_gap_detector()

gaps = await detector.detect_gaps(
    exchange="binance",
    symbol="BTCUSDT",
    timeframe="1m",
    start_time=1704067200000,  # 2024-01-01
    end_time=1711929600000     # 2024-04-01
)

print(f"Found {len(gaps)} gaps")
```

### 2. 扫描并修复

```python
from services.repair_service.main import get_repair_service

service = await get_repair_service()

result = await service.scan_symbol(
    exchange="binance",
    symbol="BTCUSDT",
    timeframe="5m",
    days=30
)

print(f"Gaps found: {result['gaps_found']}")
```

### 3. 完整性检查

```python
from services.repair_service.detectors import get_gap_detector

detector = await get_gap_detector()

report = await detector.check_completeness(
    exchange="binance",
    symbol="BTCUSDT",
    timeframe="1h",
    start_time=1704067200000,
    end_time=1711929600000
)

print(f"Completeness: {report.completeness * 100:.2f}%")
print(f"Missing: {report.missing_count}")
```

---

## 📊 Kafka Topic

### aggregation_service 标记

```python
candle.is_complete = False
candle.missing_count = 1
```

### repair_service 修复

```python
candle.is_complete = True
candle.missing_count = 0
```

---

## 📈 ClickHouse 更新

```sql
ALTER TABLE candles
UPDATE is_complete = 1,
    missing_count = 0
WHERE exchange = 'binance'
AND symbol = 'BTCUSDT'
AND timeframe = '1m'
AND open_time >= 1704067200000
AND open_time < 1704153600000
```

---

## 🔥 核心设计

### 1. 优先级队列

```python
@dataclass(order=True)
class PriorityTask:
    priority: int
    task: RepairTask
```

优先级计算：

```python
def _calculate_priority(gap: GapInfo) -> int:
    priority = 10

    if gap.timeframe == "1m":
        priority += 10
    elif gap.timeframe == "5m":
        priority += 5

    if gap.missing_count > 100:
        priority += 20
    elif gap.missing_count > 10:
        priority += 10

    return -priority
```

### 2. 重试机制

```python
max_retries = 3

if task.retry_count < max_retries:
    await self.add_task(task)
else:
    task.status = GapStatus.FAILED
```

### 3. 策略选择

```python
def _select_strategy(gap: GapInfo) -> RepairStrategy:
    if gap.missing_count <= 5:
        return RepairStrategy.INTERPOLATE
    elif gap.missing_count <= 60:
        return RepairStrategy.RESTORE
    else:
        return RepairStrategy.REBUILD
```

---

## 📚 相关文档

- [aggregation_service/README.md](../aggregation_service/README.md) - 聚合服务
- [Topic System](../../infrastructure/messaging/topics.py) - 分层 Topic 体系
