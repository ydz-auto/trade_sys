"""
修复 parquet 读取问题

问题原因：parquet 文件中存在类型不一致（string vs dictionary encoded string）
解决方案：使用 read_row_group() 逐个读取 row group
"""
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Optional, Union


def read_parquet_safe(file_path: Union[str, Path]) -> Optional[pd.DataFrame]:
    """
    安全读取 parquet 文件，处理类型不一致问题

    Args:
        file_path: parquet 文件路径

    Returns:
        DataFrame 或 None（如果读取失败）
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return None

    try:
        return pd.read_parquet(file_path)
    except Exception as e:
        pass

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
            for col in ['symbol', 'exchange', 'interval']:
                if col in result.columns:
                    result[col] = result[col].astype(str)
            return result

        return None

    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


if __name__ == "__main__":
    test_files = [
        Path(r"e:\00_crypto\00_code\backend\data_lake\crypto\binance\klines\symbol=BTCUSDT\year=2022\month=01\data.parquet"),
        Path(r"e:\00_crypto\00_code\backend\data_lake\features\1m\symbol=BTCUSDT\year=2024\month=01\data.parquet"),
        Path(r"e:\00_crypto\00_code\backend\data_lake\features\binance\BTCUSDT\features.parquet"),
    ]

    for test_file in test_files:
        print(f"\n{'='*60}")
        print(f"Reading: {test_file.name}")

        df = read_parquet_safe(test_file)

        if df is not None:
            print(f"Success! Rows: {len(df)}, Columns: {len(df.columns)}")
            print(f"Columns: {list(df.columns)[:5]}...")
        else:
            print("Failed to read file")
