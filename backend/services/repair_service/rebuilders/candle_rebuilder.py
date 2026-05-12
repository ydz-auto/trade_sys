"""
Candle Rebuilder - K线重建器
重建缺失的K线数据
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseClient

from services.aggregation_service.models.candle_model import Timeframe, Candle
from ..models.repair_models import GapInfo, GapStatus, RepairTask, RepairStrategy

logger = get_logger("repair_service.rebuilder")


class CandleRebuilder:
    """K线重建器

    重建缺失的K线数据
    """

    def __init__(self):
        self.clickhouse: Optional[ClickHouseClient] = None

    async def initialize(self):
        """初始化"""
        self.clickhouse = ClickHouseClient()

    async def rebuild(self, task: RepairTask) -> bool:
        """重建K线"""
        gap = task.gap

        if task.strategy == RepairStrategy.REBUILD:
            return await self._rebuild_from_lower_timeframe(gap)
        elif task.strategy == RepairStrategy.RESTORE:
            return await self._restore_from_api(gap)
        elif task.strategy == RepairStrategy.INTERPOLATE:
            return await self._interpolate(gap)
        else:
            return await self._mark_dirty(gap)

    async def _rebuild_from_lower_timeframe(self, gap: GapInfo) -> bool:
        """从低时间周期重建"""
        if gap.timeframe == Timeframe.M1:
            logger.warning(f"Cannot rebuild 1m from lower timeframe")
            return await self._mark_dirty(gap)

        lower_tf = self._get_lower_timeframe(gap.timeframe)
        if not lower_tf:
            return await self._mark_dirty(gap)

        try:
            rows = await self._fetch_lower_candles(
                gap.exchange,
                gap.symbol,
                lower_tf,
                gap.gap_start,
                gap.gap_end
            )

            if not rows:
                return await self._mark_dirty(gap)

            aggregated = self._aggregate_to_target(rows, lower_tf, gap.timeframe)

            await self._insert_candles(aggregated)

            logger.info(f"Rebuilt {len(aggregated)} candles for {gap.symbol} {gap.timeframe.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to rebuild: {e}")
            return False

    async def _restore_from_api(self, gap: GapInfo) -> bool:
        """从API恢复"""
        try:
            candles = await self._fetch_from_api(
                gap.exchange,
                gap.symbol,
                gap.timeframe,
                gap.gap_start,
                gap.gap_end
            )

            if candles:
                await self._insert_candles(candles)
                logger.info(f"Restored {len(candles)} candles from API")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to restore from API: {e}")
            return False

    async def _interpolate(self, gap: GapInfo) -> bool:
        """插值填充"""
        try:
            before = await self._get_nearest_candle(
                gap.exchange,
                gap.symbol,
                gap.timeframe,
                gap.gap_start,
                before=True
            )

            after = await self._get_nearest_candle(
                gap.exchange,
                gap.symbol,
                gap.timeframe,
                gap.gap_end,
                before=False
            )

            if before and after:
                candles = self._create_interpolated(
                    gap, before, after
                )
                await self._insert_candles(candles)
                logger.info(f"Interpolated {len(candles)} candles")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to interpolate: {e}")
            return False

    async def _mark_dirty(self, gap: GapInfo) -> bool:
        """标记为脏数据"""
        try:
            await self.clickhouse.execute(
                """
                INSERT INTO candles (
                    exchange, symbol, timeframe,
                    open_time, open_time_dt, close_time,
                    open, high, low, close,
                    volume, quote_volume, trade_count,
                    is_closed, is_complete, missing_count
                ) VALUES
                """,
                [{
                    "exchange": gap.exchange,
                    "symbol": gap.symbol,
                    "timeframe": gap.timeframe.value,
                    "open_time": gap.gap_start,
                    "open_time_dt": datetime.fromtimestamp(gap.gap_start / 1000),
                    "close_time": gap.gap_end,
                    "open": 0,
                    "high": 0,
                    "low": 0,
                    "close": 0,
                    "volume": 0,
                    "quote_volume": 0,
                    "trade_count": 0,
                    "is_closed": 0,
                    "is_complete": 0,
                    "missing_count": gap.missing_count,
                }]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to mark dirty: {e}")
            return False

    def _get_lower_timeframe(self, tf: Timeframe) -> Optional[Timeframe]:
        """获取更低的时间周期"""
        mapping = {
            Timeframe.M5: Timeframe.M1,
            Timeframe.M15: Timeframe.M1,
            Timeframe.M30: Timeframe.M1,
            Timeframe.H1: Timeframe.M1,
            Timeframe.H4: Timeframe.M1,
            Timeframe.D1: Timeframe.M1,
        }
        return mapping.get(tf)

    async def _fetch_lower_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start_time: int,
        end_time: int
    ) -> List:
        """获取低周期K线"""
        try:
            rows = await self.clickhouse.execute(
                """
                SELECT * FROM candles
                WHERE exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND timeframe = %(timeframe)s
                AND open_time >= %(start_time)s
                AND open_time < %(end_time)s
                ORDER BY open_time
                """,
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "timeframe": timeframe.value,
                    "start_time": start_time,
                    "end_time": end_time
                }
            )
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch lower candles: {e}")
            return []

    def _aggregate_to_target(
        self,
        rows: List,
        source_tf: Timeframe,
        target_tf: Timeframe
    ) -> List[Candle]:
        """聚合到目标周期"""
        buckets = {}
        target_bucket_size = target_tf.seconds * 1000

        for row in rows:
            open_time = row[3]
            bucket = (open_time // target_bucket_size) * target_bucket_size

            if bucket not in buckets:
                buckets[bucket] = {
                    "open": row[6],
                    "high": row[7],
                    "low": row[8],
                    "close": row[9],
                    "volume": row[10],
                    "quote_volume": row[11],
                    "trade_count": row[12],
                }
            else:
                buckets[bucket]["high"] = max(buckets[bucket]["high"], row[7])
                buckets[bucket]["low"] = min(buckets[bucket]["low"], row[8])
                buckets[bucket]["close"] = row[9]
                buckets[bucket]["volume"] += row[10]
                buckets[bucket]["quote_volume"] += row[11]
                buckets[bucket]["trade_count"] += row[12]

        candles = []
        for bucket, data in buckets.items():
            candles.append(Candle(
                exchange=rows[0][0],
                symbol=rows[0][1],
                timeframe=target_tf,
                open_time=bucket,
                close_time=bucket + target_bucket_size - 1,
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                volume=data["volume"],
                quote_volume=data["quote_volume"],
                trade_count=data["trade_count"],
                is_closed=True,
                is_complete=False,
                missing_count=0,
            ))

        return candles

    async def _fetch_from_api(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start_time: int,
        end_time: int
    ) -> List[Candle]:
        """从API获取"""
        return []

    async def _get_nearest_candle(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        time: int,
        before: bool
    ) -> Optional[Dict]:
        """获取最近的K线"""
        try:
            op = "<" if before else ">"
            order = "DESC" if before else "ASC"

            rows = await self.clickhouse.execute(
                f"""
                SELECT * FROM candles
                WHERE exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND timeframe = %(timeframe)s
                AND open_time {op} %(time)s
                ORDER BY open_time {order}
                LIMIT 1
                """,
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "timeframe": timeframe.value,
                    "time": time
                }
            )

            if rows:
                return rows[0]
            return None

        except Exception as e:
            logger.error(f"Failed to get nearest candle: {e}")
            return None

    def _create_interpolated(
        self,
        gap: GapInfo,
        before: Dict,
        after: Dict
    ) -> List[Candle]:
        """创建插值K线"""
        return []

    async def _insert_candles(self, candles: List[Candle]):
        """插入K线"""
        if not candles or not self.clickhouse:
            return

        try:
            rows = [c.to_clickhouse_row() for c in candles]
            await self.clickhouse.execute(
                """
                INSERT INTO candles (
                    exchange, symbol, timeframe,
                    open_time, open_time_dt, close_time,
                    open, high, low, close,
                    volume, quote_volume, trade_count,
                    is_closed, is_complete, missing_count
                ) VALUES
                """,
                rows
            )
        except Exception as e:
            logger.error(f"Failed to insert candles: {e}")


_rebuilder: Optional[CandleRebuilder] = None


async def get_candle_rebuilder() -> CandleRebuilder:
    """获取K线重建器"""
    global _rebuilder
    if _rebuilder is None:
        _rebuilder = CandleRebuilder()
        await _rebuilder.initialize()
    return _rebuilder
