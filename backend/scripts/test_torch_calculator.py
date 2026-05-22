import os
os.environ['TORCH_DEVICE'] = 'cuda'

import sys
sys.path.insert(0, r'E:\00_crypto\00_code\backend')

import torch
import pandas as pd
import time
from pathlib import Path

print('=' * 50)
print('TorchFeatureCalculator GPU Test')
print('=' * 50)

KLINE_PATH = Path(r"E:\00_crypto\00_code\backend\data_lake\crypto\binance\klines\symbol=BTCUSDT\year=2023\month=04\data.parquet")

print(f'\nLoading klines from: {KLINE_PATH}')
df = pd.read_parquet(KLINE_PATH)
print(f'Loaded {len(df)} rows')

print('\n--- Test 1: Import TorchFeatureCalculator ---')
try:
    from domain.feature.torch_calculator import TorchFeatureCalculator
    calc = TorchFeatureCalculator()
    print(f'TorchFeatureCalculator created')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Test 2: compute_batch (GPU) ---')
try:
    start = time.time()
    result = calc.compute_batch(df.head(10000), symbol="BTCUSDT", use_gpu=True)
    elapsed = time.time() - start
    print(f'compute_batch(10k rows) elapsed: {elapsed:.2f}s')
    print(f'Result shape: {result.shape}')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()

print('\n--- Test 3: compute_batch (50k rows) ---')
try:
    start = time.time()
    result = calc.compute_batch(df.head(50000), symbol="BTCUSDT", use_gpu=True)
    elapsed = time.time() - start
    print(f'compute_batch(50k rows) elapsed: {elapsed:.2f}s')
    print(f'Result shape: {result.shape}')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()

print('\n--- Test 4: compute_batch (full 43k rows) ---')
try:
    start = time.time()
    result = calc.compute_batch(df, symbol="BTCUSDT", use_gpu=True)
    elapsed = time.time() - start
    print(f'compute_batch(43k rows) elapsed: {elapsed:.2f}s')
    print(f'Result shape: {result.shape}')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()

print('\n--- Test 5: Cleanup ---')
try:
    torch.cuda.empty_cache()
    print('GPU cache cleared')
except Exception as e:
    print(f'FAILED: {e}')

print('\n' + '=' * 50)
print('TorchFeatureCalculator GPU test completed!')
print('=' * 50)
