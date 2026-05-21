#!/usr/bin/env python3
import os
from pathlib import Path

trades_dir = Path(r'e:\00_crypto\00_code\backend\data_lake\crypto\binance\trades')

symbols = ['BTCUSDT', 'ETCUSDT', 'ZECUSDT', 'SOLUSDT']
years = list(range(2019, 2027))  # 2019-2026

print('='*70)
print('Trades 下载进度')
print('='*70)

total_tasks = 0
success = 0
in_progress = 0
missing = 0

for symbol in symbols:
    print(f'\n{symbol}:')
    for year in years:
        status = []
        for month in range(1, 13):
            mm = f'{month:02d}'
            month_dir = trades_dir / f'symbol={symbol}' / f'year={year}' / f'month={mm}'
            parquet_file = month_dir / 'data.parquet'
            csv_files = list(month_dir.glob('*.csv'))
            zip_files = list(month_dir.glob('*.zip'))
            
            total_tasks += 1
            
            if parquet_file.exists():
                status.append('✓')
                success += 1
            elif csv_files or zip_files:
                status.append('⏳')
                in_progress += 1
            else:
                status.append('·')
                missing += 1
        
        if any(c != '·' for c in status):
            print(f'  {year}: {" ".join(status)}')

print(f'\n{"="*70}')
print(f'总计: {success}/{total_tasks} ({success/total_tasks*100:.1f}% 完成)')
print(f'成功: {success} | 进行中: {in_progress} | 未开始: {missing}')
print(f'{"="*70}')
