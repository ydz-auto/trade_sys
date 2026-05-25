"""
Feature Generation Service - 统一特征生成服务 (Application 层)

架构定位：
    Application 层 workflow，不是 Runtime。

    FeatureRuntime (在线计算，事件驱动)
         ↓ 实时特征
    FeatureGenerationService (离线批量生成，application workflow)
         ↓ 历史特征
    两者共享 UnifiedFeatureCalculator，确保在线/离线一致。

边界：
    - 使用 UnifiedFeatureCalculator 计算特征（与 FeatureRuntime 共享）
    - 不直接操作 feature_matrix_runtime 的 PIT store
    - 生成结果写入 Parquet/ClickHouse（持久化）
    - 在线特征由 FeatureRuntime 通过事件流实时计算

替代以下脚本：
- scripts/generate_features.py
- scripts/generate_orderbook_features.py
- scripts/generate_market_structure_features.py
- scripts/extract_orderbook_features.py
- scripts/quick_feature_extraction.py

用法：
    # 命令行
    python -m domain.feature.generation_service generate --symbol BTCUSDT --start 2024-01-01 --end 2024-12-31
    
    # 代码
    from application.workflows.feature_generation import FeatureGenerationService
    service = FeatureGenerationService()
    await service.generate_features(symbol, start, end)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
import pandas as pd
import numpy as np

import logging
from engines.compute.feature.unified_calculator import UnifiedFeatureCalculator, get_feature_calculator
from domain.feature.availability import SystematicAvailabilityGuard, get_systematic_guard, AvailabilityStatus
from domain.feature.label_isolation import StrictLabelStore, get_label_store, safe_dataframe
from domain.feature.infrastructure.partial_candle_handler import get_partial_candle_handler
from infrastructure.utilities.runtime_clock import get_clock
from infrastructure.utilities.time_authority import ensure_time_ms

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """特征生成配置"""
    data_root: Path = None
    output_root: Path = None
    
    exchanges: List[str] = field(default_factory=lambda: ["binance", "okx"])
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    
    feature_groups: List[str] = field(default_factory=lambda: [
        "technical",
        "volume",
        "volatility",
        "momentum",
    ])
    
    enable_orderbook: bool = True
    enable_market_structure: bool = True
    
    def __post_init__(self):
        if self.data_root is None:
            self.data_root = Path(__file__).parent.parent.parent / "data_lake"
        if self.output_root is None:
            self.output_root = self.data_root / "features"


class FeatureGenerationService:
    """
    统一特征生成服务
    
    替代多个特征生成脚本，确保：
    1. 在线/离线使用相同逻辑
    2. 走 UnifiedFeatureCalculator
    3. 防止数据泄露
    """
    
    def __init__(self, config: GenerationConfig = None):
        self.config = config or GenerationConfig()
        self.calculator = get_feature_calculator()
        self._partial_candle_handler = get_partial_candle_handler()
        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
    
    async def generate_features(
        self,
        symbol: str,
        exchange: str = "binance",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Path:
        """
        生成特征
        
        这是核心方法，替代 generate_features.py
        """
        klines_path = self.config.data_root / "crypto" / exchange / "klines" / f"symbol={symbol}"
        
        if not klines_path.exists():
            logger.error(f"Klines data not found: {klines_path}")
            return None
        
        df = await self._load_klines(klines_path, start_time, end_time)
        
        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return None
        
        # 1. Label 隔离检查：移除标签列，防止泄露
        df = safe_dataframe(df)
        
        # 2. 计算特征
        df = self.calculator.compute_batch(df, symbol)
        
        # 3. 再次 Label 隔离检查
        df = safe_dataframe(df)
        
        # 4. 特征可用性和部分 K 线检查
        df = self._apply_availability_guard(df)
        
        output_path = self.config.output_root / exchange / symbol / "features.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_parquet(output_path, index=False)
        logger.info(f"Features saved to {output_path}")
        
        return output_path
    
    async def generate_batch(
        self,
        symbols: List[str] = None,
        exchanges: List[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Path]:
        """批量生成特征"""
        symbols = symbols or self.config.symbols
        exchanges = exchanges or self.config.exchanges
        
        results = {}
        
        for exchange in exchanges:
            for symbol in symbols:
                try:
                    path = await self.generate_features(
                        symbol=symbol,
                        exchange=exchange,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    results[f"{exchange}_{symbol}"] = path
                except Exception as e:
                    logger.error(f"Failed to generate features for {exchange}_{symbol}: {e}")
                    results[f"{exchange}_{symbol}"] = None
        
        return results
    
    async def generate_orderbook_features(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> pd.DataFrame:
        """
        生成订单簿特征
        
        替代 generate_orderbook_features.py
        """
        orderbook_path = self.config.data_root / "crypto" / exchange / "orderbook" / f"symbol={symbol}"
        
        if not orderbook_path.exists():
            logger.warning(f"Orderbook data not found: {orderbook_path}")
            return pd.DataFrame()
        
        df = await self._load_orderbook(orderbook_path)
        
        if df.empty:
            return df
        
        features = self._compute_orderbook_features(df)
        
        return features
    
    async def generate_market_structure_features(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> pd.DataFrame:
        """
        生成市场结构特征
        
        替代 generate_market_structure_features.py
        """
        klines_path = self.config.data_root / "crypto" / exchange / "klines" / f"symbol={symbol}"
        
        if not klines_path.exists():
            return pd.DataFrame()
        
        df = await self._load_klines(klines_path)
        
        if df.empty:
            return df
        
        features = self._compute_market_structure_features(df)
        
        return features
    
    async def generate_features_runtime(
        self,
        symbol: str,
        exchange: str = "binance",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        mode: str = "replay",
    ) -> pd.DataFrame:
        from infrastructure.utilities.runtime_clock import set_clock_mode, ClockMode
        if mode == "replay":
            set_clock_mode(ClockMode.REPLAY)
        elif mode == "paper":
            set_clock_mode(ClockMode.PAPER)
        else:
            set_clock_mode(ClockMode.LIVE)
        
        klines_path = self.config.data_root / "crypto" / exchange / "klines" / f"symbol={symbol}"
        
        if not klines_path.exists():
            logger.error(f"Klines data not found: {klines_path}")
            return pd.DataFrame()
        
        df = await self._load_klines(klines_path, start_time, end_time)
        
        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return pd.DataFrame()
        
        df = self.calculator.compute_batch(df, symbol)
        
        if mode == "replay" and 'timestamp' in df.columns and not df.empty:
            last_ts = df['timestamp'].iloc[-1]
            if hasattr(last_ts, 'timestamp'):
                last_ts_ms = int(last_ts.timestamp() * 1000)
            else:
                last_ts_ms = int(last_ts)
            self._clock.advance_to(last_ts_ms)
        
        return df
    
    async def generate_features_safe(
        self,
        symbol: str,
        exchange: str = "binance",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        mode: str = "replay",
        normalize_columns: Optional[List[str]] = None,
        target_timeframe_ms: Optional[int] = None,
    ) -> pd.DataFrame:
        df = await self.generate_features_runtime(
            symbol=symbol,
            exchange=exchange,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
        )
        
        if df.empty:
            return df
        
        if normalize_columns:
            existing_cols = [c for c in normalize_columns if c in df.columns]
            if existing_cols:
                df = self._safe_zscore_normalize(df, existing_cols)
        
        if target_timeframe_ms is not None:
            df = self._safe_multi_timeframe_aggregate(df, target_timeframe_ms)
        
        return df
    
    def _safe_zscore_normalize(
        self,
        df: pd.DataFrame,
        columns: List[str],
        timestamp_col: str = 'timestamp',
    ) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values(timestamp_col).reset_index(drop=True)
        
        for col in columns:
            if col not in df.columns:
                continue
            
            expanding_mean = df[col].expanding(min_periods=2).mean()
            expanding_std = df[col].expanding(min_periods=2).std()
            
            zscore_col = f"{col}_zscore"
            df[zscore_col] = (df[col] - expanding_mean) / expanding_std
            df[zscore_col] = df[zscore_col].replace([np.inf, -np.inf], np.nan)
        
        return df
    
    def _safe_multi_timeframe_aggregate(
        self,
        df: pd.DataFrame,
        target_timeframe_ms: int,
        timestamp_col: str = 'timestamp',
    ) -> pd.DataFrame:
        df = df.copy()
        
        if timestamp_col not in df.columns:
            return df
        
        if df[timestamp_col].dtype == 'datetime64[ns]' or hasattr(df[timestamp_col].dt, 'tz'):
            query_time = int(df[timestamp_col].max().timestamp() * 1000)
        elif pd.api.types.is_numeric_dtype(df[timestamp_col]):
            query_time = int(df[timestamp_col].max())
        else:
            try:
                query_time = int(pd.Timestamp(df[timestamp_col].max()).timestamp() * 1000)
            except Exception:
                from infrastructure.utilities.runtime_clock import now_ms
                query_time = now_ms()
        
        result = self._partial_candle_handler.aggregate_to_higher_timeframe(
            lower_tf_df=df,
            target_period_ms=target_timeframe_ms,
            query_time=query_time,
            timestamp_col=timestamp_col,
            use_partial=False,
        )
        
        return result
    
    async def _load_klines(
        self,
        klines_path: Path,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """加载 K线数据"""
        dfs = []
        
        for year_dir in klines_path.iterdir():
            if not year_dir.is_dir() or not year_dir.name.startswith("year="):
                continue
            
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not month_dir.name.startswith("month="):
                    continue
                
                parquet_path = month_dir / "data.parquet"
                if parquet_path.exists():
                    df = pd.read_parquet(parquet_path)
                    dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
        
        df = pd.concat(dfs, ignore_index=True)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        if start_time:
            start_dt = pd.Timestamp(start_time)
            df = df[df['timestamp'] >= start_dt]
        
        if end_time:
            end_dt = pd.Timestamp(end_time)
            df = df[df['timestamp'] <= end_dt]
        
        return df
    
    async def _load_orderbook(self, orderbook_path: Path) -> pd.DataFrame:
        """加载订单簿数据"""
        dfs = []
        
        for parquet_file in orderbook_path.glob("**/*.parquet"):
            try:
                df = pd.read_parquet(parquet_file)
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to load {parquet_file}: {e}")
        
        if not dfs:
            return pd.DataFrame()
        
        return pd.concat(dfs, ignore_index=True)
    
    def _compute_orderbook_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算订单簿特征"""
        features = pd.DataFrame()
        
        if 'timestamp' in df.columns:
            features['timestamp'] = df['timestamp']
        
        if 'bid_price' in df.columns and 'ask_price' in df.columns:
            features['spread'] = df['ask_price'] - df['bid_price']
            features['spread_pct'] = features['spread'] / df['bid_price']
            features['mid_price'] = (df['bid_price'] + df['ask_price']) / 2
        
        if 'bid_volume' in df.columns and 'ask_volume' in df.columns:
            features['bid_ask_imbalance'] = (df['bid_volume'] - df['ask_volume']) / (df['bid_volume'] + df['ask_volume'])
            features['total_volume'] = df['bid_volume'] + df['ask_volume']
        
        return features
    
    def _apply_availability_guard(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        应用特征可用性检查和部分 K 线处理
        
        这是一个安全机制，确保：
        1. 特征可用性检查
        2. 部分 K 线处理
        3. 未来数据隔离
        """
        import copy
        df = copy.deepcopy(df)
        
        if len(df) == 0:
            return df
        
        # 确保我们有 timestamp 列
        timestamp_col = None
        if 'timestamp' in df.columns:
            timestamp_col = 'timestamp'
        elif 'open_time' in df.columns:
            timestamp_col = 'open_time'
        
        if timestamp_col is None:
            logger.warning("No timestamp column found, skipping availability guard")
            return df
        
        # 识别所有特征列（排除基本列）
        basic_cols = {'timestamp', 'open_time', 'open', 'high', 'low', 'close', 'volume'}
        feature_cols = [col for col in df.columns if col not in basic_cols]
        
        if not feature_cols:
            return df
        
        # 处理部分 K 线
        try:
            # 首先，将时间戳转换为 ms 整数
            timestamps_ms = []
            for idx, row in df.iterrows():
                ts = row[timestamp_col]
                try:
                    if pd.api.types.is_datetime64_any_dtype(type(ts)) or hasattr(ts, 'timestamp'):
                        ts_ms = int(ts.timestamp() * 1000)
                    else:
                        ts_ms = int(ts)
                    timestamps_ms.append(ts_ms)
                except (ValueError, TypeError):
                    timestamps_ms.append(idx)
            
            # 对于时间序列特征，我们需要确保它们符合可用性规则
            # 这里我们使用 SystematicAvailabilityGuard 来检查特征可用性
            for idx, ts_ms in enumerate(timestamps_ms):
                # 对于离线生成，我们假设 query_time 是序列末尾的时间
                query_time = timestamps_ms[-1] if idx == len(timestamps_ms) - 1 else timestamps_ms[idx]
                
                for feature_name in feature_cols:
                    # 检查特征可用性
                    status = self._availability_guard.check(
                        feature_name=feature_name,
                        feature_timestamp=ts_ms,
                        query_time=query_time,
                        clock=self._clock
                    )
                    
                    if status == AvailabilityStatus.NOT_YET_AVAILABLE:
                        # 特征尚未可用，设为 NaN
                        if pd.notna(df.at[idx, feature_name]):
                            df.at[idx, feature_name] = np.nan
                            logger.debug(f"Feature {feature_name} not available at {ts_ms}, set to NaN")
                    elif status == AvailabilityStatus.PARTIAL_ONLY:
                        # 部分可用，记录警告
                        logger.debug(f"Feature {feature_name} is partial at {ts_ms}")
        
        except Exception as e:
            logger.warning(f"Error applying availability guard: {e}")
        
        # 使用部分 K 线处理器进行最终检查
        try:
            df = self._partial_candle_handler.sanitize_dataframe(df, timestamp_col=timestamp_col)
        except Exception as e:
            logger.warning(f"Error in partial candle handler: {e}")
        
        return df
    
    def _compute_market_structure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算市场结构特征"""
        features = pd.DataFrame()
        
        if 'timestamp' in df.columns:
            features['timestamp'] = df['timestamp']
        
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            features['body'] = df['close'] - df['open']
            features['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
            features['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
            features['range'] = df['high'] - df['low']
            features['body_pct'] = features['body'] / features['range']
        
        if 'volume' in df.columns:
            features['volume_change'] = df['volume'].pct_change()
            features['volume_ma_20'] = df['volume'].rolling(20).mean()
        
        return features


async def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Feature Generation Service")
    parser.add_argument("command", choices=["generate", "batch", "orderbook", "market_structure"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    
    args = parser.parse_args()
    
    service = FeatureGenerationService()
    
    if args.command == "generate":
        path = await service.generate_features(
            symbol=args.symbol,
            exchange=args.exchange,
            start_time=args.start,
            end_time=args.end,
        )
        print(f"Features generated: {path}")
    
    elif args.command == "batch":
        results = await service.generate_batch(
            start_time=args.start,
            end_time=args.end,
        )
        for key, path in results.items():
            print(f"{key}: {path}")
    
    elif args.command == "orderbook":
        df = await service.generate_orderbook_features(
            symbol=args.symbol,
            exchange=args.exchange,
        )
        print(f"Orderbook features: {len(df)} rows")
    
    elif args.command == "market_structure":
        df = await service.generate_market_structure_features(
            symbol=args.symbol,
            exchange=args.exchange,
        )
        print(f"Market structure features: {len(df)} rows")


if __name__ == "__main__":
    asyncio.run(main())
