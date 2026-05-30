"""
Feature Cache - 特征计算缓存

避免重复计算，提高性能
"""

from typing import Dict, Optional
import pandas as pd
import hashlib
import pickle
from pathlib import Path


class FeatureCache:
    """特征计算缓存"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self._memory_cache: Dict[str, pd.Series] = {}
        self._df_signature: Optional[str] = None
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_signature(self, df: pd.DataFrame) -> str:
        """计算 DataFrame 的签名"""
        sig_data = {
            "len": len(df),
            "cols": list(df.columns),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
        }
        sig_str = pickle.dumps(sig_data)
        return hashlib.md5(sig_str).hexdigest()

    def get(self, feature_name: str, df: pd.DataFrame) -> Optional[pd.Series]:
        """从缓存获取特征"""
        current_sig = self._compute_signature(df)

        if self._df_signature != current_sig:
            self._memory_cache.clear()
            self._df_signature = current_sig
            return None

        return self._memory_cache.get(feature_name)

    def set(self, feature_name: str, df: pd.DataFrame, series: pd.Series) -> None:
        """设置缓存"""
        self._df_signature = self._compute_signature(df)
        self._memory_cache[feature_name] = series.copy()

    def invalidate(self, feature_name: Optional[str] = None) -> None:
        """使缓存失效"""
        if feature_name:
            self._memory_cache.pop(feature_name, None)
        else:
            self._memory_cache.clear()
            self._df_signature = None

    def load_from_disk(self, feature_name: str, df: pd.DataFrame) -> Optional[pd.Series]:
        """从磁盘加载缓存"""
        if not self.cache_dir:
            return None

        current_sig = self._compute_signature(df)
        cache_file = self.cache_dir / f"{feature_name}_{current_sig}.pkl"

        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached_sig, cached_series = pickle.load(f)
                if cached_sig == current_sig:
                    self._df_signature = current_sig
                    self._memory_cache[feature_name] = cached_series
                    return cached_series
            except Exception:
                pass

        return None

    def save_to_disk(self, feature_name: str, df: pd.DataFrame, series: pd.Series) -> None:
        """保存到磁盘"""
        if not self.cache_dir:
            return

        current_sig = self._compute_signature(df)
        cache_file = self.cache_dir / f"{feature_name}_{current_sig}.pkl"

        try:
            with open(cache_file, 'wb') as f:
                pickle.dump((current_sig, series), f)
        except Exception:
            pass


# 全局缓存实例
_global_cache: Optional[FeatureCache] = None


def get_cache() -> FeatureCache:
    """获取全局缓存"""
    global _global_cache
    if _global_cache is None:
        _global_cache = FeatureCache()
    return _global_cache
