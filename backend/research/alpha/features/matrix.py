"""
Feature Matrix - 特征矩阵构建

完全使用新的FeatureEngine架构构建特征矩阵！
"""

import sys
from pathlib import Path
from typing import Optional, List

import pandas as pd

from engines.compute.feature import FeatureEngine, get_engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_feature_matrix(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
    exclude_sources: Optional[List[str]] = None,
    use_engine: bool = True,
) -> pd.DataFrame:
    """
    构建特征矩阵 - 使用新的FeatureEngine架构
    
    Args:
        symbol: 交易对
        exchange: 交易所
        days: 回看天数
        timeframe: K线周期
        exclude_sources: 排除的数据源
        use_engine: 是否使用FeatureEngine（默认True）
    
    Returns:
        特征矩阵 DataFrame
    """
    print(f"[FeatureMatrix] 构建特征矩阵: {symbol}/{timeframe}, {days}天")
    
    # 使用 FeatureEngine
    if use_engine:
        try:
            engine = FeatureEngine()
            df = engine.build_historical_matrix(
                symbol=symbol,
                exchange=exchange,
                days=days,
                timeframe=timeframe,
                exclude_sources=exclude_sources
            )
            print(f"[FeatureMatrix] FeatureEngine构建成功: {df.shape}")
            return df
        except Exception as e:
            print(f"[FeatureMatrix] FeatureEngine失败: {e}")
    
    # 回退到传统方式（保留向后兼容性）
    print(f"[FeatureMatrix] 回退到传统方式...")
    return _build_fallback(symbol, exchange, days, timeframe, exclude_sources)


def _build_fallback(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
    exclude_sources: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    回退方案：从FileDataLakeReader手动构建特征矩阵
    保留此函数是为了向后兼容性
    """
    try:
        from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
    except ImportError:
        print(f"[FeatureMatrix] FileDataLakeReader导入失败")
        return pd.DataFrame()
    
    exclude_sources = exclude_sources or []
    exclude_set = {s.lower().strip() for s in exclude_sources}
    
    reader = FileDataLakeReader()
    
    # 加载基础K线
    klines = None
    if "klines" not in exclude_set:
        klines = _safe_load(reader.read_klines, exchange, symbol, timeframe, days=days)
        if klines is not None and not klines.empty:
            klines = klines.sort_values("timestamp").reset_index(drop=True)
    
    # 加载资金费率
    funding = None
    if "funding" not in exclude_set:
        funding = _safe_load(reader.read_funding, exchange, symbol, timeframe, klines)
    
    # 加载持仓量
    oi = None
    if "oi" not in exclude_set:
        oi = _safe_load(reader.read_open_interest, exchange, symbol, timeframe, klines)
    
    # 加载订单簿
    orderbook = None
    if "orderbook" not in exclude_set:
        orderbook = _safe_load(reader.read_orderbook, exchange, symbol, timeframe, klines)
    
    # 加载清算
    liquidations = None
    if "liquidations" not in exclude_set:
        liquidations = _safe_load(reader.read_liquidations, exchange, symbol, timeframe, klines)
    
    # 合并所有数据源
    df = klines if (klines is not None and not klines.empty) else pd.DataFrame()
    if df.empty:
        return df
    
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    if funding is not None and not funding.empty:
        df = df.merge(funding, on="timestamp", how="left")
    
    if oi is not None and not oi.empty:
        df = df.merge(oi, on="timestamp", how="left")
    
    if orderbook is not None and not orderbook.empty:
        df = df.merge(orderbook, on="timestamp", how="left")
    
    if liquidations is not None and not liquidations.empty:
        df = df.merge(liquidations, on="timestamp", how="left")
    
    return df


def _safe_load(func, *args, **kwargs):
    """安全加载数据"""
    try:
        result = func(*args, **kwargs)
        if result is not None and hasattr(result, "empty"):
            return result if not result.empty else None
        return result
    except Exception as e:
        print(f"[FeatureMatrix] 数据加载失败: {e}")
        return None


# 为了向后兼容，保留原始的函数别名
def build_historical_matrix(*args, **kwargs):
    return build_feature_matrix(*args, **kwargs)


__all__ = [
    "build_feature_matrix",
    "build_historical_matrix"
]
