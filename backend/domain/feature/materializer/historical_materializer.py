"""
Historical Materializer - 历史特征矩阵生成器

核心功能：
- 从data_lake读取原始数据
- 提取6大Feature Group特征
- 对齐并构建UnifiedFeatureMatrix
- 保存到feature_matrix/historical/
"""

from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime
import pandas as pd

from infrastructure.logging import get_logger
from infrastructure.storage.feature_matrix_storage import get_historical_path
from domain.feature.materializer.matrix_builder import UnifiedMatrixBuilder, UnifiedFeatureMatrix
from domain.feature.materializer.schema_registry import get_schema_registry, FeatureCategory
from domain.feature.trade.trade_feature import extract_trade_features_from_df
from domain.feature.microstructure.microstructure_feature import extract_microstructure_features
from domain.feature.oi.oi_funding_correlation import extract_oi_funding_features
from domain.feature.liquidation.liquidation_feature import extract_liquidation_features

logger = get_logger("feature.materializer.historical")


class HistoricalFeatureMaterializer:
    """历史特征矩阵生成器"""
    
    def __init__(self, data_lake_root: Path):
        self.data_lake_root = data_lake_root
        self.schema_registry = get_schema_registry()
    
    def materialize_symbol(
        self,
        symbol: str,
        interval_ms: int = 60000,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        force: bool = False
    ) -> UnifiedFeatureMatrix:
        """
        Materialize单个交易对的历史特征矩阵
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            interval_ms: 时间间隔(ms)，默认1分钟
            start_ts: 开始时间戳(ms)
            end_ts: 结束时间戳(ms)
            force: 是否强制重新生成
        """
        logger.info(f"Materializing historical features for {symbol}")
        
        # 检查是否已存在
        output_path = get_historical_path(symbol, interval_ms)
        if output_path.exists() and not force:
            logger.info(f"Loading existing feature matrix from {output_path}")
            return self._load_matrix(output_path)
        
        # 读取各数据源
        raw_data = self._load_raw_data(symbol, start_ts, end_ts)
        
        # 提取特征
        feature_groups = self._extract_feature_groups(raw_data, symbol)
        
        # 构建矩阵
        builder = UnifiedMatrixBuilder(symbol, interval_ms)
        builder.add_feature_group(feature_groups)
        matrix = builder.build()
        
        # 保存
        self._save_matrix(matrix, output_path)
        
        logger.info(f"Materialized {symbol}: shape={matrix.shape}")
        return matrix
    
    def _load_raw_data(
        self,
        symbol: str,
        start_ts: Optional[int],
        end_ts: Optional[int]
    ) -> Dict[str, pd.DataFrame]:
        """加载原始数据"""
        raw_data = {}
        
        # Trades
        trade_path = self.data_lake_root / "crypto" / "binance" / "trades" / f"symbol={symbol}"
        if trade_path.exists():
            trade_df = self._load_parquet_by_month(trade_path, start_ts, end_ts)
            if not trade_df.empty:
                raw_data["trades"] = trade_df
        
        # OI
        oi_path = self.data_lake_root / "crypto" / "binance" / "oi" / f"symbol={symbol}"
        if oi_path.exists():
            oi_df = self._load_parquet_by_month(oi_path, start_ts, end_ts)
            if not oi_df.empty:
                raw_data["oi"] = oi_df
        
        # Funding
        funding_path = self.data_lake_root / "crypto" / "binance" / "funding" / f"symbol={symbol}"
        if funding_path.exists():
            funding_df = self._load_parquet_by_month(funding_path, start_ts, end_ts)
            if not funding_df.empty:
                raw_data["funding"] = funding_df
        
        # Liquidation
        liq_path = self.data_lake_root / "crypto" / "binance" / "liquidation" / f"symbol={symbol}"
        if liq_path.exists():
            liq_df = self._load_parquet_by_month(liq_path, start_ts, end_ts)
            if not liq_df.empty:
                raw_data["liquidation"] = liq_df
        
        return raw_data
    
    def _load_parquet_by_month(
        self,
        path: Path,
        start_ts: Optional[int],
        end_ts: Optional[int]
    ) -> pd.DataFrame:
        """按月份加载Parquet"""
        dfs = []
        
        for month_dir in sorted(path.glob("month=*")):
            parquet_path = month_dir / "data.parquet"
            if not parquet_path.exists():
                continue
            
            df = pd.read_parquet(parquet_path)
            
            # 时间过滤
            if "timestamp" in df.columns:
                if start_ts:
                    df = df[df["timestamp"] >= start_ts]
                if end_ts:
                    df = df[df["timestamp"] <= end_ts]
            
            if not df.empty:
                dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
        
        return pd.concat(dfs).sort_values("timestamp").reset_index(drop=True)
    
    def _extract_feature_groups(
        self,
        raw_data: Dict[str, pd.DataFrame],
        symbol: str
    ) -> Dict[str, pd.DataFrame]:
        """提取6大特征组"""
        feature_groups = {}
        
        # Trade Flow Features
        if "trades" in raw_data:
            trade_features = extract_trade_features_from_df(raw_data["trades"], symbol)
            if not trade_features.empty:
                for col in trade_features.columns:
                    if col not in ["timestamp", "datetime", "symbol", "exchange"]:
                        feature_groups[col] = trade_features[["timestamp", col]]
        
        # Microstructure Features
        if "trades" in raw_data:
            micro_features = extract_microstructure_features(raw_data["trades"], symbol)
            if not micro_features.empty:
                for col in micro_features.columns:
                    if col not in ["timestamp", "datetime", "symbol", "exchange"]:
                        feature_groups[col] = micro_features[["timestamp", col]]
        
        # Derivatives Features (OI + Funding)
        if "oi" in raw_data or "funding" in raw_data:
            oi_df = raw_data.get("oi", pd.DataFrame())
            funding_df = raw_data.get("funding", pd.DataFrame())
            derivatives = extract_oi_funding_features(oi_df, funding_df, symbol)
            if not derivatives.empty:
                for col in derivatives.columns:
                    if col not in ["timestamp", "datetime", "symbol", "exchange"]:
                        feature_groups[col] = derivatives[["timestamp", col]]
        
        # Liquidation Features
        if "liquidation" in raw_data:
            liq_features = extract_liquidation_features(raw_data["liquidation"], symbol)
            if not liq_features.empty:
                for col in liq_features.columns:
                    if col not in ["timestamp", "datetime", "symbol", "exchange"]:
                        feature_groups[col] = liq_features[["timestamp", col]]
        
        return feature_groups
    
    def _save_matrix(self, matrix: UnifiedFeatureMatrix, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        df = matrix.to_dataframe()
        df.to_parquet(path, compression="zstd")
        logger.info(f"Saved feature matrix to {path}")
    
    def _load_matrix(self, path: Path) -> UnifiedFeatureMatrix:
        df = pd.read_parquet(path)
        timestamps = df.index.tolist()
        
        feature_vector = {}
        for col in df.columns:
            if col != "datetime":
                feature_vector[col] = df[col].tolist()
        
        symbol = str(path.parent.parent.name).replace("symbol=", "")
        interval_str = str(path.parent.name).replace("interval=", "")
        interval_ms = int(interval_str.replace("s", "")) * 1000
        
        return UnifiedFeatureMatrix(
            symbol=symbol,
            interval_ms=interval_ms,
            timestamps=timestamps,
            feature_vector=feature_vector,
            metadata={"loaded_from": str(path)}
        )

