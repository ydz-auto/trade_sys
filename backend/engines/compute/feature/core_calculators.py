"""
核心特征计算函数 - 无状态纯函数
"""
from typing import Dict, List, Optional
import pandas as pd
import numpy as np


def compute_rsi(prices: np.ndarray, periods: List[int] = None) -> Dict[str, Optional[float]]:
    """
    计算 RSI
    
    Args:
        prices: 价格数组
        periods: RSI 周期列表，默认 [7, 14, 21]
    
    Returns:
        RSI 结果字典
    """
    if periods is None:
        periods = [7, 14, 21]
    
    result = {}
    prices = np.asarray(prices)
    
    for period in periods:
        if len(prices) < period + 1:
            result[f"rsi_{period}"] = None
            continue
        
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1 + rs))
        
        result[f"rsi_{period}"] = rsi
    
    return result


def compute_sma(prices: np.ndarray, windows: List[int] = None) -> Dict[str, Optional[float]]:
    """
    计算 SMA
    
    Args:
        prices: 价格数组
        windows: SMA 窗口列表，默认 [10, 20, 50, 100]
    
    Returns:
        SMA 结果字典
    """
    if windows is None:
        windows = [10, 20, 50, 100]
    
    result = {}
    prices = np.asarray(prices)
    
    for window in windows:
        if len(prices) >= window:
            result[f"sma_{window}"] = float(np.mean(prices[-window:]))
        else:
            result[f"sma_{window}"] = None
    
    return result


def compute_ema(prices: np.ndarray, spans: List[int] = None) -> Dict[str, Optional[float]]:
    """
    计算 EMA
    
    Args:
        prices: 价格数组
        spans: EMA 跨度列表，默认 [10, 20, 50]
    
    Returns:
        EMA 结果字典
    """
    if spans is None:
        spans = [10, 20, 50]
    
    result = {}
    prices = np.asarray(prices)
    
    for span in spans:
        if len(prices) >= span:
            ema = pd.Series(prices).ewm(span=span, adjust=False).mean().iloc[-1]
            result[f"ema_{span}"] = float(ema)
        else:
            result[f"ema_{span}"] = None
    
    return result


def compute_macd(prices: np.ndarray) -> Dict[str, Optional[float]]:
    """
    计算 MACD
    
    Args:
        prices: 价格数组
    
    Returns:
        MACD 结果字典: {"macd": ..., "macd_signal": ..., "macd_hist": ...}
    """
    prices = np.asarray(prices)
    
    if len(prices) < 35:
        return {"macd": None, "macd_signal": None, "macd_hist": None}
    
    series = pd.Series(prices)
    ema_fast = series.ewm(span=12, adjust=False).mean()
    ema_slow = series.ewm(span=26, adjust=False).mean()
    
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    
    return {
        "macd": float(macd.iloc[-1]),
        "macd_signal": float(macd_signal.iloc[-1]),
        "macd_hist": float(macd_hist.iloc[-1]),
    }


def compute_bollinger(prices: np.ndarray, window: int = 20) -> Dict[str, Optional[float]]:
    """
    计算布林带
    
    Args:
        prices: 价格数组
        window: 布林带窗口，默认 20
    
    Returns:
        布林带结果字典
    """
    prices = np.asarray(prices)
    
    if len(prices) < window:
        return {"bb_upper": None, "bb_middle": None, "bb_lower": None, "bb_width": None}
    
    recent = prices[-window:]
    sma = np.mean(recent)
    std = np.std(recent)
    
    return {
        "bb_upper": sma + 2 * std,
        "bb_middle": sma,
        "bb_lower": sma - 2 * std,
        "bb_width": 4 * std / sma if sma > 0 else 0.0,
    }


def compute_volume_ratio(volumes: np.ndarray, window: int = 20) -> Dict[str, Optional[float]]:
    """
    计算成交量比率
    
    Args:
        volumes: 成交量数组
        window: 窗口大小，默认 20
    
    Returns:
        成交量比率结果字典
    """
    volumes = np.asarray(volumes)
    
    if len(volumes) < window:
        return {"volume_ratio": None, "volume_ma": None}
    
    current_vol = volumes[-1]
    avg_vol = np.mean(volumes[-window:])
    
    return {
        "volume_ratio": current_vol / avg_vol if avg_vol > 0 else 1.0,
        "volume_ma": avg_vol,
    }


def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Dict[str, Optional[float]]:
    """
    计算 ATR
    
    Args:
        highs: 最高价数组
        lows: 最低价数组
        closes: 收盘价数组
        period: ATR 周期，默认 14
    
    Returns:
        ATR 结果字典
    """
    highs = np.asarray(highs)
    lows = np.asarray(lows)
    closes = np.asarray(closes)
    
    if len(closes) < period + 1:
        return {"atr_14": None}
    
    tr_list = []
    for i in range(1, min(period + 1, len(closes))):
        tr = max(
            highs[-i] - lows[-i],
            abs(highs[-i] - closes[-i - 1]),
            abs(lows[-i] - closes[-i - 1]),
        )
        tr_list.append(tr)
    
    atr = np.mean(tr_list) if tr_list else 0.0
    
    return {"atr_14": atr}


def compute_momentum(prices: np.ndarray, period: int = 10) -> Dict[str, Optional[float]]:
    """
    计算动量
    
    Args:
        prices: 价格数组
        period: 动量周期，默认 10
    
    Returns:
        动量结果字典
    """
    prices = np.asarray(prices)
    
    if len(prices) < period + 1:
        return {"momentum_10": None}
    
    momentum_10 = (prices[-1] - prices[-period - 1]) / prices[-period - 1] if prices[-period - 1] > 0 else 0.0
    
    return {"momentum_10": momentum_10}


def compute_all_features(
    prices: np.ndarray,
    volumes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray
) -> Dict[str, Optional[float]]:
    """
    计算所有特征
    
    Args:
        prices: 收盘价数组
        volumes: 成交量数组
        highs: 最高价数组
        lows: 最低价数组
    
    Returns:
        所有特征结果字典
    """
    features = {}
    features.update(compute_rsi(prices))
    features.update(compute_sma(prices))
    features.update(compute_ema(prices))
    features.update(compute_macd(prices))
    features.update(compute_bollinger(prices))
    features.update(compute_volume_ratio(volumes))
    features.update(compute_atr(highs, lows, prices))
    features.update(compute_momentum(prices))
    return features
