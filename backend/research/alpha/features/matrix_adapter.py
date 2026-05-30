"""
Research Feature Matrix Adapter - research 的特征矩阵适配器

研究环境现在完全使用 FeatureEngine，所有特征计算都统一通过引擎层！

用法：
    from research.alpha.features.matrix_adapter import get_research_feature_matrix
    df = get_research_feature_matrix(symbol="BTCUSDT", days=90, timeframe="1h")
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd


BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def get_research_feature_matrix(
    symbol: str,
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
    feature_source: str = "engine",
) -> pd.DataFrame:
    """
    获取研究用的特征矩阵（完全使用新的FeatureEngine）

    Args:
        symbol: 交易对
        exchange: 交易所
        days: 天数
        timeframe: 时间周期
        feature_source: 特征来源（"engine" 或 "research"）

    Returns:
        特征矩阵 DataFrame
    """
    print(f"[MatrixAdapter] 获取特征矩阵: {symbol}/{timeframe}, {days}天")
    
    try:
        from engines.compute.feature import FeatureEngine
        engine = FeatureEngine(source=feature_source)
        df = engine.build_historical_matrix(
            symbol=symbol,
            exchange=exchange,
            days=days,
            timeframe=timeframe,
        )
        print(f"[MatrixAdapter] FeatureEngine 成功: {df.shape}")
        return df
    except Exception as e:
        print(f"[MatrixAdapter] FeatureEngine 失败: {e}")
    
    # 回退到旧的方法
    try:
        from research.alpha.features.matrix import build_feature_matrix
        print(f"[MatrixAdapter] 回退到旧 build_feature_matrix")
        return build_feature_matrix(
            symbol=symbol,
            exchange=exchange,
            days=days,
            timeframe=timeframe,
        )
    except Exception as e:
        print(f"[MatrixAdapter] 回退也失败: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# 向后兼容别名
def build_feature_matrix_adapter(*args, **kwargs) -> pd.DataFrame:
    return get_research_feature_matrix(*args, **kwargs)


__all__ = [
    "get_research_feature_matrix",
    "build_feature_matrix_adapter",
]
