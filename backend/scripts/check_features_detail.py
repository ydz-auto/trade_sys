#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

features_dir = Path(r'e:\00_crypto\00_code\backend\data_lake\features\binance')

print('='*80)
print('特征文件状态')
print('='*80)

for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    fpath = features_dir / symbol / 'features.parquet'
    if fpath.exists():
        df = pd.read_parquet(fpath)
        size_mb = fpath.stat().st_size / 1024 / 1024
        print(f'\n{symbol}:')
        print(f'  时间范围: {df["timestamp"].min()} ~ {df["timestamp"].max()}')
        print(f'  记录数: {len(df):,}')
        print(f'  特征数: {len(df.columns)}')
        print(f'  文件大小: {size_mb:.1f} MB')
        print(f'  特征列: {list(df.columns)}')
