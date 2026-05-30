"""
多进程安全工具模块

解决 Windows 下 pandas+pyarrow+multiprocessing.spawn 导致的 Access Violation (0xC0000005) 问题

核心问题：在 Windows 下使用 multiprocessing.spawn 传递包含 pyarrow 类型的 DataFrame 时，如果没有
显式指定 dtype，很容易触发访问冲突错误。

本模块提供以下功能：
1. clean_dataframe_for_multiprocessing - 清理 DataFrame 以确保多进程安全
2. safe_pickle_dataframe - 安全地序列化 DataFrame
3. ensure_multiprocessing_safe - 确保任何数据在传递给多进程前是安全的
"""

import pandas as pd
import numpy as np
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


def clean_dataframe_for_multiprocessing(df: pd.DataFrame) -> pd.DataFrame:
    """
    清理 DataFrame 以确保多进程安全
    
    这是解决 Windows 下 pandas+pyarrow+multiprocessing.spawn Access Violation 的关键方法
    
    Args:
        df: 要清理的 DataFrame
        
    Returns:
        清理后的安全 DataFrame
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # 1. 强制转换所有 Arrow 类型和扩展类型
    df = _convert_arrow_and_extension_types(df)
    
    # 2. 确保所有列都有明确的、安全的 dtype
    df = _enforce_safe_dtypes(df)
    
    # 3. 重置索引确保连续性
    df = df.reset_index(drop=True)
    
    # 4. 确保没有剩余的 object 类型包含复杂对象
    df = _sanitize_object_columns(df)
    
    return df


def _convert_arrow_and_extension_types(df: pd.DataFrame) -> pd.DataFrame:
    """转换 Arrow 类型和 pandas 扩展类型到标准类型"""
    df = df.copy()
    for col in df.columns:
        try:
            col_type = str(df[col].dtype)
            
            if "arrow" in col_type.lower() or "string" in col_type.lower():
                # 转换字符串类型
                df[col] = df[col].astype(str)
            elif df[col].dtype == "boolean":
                # 转换布尔类型
                df[col] = df[col].astype(bool)
            elif df[col].dtype in ["Int64", "Int32", "Int16", "Int8"]:
                # 转换可空整数类型
                df[col] = df[col].astype("int64")
            elif df[col].dtype in ["Float64", "Float32"]:
                # 转换可空浮点类型
                df[col] = df[col].astype("float64")
            elif hasattr(df[col].dtype, "name") and "Arrow" in df[col].dtype.name:
                # 处理其他 Arrow 类型
                try:
                    df[col] = df[col].astype(str)
                except Exception:
                    # 如果无法转换为字符串，尝试转换为数值
                    try:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    except Exception:
                        # 最后手段：转为字符串
                        df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else x)
        except Exception as e:
            logger.debug(f"Failed to convert column {col}: {e}")
            try:
                # 尝试安全的回退方案
                df[col] = df[col].astype(str)
            except Exception:
                pass
    
    return df


def _enforce_safe_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """确保所有列都有明确的、安全的 dtype"""
    df = df.copy()
    for col in df.columns:
        try:
            if pd.api.types.is_object_dtype(df[col]):
                # 检查是否是字符串或混合类型
                try:
                    # 尝试转换为数值类型
                    numeric = pd.to_numeric(df[col], errors="coerce")
                    if not numeric.isna().all():
                        df[col] = numeric
                    else:
                        # 保持为字符串
                        df[col] = df[col].astype(str)
                except Exception:
                    # 保持为字符串
                    df[col] = df[col].astype(str)
            elif pd.api.types.is_integer_dtype(df[col]):
                df[col] = df[col].astype("int64")
            elif pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].astype("float64")
            elif pd.api.types.is_bool_dtype(df[col]):
                df[col] = df[col].astype(bool)
            elif pd.api.types.is_datetime64_dtype(df[col]):
                # 日期时间类型保持不变，但确保是 naive
                if hasattr(df[col].dtype, "tz") and df[col].dtype.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)
        except Exception as e:
            logger.debug(f"Failed to enforce dtype for column {col}: {e}")
            # 如果失败，至少确保是字符串类型
            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass
    
    return df


def _sanitize_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    """清理 object 类型的列，确保不包含复杂对象"""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            try:
                # 尝试确保所有值都是可序列化的简单类型
                df[col] = df[col].apply(
                    lambda x: str(x) if not isinstance(x, (int, float, bool, str, type(None))) else x
                )
            except Exception as e:
                logger.debug(f"Failed to sanitize object column {col}: {e}")
    
    return df


def ensure_multiprocessing_safe(data: Any) -> Any:
    """
    确保任何数据在传递给多进程前是安全的
    
    Args:
        data: 任何类型的数据
        
    Returns:
        安全的数据
    """
    if isinstance(data, pd.DataFrame):
        return clean_dataframe_for_multiprocessing(data)
    elif isinstance(data, pd.Series):
        return clean_dataframe_for_multiprocessing(data.to_frame()).iloc[:, 0]
    elif isinstance(data, dict):
        return {k: ensure_multiprocessing_safe(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [ensure_multiprocessing_safe(item) for item in data]
    else:
        return data


def safe_pickle_dataframe(df: pd.DataFrame) -> bytes:
    """
    安全地序列化 DataFrame
    
    Args:
        df: 要序列化的 DataFrame
        
    Returns:
        序列化后的数据
    """
    import pickle
    safe_df = clean_dataframe_for_multiprocessing(df)
    return pickle.dumps(safe_df)


def safe_unpickle_dataframe(data: bytes) -> pd.DataFrame:
    """
    安全地反序列化 DataFrame
    
    Args:
        data: 序列化的数据
        
    Returns:
        反序列化后的 DataFrame
    """
    import pickle
    df = pickle.loads(data)
    return clean_dataframe_for_multiprocessing(df)


class MultiprocessingSafeDataFrameWrapper:
    """
    DataFrame 包装器，确保在传递给多进程时是安全的
    """
    
    def __init__(self, df: pd.DataFrame):
        self._df = clean_dataframe_for_multiprocessing(df)
    
    def get(self) -> pd.DataFrame:
        return self._df
    
    def __getstate__(self):
        # 确保在 pickling 时使用安全版本
        return {"_df": clean_dataframe_for_multiprocessing(self._df)}
    
    def __setstate__(self, state):
        self._df = clean_dataframe_for_multiprocessing(state["_df"])
