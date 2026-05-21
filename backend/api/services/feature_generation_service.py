"""
Feature Generation Service - 特征生成服务

从Trades历史数据批量提取多周期特征
使用 aggregation_service 的历史特征提取器
"""
import asyncio
from typing import List, Dict, Any, Optional

from infrastructure.logging import get_logger

from services.aggregation_service import (
    extract_historical_features,
    get_feature_status as get_aggregation_feature_status
)

logger = get_logger("api.feature_generation_service")


async def generate_symbol_features(
    symbol: str,
    years: List[int],
    intervals: List[str],
    force_regenerate: bool = False
) -> List[Dict[str, Any]]:
    """生成币种的特征数据"""
    logger.info(f"Starting feature generation for {symbol}")
    logger.info(f"Years: {years}, Intervals: {intervals}")

    results = await extract_historical_features(symbol, years, intervals)

    return results


async def get_feature_status(symbol: str, interval: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取特征状态"""
    return await get_aggregation_feature_status(symbol, interval)


async def clear_feature_cache(symbol: str, interval: Optional[str] = None) -> int:
    """清除特征缓存"""
    from pathlib import Path
    import shutil

    FEATURES_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake\features")
    cleared = 0

    intervals = [interval] if interval else [
        "1m", "5m", "15m", "1h", "4h", "1d"
    ]

    for intvl in intervals:
        cache_path = FEATURES_ROOT / intvl / f"symbol={symbol}"
        if cache_path.exists():
            shutil.rmtree(cache_path)
            cleared += 1

    return cleared
