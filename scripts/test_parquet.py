
#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from infrastructure.storage.parquet_reader import read_parquet_safe
from pathlib import Path

test_file = Path(r"e:\00_crypto\00_code\backend\data_lake\crypto\binance\klines\symbol=BTCUSDT\year=2022\month=01\data.parquet")
df = read_parquet_safe(test_file)

print(f"Loaded {len(df)} rows")
print(df.head())
print("\nColumns:")
print(df.columns.tolist())

