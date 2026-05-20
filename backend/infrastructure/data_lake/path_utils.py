"""
Data Lake Path Utilities - 数据湖路径工具

提供统一的数据湖路径访问接口，支持 SMB 和本地路径配置化
"""

from pathlib import Path
from typing import Optional

from config.loader import get_config


def get_data_lake_root() -> Path:
    """
    获取数据湖根目录路径
    
    根据配置决定使用 SMB 路径还是本地路径
    
    Returns:
        Path: 数据湖根目录路径
    """
    config = get_config()
    data_lake_config = config.infra.data_lake
    
    if data_lake_config.use_smb:
        smb_url = data_lake_config.smb_url
        smb_path = smb_url.replace("smb://", "")
        return Path(f"/mnt/{smb_path}")
    else:
        local_path = data_lake_config.local_path
        if local_path.startswith("./"):
            project_root = Path(__file__).parent.parent
            return project_root / local_path[2:]
        return Path(local_path)


def get_data_lake_subpath(*parts: str) -> Path:
    """
    获取数据湖子路径
    
    Args:
        *parts: 路径组成部分
        
    Returns:
        Path: 完整的数据湖子路径
        
    Example:
        >>> get_data_lake_subpath("features", "binance", "BTCUSDT")
        Path("/mnt/192.168.1.14/00_crypto/00_code/backend/data_lake/features/binance/BTCUSDT")
    """
    root = get_data_lake_root()
    return root.joinpath(*parts)


def get_features_path(exchange: Optional[str] = None, symbol: Optional[str] = None) -> Path:
    """
    获取特征数据路径
    
    Args:
        exchange: 交易所名称 (如 "binance", "okx")
        symbol: 交易对符号 (如 "BTCUSDT")
        
    Returns:
        Path: 特征数据路径
    """
    parts = ["features"]
    if exchange:
        parts.append(exchange)
    if symbol:
        parts.append(symbol)
    return get_data_lake_subpath(*parts)


def get_models_path() -> Path:
    """获取模型存储路径"""
    return get_data_lake_subpath("models")


def get_research_path() -> Path:
    """获取研究结果存储路径"""
    return get_data_lake_subpath("research")


def get_crypto_data_path(exchange: str, data_type: str) -> Path:
    """
    获取加密货币数据路径
    
    Args:
        exchange: 交易所名称 ("binance", "okx")
        data_type: 数据类型 ("klines", "funding", "oi", "trades", "liquidation")
        
    Returns:
        Path: 数据路径
    """
    return get_data_lake_subpath("crypto", exchange, data_type)


_data_lake_root_cache: Optional[Path] = None


def get_data_lake_root_cached() -> Path:
    """
    获取数据湖根目录路径（带缓存）
    
    用于频繁访问场景，避免重复加载配置
    
    Returns:
        Path: 数据湖根目录路径
    """
    global _data_lake_root_cache
    if _data_lake_root_cache is None:
        _data_lake_root_cache = get_data_lake_root()
    return _data_lake_root_cache
