#!/usr/bin/env python3
"""检查数据湖里的funding和OI数据结构"""
import sys
import os
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

print("=" * 80)
print("检查数据结构")
print("=" * 80)

# 检查funding数据
funding_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "funding" / "symbol=BTCUSDT" / "data.parquet"
print(f"\n1. 检查funding数据: {funding_path}")
if funding_path.exists():
    df_funding = pd.read_parquet(funding_path)
    print(f"   - 行数: {len(df_funding)}")
    print(f"   - 列数: {len(df_funding.columns)}")
    print(f"   - 列名: {df_funding.columns.tolist()}")
    print("\n   前5行数据:")
    print(df_funding.head())
    print(f"\n   时间范围: {df_funding['timestamp'].min()} 到 {df_funding['timestamp'].max()}")
else:
    print("   - 文件不存在")

# 检查OI数据
oi_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "oi" / "symbol=BTCUSDT" / "data.parquet"
print(f"\n2. 检查OI数据: {oi_path}")
if oi_path.exists():
    df_oi = pd.read_parquet(oi_path)
    print(f"   - 行数: {len(df_oi)}")
    print(f"   - 列数: {len(df_oi.columns)}")
    print(f"   - 列名: {df_oi.columns.tolist()}")
    print("\n   前5行数据:")
    print(df_oi.head())
    print(f"\n   时间范围: {df_oi['timestamp'].min()} 到 {df_oi['timestamp'].max()}")
else:
    print("   - 文件不存在")

print("\n" + "=" * 80)
