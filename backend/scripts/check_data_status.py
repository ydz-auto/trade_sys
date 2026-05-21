#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

data_root = Path(r'e:\00_crypto\00_code\backend\data_lake\crypto\binance')

print("=" * 70)
print("数据湖状态检查")
print("=" * 70)

print("\n【K线数据 - Futures】")
for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    klines_dir = data_root / "klines" / f"symbol={symbol}"
    if klines_dir.exists():
        years = sorted([d.name for d in klines_dir.iterdir() if d.is_dir()])
        print(f"  {symbol}: {years}")

print("\n【K线数据 - Spot】")
for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    spot_dir = data_root / "spot_klines" / f"symbol={symbol}"
    if spot_dir.exists():
        years = sorted([d.name for d in spot_dir.iterdir() if d.is_dir()])
        print(f"  {symbol}: {years}")

print("\n【Funding 数据】")
for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    fpath = data_root / "funding" / f"symbol={symbol}" / "data.parquet"
    if fpath.exists():
        df = pd.read_parquet(fpath)
        print(f"  {symbol}: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

print("\n【Open Interest 数据】")
for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    fpath = data_root / "oi" / f"symbol={symbol}" / "data.parquet"
    if fpath.exists():
        df = pd.read_parquet(fpath)
        print(f"  {symbol}: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

print("\n【特征数据】")
features_dir = Path(r'e:\00_crypto\00_code\backend\data_lake\features\binance')
for symbol in ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']:
    fpath = features_dir / symbol / "features.parquet"
    if fpath.exists():
        df = pd.read_parquet(fpath)
        print(f"  {symbol}: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
