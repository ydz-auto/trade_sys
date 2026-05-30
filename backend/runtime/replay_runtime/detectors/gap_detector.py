from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger
from infrastructure.persistence.repository.market_data.kline_repository import (
    KlineRepository,
    get_kline_repository,
)

from domain.event.base_event import Timeframe, Candle
from runtime.replay_runtime.models.repair_models.repair_models import GapInfo, GapStatus, IntegrityReport

logger = get_logger("repair_service.gap_detector")


class GapDetector:
    def __init__(self):
        self._kline_repo: Optional[KlineRepository] = None

    async def initialize(self):
        self._kline_repo = await get_kline_repository()

    async def detect_gaps(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start_time: int,
        end_time: int
    ) -> List[GapInfo]:
        if not self._kline_repo:
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
            return await self._kline_repo.fetch_candles(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
            )
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

        for candle in candles:
            candle_time = candle["open_time"]
            is_complete = candle.get("is_complete", True)
            missing = candle.get("missing_count", 0)

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
        complete_count = len([c for c in candles if c.get("is_complete", True)]) - sum(
            c.get("missing_count", 0) for c in candles
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
