"""
Kline Loader - 从 FileDataLakeReader 独立加载 K 线数据

不依赖 research/alpha/features/matrix.py，供 engine standalone 模式使用。

功能：
1. 加载原始 kline 数据
2. 自动 fallback: 1h → 1m resample
3. 截取指定天数
4. 输出标准化 DataFrame: timestamp, open, high, low, close, volume
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_klines(
    exchange: str = "binance",
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    days: int = 90,
) -> pd.DataFrame:
    """
    从 FileDataLakeReader 加载 K 线数据

    Args:
        exchange: 交易所
        symbol: 交易对
        timeframe: K 线周期
        days: 回溯天数

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

    reader = FileDataLakeReader()

    klines = reader.load_klines(exchange, symbol, timeframe=timeframe)

    if klines is None or len(klines) == 0:
        if timeframe != "1m":
            print(f"  [kline_loader] {timeframe}数据不存在，从1m重采样...")
            klines_1m = reader.load_klines(exchange, symbol, timeframe="1m")
            if klines_1m is not None and len(klines_1m) > 0:
                klines = _resample_klines(klines_1m, timeframe)
            else:
                raise ValueError(f"没有1m数据作为fallback for {symbol}")
        else:
            raise ValueError(f"没有{timeframe} klines数据 for {symbol}")

    klines["timestamp"] = pd.to_datetime(klines["timestamp"])
    cutoff = klines["timestamp"].max() - pd.Timedelta(days=days)
    klines = klines[klines["timestamp"] >= cutoff].copy()

    base = klines[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    base = base.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        base[col] = pd.to_numeric(base[col], errors="coerce")

    return base


def _resample_klines(klines_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """将 1m klines 重采样到目标周期"""
    df = klines_1m.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    ohlc = df["open"].resample(timeframe).first()
    high = df["high"].resample(timeframe).max()
    low = df["low"].resample(timeframe).min()
    close = df["close"].resample(timeframe).last()
    volume = df["volume"].resample(timeframe).sum()

    result = pd.DataFrame({
        "timestamp": ohlc.index,
        "open": ohlc.values,
        "high": high.values,
        "low": low.values,
        "close": close.values,
        "volume": volume.values,
    })
    result = result.dropna(subset=["open"]).reset_index(drop=True)

    if "exchange" in klines_1m.columns:
        result["exchange"] = klines_1m["exchange"].iloc[0]
    if "symbol" in klines_1m.columns:
        result["symbol"] = klines_1m["symbol"].iloc[0]
    if "interval" in klines_1m.columns:
        result["interval"] = timeframe

    return result
