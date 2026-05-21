"""测试数据读取"""
import pandas as pd
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
        try:
            df = pd.read_parquet(data_path, engine='pyarrow')
            print(f"Rows: {len(df)}")
            print(f"Columns: {list(df.columns)}")
            print(f"Date range: {df.iloc[0].get('timestamp', 'N/A')} to {df.iloc[-1].get('timestamp', 'N/A')}")
        except Exception as e:
            print(f"Error: {e}")
