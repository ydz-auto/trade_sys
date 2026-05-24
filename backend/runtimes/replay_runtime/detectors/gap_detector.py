from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger
from infrastructure.persistence.database.clickhouse import ClickHouseManager

from domain.event.base_event import Timeframe
from engines.compute.models.candle_model import Candle
from runtimes.replay_runtime.models.repair_models import GapInfo, GapStatus, IntegrityReport

logger = get_logger("repair_service.gap_detector")


class GapDetector:
    def __init__(self):
        self.clickhouse: Optional[ClickHouseManager] = None

    async def initialize(self):
        self.clickhouse = ClickHouseManager()

    async def detect_gaps(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start_time: int,
        end_time: int
    ) -> List[GapInfo]:
        if not self.clickhouse:
            return []

        candles = await self._fetch_candles(exchange, symbol, timeframe.value, start_time, end_time)

        if not candles:
            bucket_size = timeframe.seconds * 1000
            expected_count = (end_time - start_time) // bucket_size

            return [GapInfo(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                gap_start=start_time,
                gap_end=end_time,
                missing_count=expected_count,
                status=GapStatus.DETECTED,
            )]

        gaps = self._find_gaps(exchange, symbol, timeframe, start_time, end_time, candles)
        return gaps

    async def _fetch_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int
    ) -> List[Dict]:
        try:
            rows = await self.clickhouse.execute(
                """
                SELECT
                    open_time,
                    close_time,
                    is_complete,
                    missing_count
                FROM candles
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
                    "timeframe": timeframe,
                    "start_time": start_time,
                    "end_time": end_time
                }
            )
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch candles: {e}")
            return []

    def _find_gaps(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start_time: int,
        end_time: int,
        candles: List[Dict]
    ) -> List[GapInfo]:
        gaps = []
        bucket_size = timeframe.seconds * 1000

        expected_bucket = start_time
        prev_bucket = None

        for row in candles:
            candle_time = row[0]
            is_complete = bool(row[2]) if len(row) > 2 else True
            missing = int(row[3]) if len(row) > 3 else 0

            if missing > 0:
                gaps.append(GapInfo(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    gap_start=candle_time,
                    gap_end=candle_time + bucket_size,
                    missing_count=missing,
                    status=GapStatus.DETECTED,
                ))
                continue

            if prev_bucket is not None:
                expected = prev_bucket + bucket_size
                if candle_time > expected:
                    gap_count = (candle_time - expected) // bucket_size
                    gaps.append(GapInfo(
                        exchange=exchange,
                        symbol=symbol,
                        timeframe=timeframe,
                        gap_start=expected,
                        gap_end=candle_time,
                        missing_count=gap_count,
                        status=GapStatus.DETECTED,
                    ))

            prev_bucket = candle_time

        if prev_bucket is not None:
            expected_end = prev_bucket + bucket_size
            if expected_end < end_time:
                gap_count = (end_time - expected_end) // bucket_size
                gaps.append(GapInfo(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    gap_start=expected_end,
                    gap_end=end_time,
                    missing_count=gap_count,
                    status=GapStatus.DETECTED,
                ))

        return gaps

    async def check_completeness(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start_time: int,
        end_time: int
    ) -> IntegrityReport:
        candles = await self._fetch_candles(exchange, symbol, timeframe.value, start_time, end_time)
        gaps = self._find_gaps(exchange, symbol, timeframe, start_time, end_time, candles)

        bucket_size = timeframe.seconds * 1000
        total_buckets = (end_time - start_time) // bucket_size
        complete_count = len([c for c in candles if len(c) > 2 and bool(c[2])]) - sum(
            int(c[3]) if len(c) > 3 else 0 for c in candles
        )
        missing_count = total_buckets - complete_count

        completeness = complete_count / total_buckets if total_buckets > 0 else 0

        return IntegrityReport(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            total_buckets=total_buckets,
            missing_count=missing_count,
            complete_count=complete_count,
            completeness=completeness,
            gaps=gaps,
        )

    async def scan_symbols(
        self,
        exchange: str,
        symbols: List[str],
        timeframes: List[Timeframe],
        start_time: int,
        end_time: int
    ) -> Dict[str, List[GapInfo]]:
        results = {}

        for symbol in symbols:
            for tf in timeframes:
                gaps = await self.detect_gaps(exchange, symbol, tf, start_time, end_time)
                if gaps:
                    key = f"{exchange}:{symbol}:{tf.value}"
                    results[key] = gaps

        return results


_detector: Optional[GapDetector] = None


async def get_gap_detector() -> GapDetector:
    global _detector
    if _detector is None:
        _detector = GapDetector()
        await _detector.initialize()
    return _detector
