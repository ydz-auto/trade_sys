"""
Debug why SMA and RSI have differences
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd
import numpy as np


def main():
    from engines.compute.feature.feature_engine import FeatureEngine
    
    symbol = "BTCUSDT"
    timeframe = "1h"
    days = 10
    exchange = "binance"
    
    print("=== Getting research source data ===")
    engine_research = FeatureEngine(source="research")
    df_research = engine_research.build_historical_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    
    print("\n=== Getting engine source data ===")
    engine_engine = FeatureEngine(source="engine")
    df_engine = engine_engine.build_historical_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    
    # 查看 SMA
    print("\n=== SMA 20 Comparison ===")
    print("First 30 values:")
    compare_df = pd.DataFrame({
        "Close": df_research["close"],
        "Research_SMA": df_research["sma_20"],
        "Engine_SMA": df_engine["sma_20"],
        "Diff": df_engine["sma_20"] - df_research["sma_20"]
    })
    print(compare_df.head(30).to_string())
    
    print("\n=== RSI 14 Comparison ===")
    print("First 30 values:")
    compare_df_rsi = pd.DataFrame({
        "Close": df_research["close"],
        "Research_RSI": df_research["rsi_14"],
        "Engine_RSI": df_engine["rsi_14"],
        "Diff": df_engine["rsi_14"] - df_research["rsi_14"]
    })
    print(compare_df_rsi.head(30).to_string())
    
    # 自己手动计算 SMA
    print("\n=== Manual Calculation ===")
    manual_sma = df_research["close"].rolling(20).mean()
    compare_df["Manual_SMA"] = manual_sma
    compare_df["Engine_Minus_Manual"] = df_engine["sma_20"] - manual_sma
    compare_df["Research_Minus_Manual"] = df_research["sma_20"] - manual_sma
    print(compare_df[["Close", "Research_SMA", "Engine_SMA", "Manual_SMA", 
                       "Research_Minus_Manual", "Engine_Minus_Manual"]].head(30).to_string())


if __name__ == "__main__":
    main()
