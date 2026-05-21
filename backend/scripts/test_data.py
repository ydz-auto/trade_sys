"""测试数据读取"""
import sys
sys.path.insert(0, r"e:\00_crypto\00_code\backend")

from shared.utils.parquet_reader import read_parquet_safe
from pathlib import Path

paths = [
    Path(r"e:\00_crypto\00_code\backend\data_lake\features\1m\symbol=BTCUSDT\year=2024\month=01\data.parquet"),
    Path(r"e:\00_crypto\00_code\backend\data_lake\features\5m\symbol=BTCUSDT\year=2024\month=01\data.parquet"),
    Path(r"e:\00_crypto\00_code\backend\data_lake\features\15m\symbol=BTCUSDT\year=2024\month=01\data.parquet"),
]

for data_path in paths:
    print(f"\nData path: {data_path}")
    print(f"Exists: {data_path.exists()}")
    
    if data_path.exists():
        df = read_parquet_safe(data_path)
        if df is not None:
            print(f"Rows: {len(df)}")
            print(f"Columns: {list(df.columns)}")
            if 'timestamp' in df.columns:
                print(f"Date range: {df.iloc[0].get('timestamp', 'N/A')} to {df.iloc[-1].get('timestamp', 'N/A')}")
        else:
            print("Failed to read file")
