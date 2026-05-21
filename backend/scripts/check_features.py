#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

features_dir = Path(r'e:\00_crypto\00_code\backend\data_lake\features\binance')

for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    fpath = features_dir / symbol / 'features.parquet'
    if fpath.exists():
        df = pd.read_parquet(fpath)
        print(f'{symbol}:')
        print(f'  时间范围: {df["timestamp"].min()} ~ {df["timestamp"].max()}')
        print(f'  记录数: {len(df):,}')
        print(f'  特征列: {len(df.columns)}')
        print()
