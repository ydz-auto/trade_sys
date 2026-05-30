"""
Debug index issue
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd


def main():
    from engines.compute.feature.feature_engine import FeatureEngine
    
    symbol = "BTCUSDT"
    timeframe = "1h"
    days = 10
    exchange = "binance"
    
    print("=== Debug Index Issue ===")
    print()
    
    print("Getting research source data...")
    engine_research = FeatureEngine(source="research")
    df_research = engine_research.build_historical_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    print(f"Research data shape: {df_research.shape}")
    print(f"Research index type: {type(df_research.index)}")
    print(f"Research index dtype: {df_research.index.dtype}")
    print(f"Research first 5 index: {list(df_research.index[:5])}")
    print()
    
    print("Getting engine source data...")
    engine_engine = FeatureEngine(source="engine")
    df_engine = engine_engine.build_historical_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    print(f"Engine data shape: {df_engine.shape}")
    print(f"Engine index type: {type(df_engine.index)}")
    print(f"Engine index dtype: {df_engine.index.dtype}")
    print(f"Engine first 5 index: {list(df_engine.index[:5])}")
    print()
    
    print("Research columns sample:")
    print(list(df_research.columns[:20]))
    print()
    
    print("Engine columns sample:")
    print(list(df_engine.columns[:20]))
    print()
    
    print("Checking ret_1 availability:")
    print(f"  ret_1 in research: {'ret_1' in df_research.columns}")
    print(f"  ret_1 in engine: {'ret_1' in df_engine.columns}")
    if 'ret_1' in df_research.columns:
        print(f"  research ret_1 first 10: {list(df_research['ret_1'].head(10))}")
    if 'ret_1' in df_engine.columns:
        print(f"  engine ret_1 first 10: {list(df_engine['ret_1'].head(10))}")


if __name__ == "__main__":
    main()

