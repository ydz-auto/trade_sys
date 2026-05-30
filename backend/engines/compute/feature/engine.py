"""
Feature Engine - 统一特征计算引擎

职责：
1. 从 Registry 获取特征定义
2. 解析特征依赖
3. 协调 AccelerationService 进行加速计算
4. 管理缓存
5. 返回计算结果
6. 构建历史特征矩阵
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
        source: Optional[str] = None,
    ):
        self.registry = registry or get_registry()
        self.cache = cache or get_cache()
        self.use_cache = use_cache
        self.source = source

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


    def build_historical_matrix(
        self,
        symbol: str = "BTCUSDT",
        exchange: str = "binance",
        days: int = 90,
        timeframe: str = "1h",
        exclude_sources: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        构建历史特征矩阵

        Args:
            symbol: 交易对
            exchange: 交易所
            days: 回看天数
            timeframe: K线周期
            exclude_sources: 排除的数据源

        Returns:
            特征矩阵 DataFrame
        """
        try:
            from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
            reader = FileDataLakeReader()

            # 加载基础K线数据
            klines = self._load_klines(reader, exchange, symbol, timeframe, days)
            
            # 加载资金费率
            funding = self._load_funding(reader, exchange, symbol, timeframe, klines)
            
            # 加载持仓量
            oi = self._load_oi(reader, exchange, symbol, timeframe, klines)
            
            # 加载订单簿
            orderbook = self._load_orderbook(reader, exchange, symbol, timeframe, klines)
            
            # 加载清算数据
            liquidations = self._load_liquidations(reader, exchange, symbol, timeframe, klines)
            
            # 合并所有数据源
            df = self._merge_datasets(klines, funding, oi, orderbook, liquidations)
            
            # 计算所有特征
            df = self._compute_all_features(df)
            
            # 确保数据对多进程安全
            try:
                from infrastructure.utils.multiprocessing_utils import clean_dataframe_for_multiprocessing
                df = clean_dataframe_for_multiprocessing(df)
            except Exception as e:
                print(f"  清理多进程数据失败（非致命）: {e}")
            
            return df

        except Exception as e:
            print(f"  FeatureEngine 构建矩阵失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _load_klines(self, reader, exchange, symbol, timeframe, days):
        """加载K线数据"""
        try:
            klines = reader.read_klines(exchange, symbol, timeframe, days=days)
            if klines is not None and not klines.empty:
                klines = klines.sort_values("timestamp").reset_index(drop=True)
            return klines
        except Exception as e:
            print(f"  加载K线失败: {e}")
            return None

    def _load_funding(self, reader, exchange, symbol, timeframe, klines):
        """加载资金费率数据"""
        try:
            return reader.read_funding(exchange, symbol, timeframe, klines)
        except Exception as e:
            print(f"  加载资金费率失败: {e}")
            return None

    def _load_oi(self, reader, exchange, symbol, timeframe, klines):
        """加载持仓量数据"""
        try:
            return reader.read_open_interest(exchange, symbol, timeframe, klines)
        except Exception as e:
            print(f"  加载持仓量失败: {e}")
            return None

    def _load_orderbook(self, reader, exchange, symbol, timeframe, klines):
        """加载订单簿数据"""
        try:
            return reader.read_orderbook(exchange, symbol, timeframe, klines)
        except Exception as e:
            print(f"  加载订单簿失败: {e}")
            return None

    def _load_liquidations(self, reader, exchange, symbol, timeframe, klines):
        """加载清算数据"""
        try:
            return reader.read_liquidations(exchange, symbol, timeframe, klines)
        except Exception as e:
            print(f"  加载清算数据失败: {e}")
            return None

    def _merge_datasets(self, klines, funding, oi, orderbook, liquidations):
        """合并所有数据集"""
        if klines is None or klines.empty:
            return pd.DataFrame()

        df = klines.copy()
        df = df.sort_values("timestamp").reset_index(drop=True)

        # 合并资金费率
        if funding is not None and not funding.empty:
            df = df.merge(funding, on="timestamp", how="left")

        # 合并持仓量
        if oi is not None and not oi.empty:
            df = df.merge(oi, on="timestamp", how="left")

        # 合并订单簿
        if orderbook is not None and not orderbook.empty:
            df = df.merge(orderbook, on="timestamp", how="left")

        # 合并清算数据
        if liquidations is not None and not liquidations.empty:
            df = df.merge(liquidations, on="timestamp", how="left")

        return df

    def _compute_all_features(self, df):
        """计算所有特征"""
        # 首先计算基础特征
        base_features = [
            "ret_1", "ret_3", "ret_5", "ret_10", "ret_20",
            "atr_pct", "atr_expansion", "trend_20", "slope",
            "volatility_zscore", "rsi_14", "macd",
        ]
        
        # 计算基础特征
        df = self.compute(df, base_features)
        
        # 计算其他技术指标
        tech_features = [
            "ema_20", "ema_50", "sma_20", "sma_50", "sma_100",
            "bb_upper", "bb_middle", "bb_lower", "bb_width",
        ]
        
        df = self.compute(df, tech_features)
        
        # 计算市场特征
        market_features = [
            "funding_zscore", "oi_zscore", "oi_funding_divergence",
            "leverage_crowdedness",
        ]
        
        df = self.compute(df, market_features)
        
        # 计算Alpha因子
        alpha_features = [
            "distance_from_ma20", "zscore_price", "breakout_strength",
        ]
        
        df = self.compute(df, alpha_features)
        
        return df


def get_engine() -> FeatureEngine:
    """获取全局 FeatureEngine 实例"""
    return FeatureEngine()
