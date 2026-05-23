# 时间权威系统 (Time Authority)

## 概述

时间权威系统是一个强制统一时间格式的基础设施层，确保 Runtime 内部只使用 `int64 ms` 格式的时间戳，彻底解决了之前出现的 `str + int` 拼接错误和时间格式不统一的问题。

## 核心原则

1. **Runtime 内部统一使用 int64 ms**：所有 Runtime 组件只接受和输出 `int64 ms` 格式的时间戳
2. **入口强制转换**：所有外部输入（API、数据文件、配置）必须在进入 Runtime 前转换为 `int64 ms`
3. **来源追踪**：记录时间的来源，便于调试和追踪
4. **单调检查**：检测时间倒流问题

## 核心模块

### `infrastructure.time_authority`

主要组件：

- **`TimeAuthority`**：核心时间权威类，提供所有时间处理功能
- **`normalize_time_ms()`**：将任意时间格式转换为 `int64 ms`
- **`ensure_time_ms()`**：确保时间是 `int64 ms` 格式（转换 + 验证）
- **`validate_time_ms()`**：验证时间有效性
- **`check_monotonic()`**：检查时间是否单调递增
- **`TimeSource`**：枚举，记录时间来源

### 支持的输入格式

| 格式类型 | 示例 | 处理方式 |
|---------|------|---------|
| ISO 字符串 | `"2025-01-01"`, `"2025-01-01 12:00:00"` | 解析为 UTC 时间戳 |
| 秒时间戳 (int) | `1746272000` | 自动乘以 1000 |
| 毫秒时间戳 (int) | `1746272000000` | 直接使用 |
| 浮点秒 | `1746272000.5` | 乘以 1000 并取整 |
| `pd.Timestamp` | `pd.Timestamp("2025-01-01")` | 转换为 int64 ms |
| `datetime` | `datetime(2025, 1, 1)` | 转换为 UTC int64 ms |
| `np.datetime64` | `np.datetime64("2025-01-01")` | 转换为 int64 ms |

## 集成位置

### 1. ReplayRuntime (`runtime/replay_runtime/runtime.py`)

- **`start_session()`**：强制转换 `start_time_ms` 和 `end_time_ms`
- **`load_dataset()`**：自动检测并归一化数据文件中的时间列
- **`_process_event()`**：强制验证事件时间类型为 int

### 2. 优化服务 (`application/optimization_service/service.py`)

- **`run_task()`**：使用时间权威转换配置中的时间
- **`_run_single_backtest_sync()`**：子进程中也实现统一时间处理逻辑
- **参数传递**：确保多进程调用时传递正确格式的时间

### 3. UnifiedEvent (`infrastructure/event/unified_schema.py`)

- **`__post_init__()`**：自动验证和转换事件中的时间字段
- **`_validate_time_fields()`**：强制时间字段类型检查

## 使用示例

### 在新代码中使用时间权威系统

```python
from infrastructure.time_authority import (
    ensure_time_ms,
    normalize_time_ms,
    check_monotonic,
    TimeSource,
)

# 1. 确保时间是 int64 ms 格式
start_time = ensure_time_ms("2025-01-01", source=TimeSource.API, field_name="start_time")
end_time = ensure_time_ms(1746272000, source=TimeSource.API, field_name="end_time")

# 2. 单调检查
check_monotonic(start_time)
check_monotonic(end_time)

# 3. 在 Runtime 中只使用 int64 ms
result = await runtime.run_backtest(
    start_time_ms=start_time,
    end_time_ms=end_time,
    ...
)
```

### 在 API 层转换时间

```python
from infrastructure.time_authority import ensure_time_ms, TimeSource

@router.post("/backtest")
async def run_backtest(config: BacktestConfig):
    # 转换配置中的时间
    start_time = ensure_time_ms(config.start_date, source=TimeSource.API, field_name="start_date")
    end_time = ensure_time_ms(config.end_date, source=TimeSource.API, field_name="end_date")
    
    # 传递转换后的时间给 Runtime
    result = await backtest_service.run(
        start_time_ms=start_time,
        end_time_ms=end_time,
        ...
    )
```

## 测试

### 测试脚本位置

- **模块测试**：`backend/scripts/test_time_authority_simple.py`
- **API 流程测试**：`backend/scripts/test_time_authority_api.py`
- **集成测试**：`backend/tests/test_infrastructure.py`

### 运行测试

```bash
cd backend
python scripts/test_time_authority_simple.py
```

## 时间类型规范（强制执行）

| 位置 | 允许类型 | 要求 |
|------|---------|------|
| **Runtime 内部** | `int64 ms` | **唯一允许**，禁止其他任何类型 |
| **API 输入** | `str` / `int` / `pd.Timestamp` | 必须在进入 Runtime 前转换 |
| **数据文件** | 任意格式 | 必须在加载时统一转换为 `int64 ms` |
| **输出/展示** | `datetime` / `str` | 仅用于展示，不进入逻辑层 |

## 问题排查

### 常见错误

**错误 1：`TypeError: can only concatenate str (not "int") to str`**

原因：时间是字符串格式，但代码试图进行数值运算

解决：使用 `ensure_time_ms()` 确保时间在进入 Runtime 前转换为 `int64 ms`

**错误 2：时间验证失败**

原因：时间超出了合理范围（1970-01-01 ~ 2050-01-01）

解决：检查时间来源，确保时间格式正确

**错误 3：非单调时间**

原因：检测到时间倒流

解决：检查数据源排序是否正确，调用 `check_monotonic()` 可以发现问题

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      API 层 / Adapter 层                      │
│  接受各种时间格式 (str / pd.Timestamp / datetime / int)     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Time Authority (时间权威)                       │
│  normalize_time_ms() / ensure_time_ms() / validate_time_ms()│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Runtime 层 (内部)                          │
│              仅接受 int64 ms 格式！！！                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  ReplayRuntime / SignalRuntime / ExecutionRuntime       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 总结

时间权威系统解决了以下问题：

1. ✅ **统一时间格式**：所有 Runtime 内部只使用 `int64 ms`
2. ✅ **消除类型错误**：不再有 `str + int` 拼接错误
3. ✅ **提供转换工具**：支持多种时间格式自动转换
4. ✅ **验证和保护**：单调检查、范围验证、来源追踪
5. ✅ **完整集成**：已集成到所有关键路径

现在 Runtime 真正开始工作，之前隐藏的问题都暴露出来并得到了解决！ 🎉
