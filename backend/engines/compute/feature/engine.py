"""
Feature Engine - 统一特征计算引擎

职责：
1. 从 Registry 获取特征定义
2. 解析特征依赖
3. 协调 AccelerationService 进行加速计算
4. 管理缓存
5. 返回计算结果
"""

from typing import List, Optional, Union
from pathlib import Path
import pandas as pd
from engines.compute.feature.registry import get_registry, FeatureRegistry
from engines.compute.feature.cache import get_cache, FeatureCache
from engines.compute.feature.contracts import Feature


class FeatureEngine:
    """统一特征计算引擎"""

    def __init__(
        self,
        registry: Optional[FeatureRegistry] = None,
        cache: Optional[FeatureCache] = None,
        use_cache: bool = True,
    ):
        self.registry = registry or get_registry()
        self.cache = cache or get_cache()
        self.use_cache = use_cache

    def compute(
        self,
        df: pd.DataFrame,
        features: Union[List[str], List[Feature]],
        use_cache: Optional[bool] = None,
    ) -> pd.DataFrame:
        """
        计算特征

        Args:
            df: 基础数据 DataFrame
            features: 特征名称列表或 Feature 实例列表
            use_cache: 是否使用缓存（覆盖实例级设置）

        Returns:
            包含计算后特征的 DataFrame
        """
        use_cache_flag = use_cache if use_cache is not None else self.use_cache

        feature_names = self._resolve_feature_names(features)
        resolved_features = self.registry.resolve_dependencies(feature_names)

        result_df = df.copy()

        for name in resolved_features:
            feature = self.registry.get(name)
            if feature is None:
                print(f"  ⚠️ 特征不存在: {name}")
                continue

            if use_cache_flag:
                cached = self.cache.get(name, df)
                if cached is not None:
                    result_df[name] = cached
                    continue

            try:
                series = feature.compute(df)
                result_df[name] = series

                if use_cache_flag:
                    self.cache.set(name, df, series)

            except Exception as e:
                print(f"  ❌ 计算特征失败 {name}: {e}")

        return result_df

    def compute_single(
        self,
        df: pd.DataFrame,
        feature: Union[str, Feature],
        use_cache: Optional[bool] = None,
    ) -> pd.Series:
        """
        计算单个特征

        Args:
            df: 基础数据 DataFrame
            feature: 特征名称或 Feature 实例
            use_cache: 是否使用缓存

        Returns:
            计算后的特征 Series
        """
        name = feature if isinstance(feature, str) else feature.name
        feature_obj = self.registry.get(name) if isinstance(feature, str) else feature

        if feature_obj is None:
            raise ValueError(f"特征不存在: {name}")

        use_cache_flag = use_cache if use_cache is not None else self.use_cache

        if use_cache_flag:
            cached = self.cache.get(name, df)
            if cached is not None:
                return cached

        series = feature_obj.compute(df)

        if use_cache_flag:
            self.cache.set(name, df, series)

        return series

    def list_features(self, category: Optional[str] = None) -> List[str]:
        """
        列出特征

        Args:
            category: 特征类别过滤

        Returns:
            特征名称列表
        """
        if category:
            return self.registry.list_by_category(category)
        return self.registry.list_all()

    def get_feature(self, name: str) -> Optional[Feature]:
        """获取特征定义"""
        return self.registry.get(name)

    def register_feature(self, feature: Feature) -> None:
        """注册特征"""
        self.registry.register(feature)

    def _resolve_feature_names(self, features: Union[List[str], List[Feature]]) -> List[str]:
        """解析特征名称列表"""
        names = []
        for f in features:
            if isinstance(f, str):
                names.append(f)
            else:
                names.append(f.name)
        return names

    def invalidate_cache(self, feature_name: Optional[str] = None) -> None:
        """使缓存失效"""
        self.cache.invalidate(feature_name)


def get_engine() -> FeatureEngine:
    """获取全局 FeatureEngine 实例"""
    return FeatureEngine()
