import pandas as pd
import time
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.feature.unified_calculator import UnifiedFeatureCalculator

KLINE_PATH = Path(r"E:\00_crypto\00_code\backend\data_lake\crypto\binance\klines\symbol=BTCUSDT\year=2023\month=04\data.parquet")
CACHE_PATH = Path(r"E:\00_crypto\00_code\backend\data_lake\features_cache")

print("Loading klines data...")
df = pd.read_parquet(KLINE_PATH)
print(f"Loaded {len(df)} rows")

print()
print("Computing features with GPU...")
calc = UnifiedFeatureCalculator(use_gpu=True)
print(f"GPU available: {calc._gpu_available}")

start = time.time()
features_df = calc.compute_batch(df, symbol="BTCUSDT", use_gpu=True)
elapsed = time.time() - start
print(f"Feature extraction: {elapsed:.2f}s")

FEATURE_COLS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "rsi_7", "rsi_14", "rsi_21",
    "sma_5", "sma_10", "sma_20", "sma_30", "sma_50", "sma_100",
    "ema_5", "ema_10", "ema_20", "ema_30",
    "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_middle", "bb_lower",
    "atr_14",
    "momentum_10", "momentum_20",
    "volume_ratio",
]

existing_cols = [c for c in FEATURE_COLS if c in features_df.columns]
features_df = features_df[existing_cols].copy()
print(f"Saving {len(features_df)} rows, {len(existing_cols)} features to cache...")

CACHE_PATH.mkdir(parents=True, exist_ok=True)
out_path = CACHE_PATH / "features_opt.parquet"
features_df.to_parquet(out_path, index=False)
print(f"Saved to: {out_path}")
print(f"File size: {out_path.stat().st_size / 1024 / 1024:.2f} MB")
