"""
数据准备模块 - 处理结构化信号和非结构化信号
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("research.correlation.data")


@dataclass
class FeatureMatrix:
    """特征矩阵容器"""
    data: pd.DataFrame
    target_col: str
    feature_cols: List[str]
    timestamp_col: Optional[str] = None
    
    def get_X(self) -> pd.DataFrame:
        """获取特征矩阵"""
        return self.data[self.feature_cols]
    
    def get_y(self) -> pd.Series:
        """获取目标变量"""
        return self.data[self.target_col]
    
    def get_feature_names(self) -> List[str]:
        """获取特征名称列表"""
        return self.feature_cols.copy()


class DataPreparation:
    """
    数据准备类
    
    功能：
    1. 从 feature_pipeline 获取结构化数据
    2. 处理非结构化数据（新闻、社交）生成情感信号
    3. 创建滞后特征
    4. 对齐时间序列
    """
    
    def __init__(self):
        self.sentiment_cache: Dict[str, pd.Series] = {}
    
    async def fetch_from_pipeline(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        从 feature_pipeline 获取特征数据
        
        实际使用时需要对接你的数据存储（数据库/文件）
        """
        try:
            # 尝试从 research pipeline 获取
            from research.pipeline import get_feature_pipeline
            
            pipeline = get_feature_pipeline()
            
            # 这里简化处理，实际应从你的数据库读取
            logger.info(f"Fetching features for {symbol} {timeframe}")
            
            # 模拟数据 - 实际使用时替换为真实数据源
            df = self._generate_mock_data(symbol, timeframe, start_time, end_time)
            
            return df
            
        except Exception as e:
            logger.warning(f"Failed to fetch from pipeline: {e}, using mock data")
            return self._generate_mock_data(symbol, timeframe, start_time, end_time)
    
    def _generate_mock_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """生成模拟数据用于测试"""
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            # 默认30天数据
            start_time = end_time - timedelta(days=30)
        
        # 根据 timeframe 生成时间序列
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D"
        }
        freq = freq_map.get(timeframe, "1H")
        
        timestamps = pd.date_range(start=start_time, end=end_time, freq=freq)
        n = len(timestamps)
        
        # 生成价格序列（随机游走）
        np.random.seed(42)
        returns = np.random.normal(0.0001, 0.02, n)  # 收益率
        price = 50000 * np.exp(np.cumsum(returns))  # 价格
        
        # 生成其他特征
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": price * (1 + np.random.normal(0, 0.001, n)),
            "high": price * (1 + abs(np.random.normal(0, 0.01, n))),
            "low": price * (1 - abs(np.random.normal(0, 0.01, n))),
            "close": price,
            "volume": np.random.lognormal(10, 1, n),
            "rsi_14": np.clip(np.random.normal(50, 15, n), 0, 100),
            "macd": np.random.normal(0, 100, n),
            "bb_position": np.clip(np.random.normal(0.5, 0.2, n), 0, 1),
            "volatility_1h": np.abs(np.random.normal(0, 0.02, n)),
            "volume_ratio": np.random.normal(1, 0.3, n),
        })
        
        # 计算收益率
        df["returns"] = df["close"].pct_change()
        
        df.set_index("timestamp", inplace=True)
        df.dropna(inplace=True)
        
        logger.info(f"Generated mock data: {len(df)} rows")
        return df
    
    async def process_unstructured_data(
        self,
        news_data: List[Dict],
        time_index: Optional[pd.DatetimeIndex] = None,
        aggregation_window: str = "1H"
    ) -> pd.Series:
        """
        处理非结构化数据（新闻、推文）生成情感时间序列
        
        Args:
            news_data: 新闻数据列表，每项包含 timestamp 和 sentiment_score
            time_index: 要对齐的时间索引
            aggregation_window: 聚合窗口
        
        Returns:
            pd.Series: 情感得分时间序列
        """
        if not news_data:
            logger.warning("No news data provided")
            return pd.Series()
        
        # 转换为 DataFrame
        records = []
        for item in news_data:
            records.append({
                "timestamp": pd.to_datetime(item.get("published", item.get("timestamp", datetime.now()))),
                "sentiment_score": item.get("sentiment_score", 0.5),
                "sentiment": item.get("sentiment", "neutral"),
                "confidence": item.get("sentiment_confidence", 0.5),
            })
        
        df = pd.DataFrame(records)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        
        # 按时间窗口聚合情感得分（加权平均）
        sentiment_series = df.resample(aggregation_window).apply(
            lambda x: np.average(x["sentiment_score"], weights=x["confidence"]) if len(x) > 0 else 0.5
        )
        
        # 标准化到 [-1, 1]
        sentiment_series = (sentiment_series - 0.5) * 2
        
        # 对齐时间索引
        if time_index is not None:
            sentiment_series = sentiment_series.reindex(time_index, method="ffill").fillna(0)
        
        logger.info(f"Processed {len(news_data)} news items into {len(sentiment_series)} sentiment points")
        return sentiment_series
    
    def build_feature_matrix(
        self,
        feature_df: pd.DataFrame,
        sentiment_series: Optional[pd.Series] = None,
        target_col: str = "returns",
        lag_windows: List[int] = [1, 5, 10, 15],
        include_raw_features: bool = True
    ) -> FeatureMatrix:
        """
        构建特征矩阵，包含滞后特征
        
        Args:
            feature_df: 原始特征DataFrame
            sentiment_series: 情感时间序列
            target_col: 目标变量列名
            lag_windows: 滞后窗口列表
            include_raw_features: 是否包含原始特征
        
        Returns:
            FeatureMatrix: 特征矩阵对象
        """
        df = feature_df.copy()
        
        # 添加情感特征
        if sentiment_series is not None and len(sentiment_series) > 0:
            df["sentiment"] = sentiment_series.reindex(df.index).fillna(0)
            
            # 情感滞后特征
            for lag in lag_windows:
                df[f"sentiment_lag_{lag}"] = df["sentiment"].shift(lag)
        
        # 为每个特征创建滞后列
        feature_cols = []
        
        if include_raw_features:
            # 选择数值型特征列
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            exclude_cols = [target_col, "timestamp"]
            base_features = [c for c in numeric_cols if c not in exclude_cols]
            
            for col in base_features:
                if not col.startswith("lag_"):  # 避免重复创建
                    feature_cols.append(col)
                    
                    # 创建滞后特征
                    for lag in lag_windows:
                        lag_col = f"{col}_lag_{lag}"
                        df[lag_col] = df[col].shift(lag)
                        feature_cols.append(lag_col)
        
        # 删除包含 NaN 的行
        df.dropna(inplace=True)
        
        # 确保目标变量存在
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in data")
        
        # 构建 FeatureMatrix
        matrix = FeatureMatrix(
            data=df,
            target_col=target_col,
            feature_cols=feature_cols,
            timestamp_col=df.index.name if df.index.name else "timestamp"
        )
        
        logger.info(f"Feature matrix built: {len(df)} samples, {len(feature_cols)} features")
        return matrix
    
    def normalize_features(
        self,
        feature_matrix: FeatureMatrix,
        method: str = "zscore"
    ) -> FeatureMatrix:
        """
        特征归一化
        
        Args:
            feature_matrix: 特征矩阵
            method: 归一化方法 (zscore, minmax, robust)
        
        Returns:
            FeatureMatrix: 归一化后的特征矩阵
        """
        df = feature_matrix.data.copy()
        feature_cols = feature_matrix.feature_cols
        
        if method == "zscore":
            df[feature_cols] = (df[feature_cols] - df[feature_cols].mean()) / df[feature_cols].std()
        elif method == "minmax":
            df[feature_cols] = (df[feature_cols] - df[feature_cols].min()) / (df[feature_cols].max() - df[feature_cols].min())
        elif method == "robust":
            median = df[feature_cols].median()
            iqr = df[feature_cols].quantile(0.75) - df[feature_cols].quantile(0.25)
            df[feature_cols] = (df[feature_cols] - median) / iqr
        
        # 处理无穷值和NaN
        df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan)
        df[feature_cols] = df[feature_cols].fillna(0)
        
        return FeatureMatrix(
            data=df,
            target_col=feature_matrix.target_col,
            feature_cols=feature_cols,
            timestamp_col=feature_matrix.timestamp_col
        )
