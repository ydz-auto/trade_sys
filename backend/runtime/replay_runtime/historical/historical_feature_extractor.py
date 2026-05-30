"""
Historical Feature Extractor - 历史特征提取器

基于 aggregation_service 架构，从已下载的Trades历史数据提取特征

数据流：
Trades Parquet → TradeBatch → TradeToCandleAggregator → 1s Candle → 多周期聚合 → Feature Parquet
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import pandas as pd
import asyncio

from infrastructure.logging import get_logger

from domain.event.base_event import Candle, Timeframe, Trade
from engines.compute.aggregation.compute import CandleWindow, apply_trade_to_window, build_candle_from_trade_window
from domain.execution.models.trade_batch import TradeBatch

logger = get_logger("historical_feature_extractor")

TRADES_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake\crypto\binance\trades")
FEATURES_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake\features")

INTERVAL_TO_TIMEFRAME = {
    "1m": Timeframe.M1,
    "5m": Timeframe.M5,
    "15m": Timeframe.M15,
    "1h": Timeframe.H1,
    "4h": Timeframe.H4,
    "1d": Timeframe.D1,
}


class HistoricalFeatureExtractor:
    """历史特征提取器 - 基于aggregation_service架构"""

    def __init__(self):
        self.trade_aggregator = None
        self._window_cache: Dict[str, CandleWindow] = {}

    async def initialize(self):
        pass

    def _get_trades_from_parquet(self, symbol: str, year: int, month: int) -> pd.DataFrame:
        """从Parquet读取交易数据"""
        month_str = f"{month:02d}"
        trades_path = TRADES_ROOT / f"symbol={symbol}" / f"year={year}" / f"month={month_str}" / "data.parquet"

        if not trades_path.exists():
            logger.warning(f"Trades data not found: {trades_path}")
            return pd.DataFrame()

        return pd.read_parquet(trades_path)

    def _convert_df_to_trades(self, df: pd.DataFrame, symbol: str) -> List[Trade]:
        """将DataFrame转换为Trade对象列表"""
        trades = []

        for _, row in df.iterrows():
            timestamp_val = row["timestamp"]
            if isinstance(timestamp_val, pd.Timestamp):
                timestamp_ms = int(timestamp_val.timestamp() * 1000)
            else:
                timestamp_ms = int(timestamp_val)
            
            trade = Trade(
                exchange="binance",
                symbol=symbol,
                timestamp=timestamp_ms,
                price=float(row["price"]),
                quantity=float(row["qty"]),
                quote_quantity=float(row["quote_qty"]),
                is_buyer_maker=bool(row["is_buyer_maker"]),
                trade_id=str(row["id"]),
            )
            trades.append(trade)

        return trades

    def _aggregate_to_1s_candles(self, trades: List[Trade]) -> List[Candle]:
        windows: Dict[Tuple[str, str], CandleWindow] = {}
        candles = []

        for trade in trades:
            key = (trade.exchange, trade.symbol)
            if key not in windows:
                windows[key] = CandleWindow(
                    exchange=trade.exchange,
                    symbol=trade.symbol,
                    timeframe=Timeframe.S1,
                    bucket=0,
                )
            candle = apply_trade_to_window(windows[key], trade)
            if candle:
                candles.append(candle)

        for window in windows.values():
            if window.bucket > 0:
                candles.append(build_candle_from_trade_window(window))
                window.reset()

        return candles

    def _aggregate_candles_to_interval(self, candles: List[Candle], interval: str) -> List[Candle]:
        """将1秒K线聚合到目标周期"""
        target_timeframe = INTERVAL_TO_TIMEFRAME.get(interval)
        if not target_timeframe:
            logger.error(f"Unsupported interval: {interval}")
            return []

        candles.sort(key=lambda c: c.open_time)

        windows: Dict[str, CandleWindow] = {}
        result_candles = []

        for candle in candles:
            key = f"{candle.symbol}"
            window_key = f"{key}_{target_timeframe.value}"

            if window_key not in windows:
                windows[window_key] = CandleWindow(
                    exchange=candle.exchange,
                    symbol=candle.symbol,
                    timeframe=target_timeframe,
                    bucket=0,
                )

            window = windows[window_key]
            bucket_size = target_timeframe.to_milliseconds()
            candle_bucket = (candle.open_time // bucket_size) * bucket_size

            if window.bucket == 0:
                window.bucket = candle_bucket
            elif candle_bucket > window.bucket:
                close_candle = window.to_candle(window.bucket, window.bucket + bucket_size - 1)
                result_candles.append(close_candle)
                window.reset()
                window.bucket = candle_bucket

            window.update(candle.close, candle.volume, candle.quote_volume, candle.open_time)

        for window in windows.values():
            if window.bucket > 0:
                bucket_size = target_timeframe.to_milliseconds()
                close_candle = window.to_candle(window.bucket, window.bucket + bucket_size - 1)
                result_candles.append(close_candle)

        return result_candles

    def _candles_to_features(self, candles: List[Candle], interval: str) -> pd.DataFrame:
        """将K线转换为特征DataFrame"""
        features = []

        for candle in candles:
            features.append({
                "timestamp": candle.open_time,
                "datetime": datetime.fromtimestamp(candle.open_time / 1000),
                "exchange": candle.exchange,
                "symbol": candle.symbol,
                "interval": interval,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "quote_volume": candle.quote_volume,
                "trade_count": candle.trade_count,
                "vwap": candle.quote_volume / candle.volume if candle.volume > 0 else 0.0,
            })

        return pd.DataFrame(features)

    async def extract_features_for_month(
        self,
        symbol: str,
        year: int,
        month: int,
        intervals: List[str] = None
    ) -> Dict[str, Any]:
        """提取单个月份的特征"""
        if intervals is None:
            intervals = ["1m", "5m", "15m", "1h", "4h", "1d"]

        month_str = f"{month:02d}"
        logger.info(f"Extracting features for {symbol} {year}-{month_str}")

        df = self._get_trades_from_parquet(symbol, year, month)
        if len(df) == 0:
            return {
                "success": False,
                "symbol": symbol,
                "year": year,
                "month": month,
                "message": "No trades data found"
            }

        trades = self._convert_df_to_trades(df, symbol)
        logger.info(f"Loaded {len(trades)} trades")

        candles_1s = self._aggregate_to_1s_candles(trades)
        logger.info(f"Generated {len(candles_1s)} 1s candles")

        results = {}

        for interval in intervals:
            output_dir = FEATURES_ROOT / interval / f"symbol={symbol}" / f"year={year}" / f"month={month_str}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "data.parquet"

            aggregated_candles = self._aggregate_candles_to_interval(candles_1s, interval)
            features_df = self._candles_to_features(aggregated_candles, interval)

            features_df.to_parquet(output_path, compression="zstd", index=False)
            size_mb = output_path.stat().st_size / (1024 * 1024)

            results[interval] = {
                "status": "success",
                "records": len(features_df),
                "path": str(output_path),
                "size_mb": size_mb
            }

            logger.info(f"{interval}: {len(features_df)} records, {size_mb:.2f} MB")

        return {
            "success": True,
            "symbol": symbol,
            "year": year,
            "month": month,
            "trades_count": len(trades),
            "candles_1s_count": len(candles_1s),
            "results": results
        }

    async def extract_features(
        self,
        symbol: str,
        years: List[int],
        intervals: List[str] = None
    ) -> List[Dict[str, Any]]:
        """批量提取特征"""
        if intervals is None:
            intervals = ["1m", "5m", "15m", "1h", "4h", "1d"]

        all_results = []

        for year in years:
            for month in range(1, 13):
                if datetime(year, month, 1) > datetime.now():
                    continue

                result = await self.extract_features_for_month(symbol, year, month, intervals)
                all_results.append(result)

        return all_results


async def extract_historical_features(
    symbol: str,
    years: List[int],
    intervals: List[str] = None
) -> List[Dict[str, Any]]:
    """提取历史特征的便捷函数"""
    extractor = HistoricalFeatureExtractor()
    await extractor.initialize()
    return await extractor.extract_features(symbol, years, intervals)


async def get_feature_status(symbol: str, interval: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取特征状态"""
    statuses = []
    intervals_list = [interval] if interval else list(INTERVAL_TO_TIMEFRAME.keys())

    for intvl in intervals_list:
        interval_path = FEATURES_ROOT / intvl / f"symbol={symbol}"
        total_records = 0
        total_size = 0
        latest_ts = None

        if interval_path.exists():
            for month_dir in interval_path.rglob("month=*/data.parquet"):
                try:
                    df = pd.read_parquet(month_dir)
                    total_records += len(df)
                    total_size += month_dir.stat().st_size
                    if "timestamp" in df.columns:
                        ts = df["timestamp"].max()
                        if latest_ts is None or ts > latest_ts:
                            latest_ts = ts
                except Exception as e:
                    logger.warning(f"Failed to read {month_dir}: {e}")

        statuses.append({
            "symbol": symbol,
            "interval": intvl,
            "latest_timestamp": datetime.fromtimestamp(latest_ts / 1000).isoformat() if latest_ts else None,
            "records_count": total_records,
            "storage_size_mb": total_size / (1024 * 1024),
            "clickhouse_available": False
        })

    return statuses
