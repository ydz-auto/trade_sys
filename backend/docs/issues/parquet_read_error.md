# Issue: Parquet 文件读取失败 - Repetition level histogram size mismatch

## 问题描述

读取 `data_lake` 目录下的 parquet 文件时报错：

```
OSError: Repetition level histogram size mismatch
```

或

```
ArrowTypeError: Unable to merge: Field symbol has incompatible types: string vs dictionary<values=string, indices=int32, ordered=0>
```

## 影响范围

所有 parquet 文件无法正常读取：
- `data_lake/features/1m/`
- `data_lake/features/5m/`
- `data_lake/features/15m/`
- `data_lake/features/binance/`
- `data_lake/crypto/binance/klines/`

## 根本原因

### 1. PyArrow 版本不兼容

- 文件创建时使用：**PyArrow 24.0.0**
- 读取时环境版本：**PyArrow 19.0.0**

通过 `ParquetFile.metadata.created_by` 可查看文件创建版本：
```
Created by: parquet-cpp-arrow version 24.0.0
```

### 2. 文件内部类型不一致

parquet 文件在追加写入时，字符串列（如 `symbol`, `exchange`）使用了不同的编码：
- 第一次写入：`string` 类型
- 后续写入：`dictionary<values=string, indices=int32, ordered=0>` 类型（字典编码）

这导致 PyArrow 无法合并多个 row group 的数据。

## 解决方案

### 方案一：升级 PyArrow（推荐）

```bash
pip install --upgrade pyarrow
```

确保版本 >= 24.0.0

### 方案二：使用安全读取函数

创建 `shared/utils/parquet_reader.py`：

```python
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Optional, Union


def read_parquet_safe(file_path: Union[str, Path]) -> Optional[pd.DataFrame]:
    """
    安全读取 parquet 文件，处理类型不一致问题
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return None
    
    # 先尝试标准方式读取
    try:
        return pd.read_parquet(file_path)
    except Exception:
        pass
    
    # 使用 read_row_group() 逐个读取
    try:
        pf = pq.ParquetFile(file_path)
        dfs = []
        
        for i in range(pf.metadata.num_row_groups):
            try:
                table = pf.read_row_group(i)
                df = table.to_pandas()
                dfs.append(df)
            except Exception as rg_error:
                print(f"Warning: Failed to read row group {i}: {rg_error}")
        
        if dfs:
            result = pd.concat(dfs, ignore_index=True)
            # 统一字符串列类型
            for col in ['symbol', 'exchange', 'interval']:
                if col in result.columns:
                    result[col] = result[col].astype(str)
            return result
        
        return None
        
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
```

使用方式：

```python
from shared.utils.parquet_reader import read_parquet_safe

df = read_parquet_safe("data_lake/features/1m/symbol=BTCUSDT/year=2024/month=01/data.parquet")
```

## 预防措施

### 1. 固定 PyArrow 版本

在 `requirements.txt` 或 `pyproject.toml` 中指定版本：

```
pyarrow>=24.0.0
```

### 2. 写入时统一类型

写入 parquet 时，显式指定 schema，避免字典编码：

```python
import pyarrow as pa
import pyarrow.parquet as pq

schema = pa.schema([
    ('symbol', pa.string()),
    ('exchange', pa.string()),
    # ... 其他字段
])

table = pa.Table.from_pandas(df, schema=schema)
pq.write_table(table, output_path)
```

### 3. 避免追加写入

使用一次性写入而非追加写入，或确保追加时类型一致：

```python
# 不推荐：追加写入可能导致类型不一致
if file_path.exists():
    existing_df = pd.read_parquet(file_path)
    df = pd.concat([existing_df, df])

# 推荐：一次性写入
df.to_parquet(file_path, index=False)
```

## 验证

升级后运行测试：

```bash
python scripts/test_data.py
```

预期输出：

```
Data path: ...data_lake/features/1m/symbol=BTCUSDT/year=2024/month=01/data.parquet
Exists: True
Rows: 44640
Columns: ['datetime', 'mid_price_first', ...]
```

## 相关文件

- 解决方案实现：`shared/utils/parquet_reader.py`
- 测试脚本：`scripts/test_data.py`

## 日期

2026-05-22
