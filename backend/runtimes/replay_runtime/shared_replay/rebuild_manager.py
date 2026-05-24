"""
Rebuild Manager - 重建管理器
管理K线数据的重建和修复
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import asyncio
import uuid

from infrastructure.logging import get_logger
from infrastructure.persistence.database.clickhouse import ClickHouseManager

from domain.event.base_event import Timeframe, Exchange, Candle
from infrastructure.persistence.database.clickhouse import candle_to_clickhouse_row

from runtimes.replay_runtime.models.models import (
    RebuildTask,
    RebuildStatus,
    RebuildStats,
    EventRecord,
    EventType,
)

logger = get_logger("shared.replay.rebuild_manager")


@dataclass
class RebuildConfig:
    """重建配置"""
    batch_size: int = 1000
    max_concurrent_tasks: int = 3
    auto_detect_gaps: bool = True
    rebuild_from_lower_tf: bool = True


class RebuildManager:
    """重建管理器

    管理K线数据的重建，支持：
    - 缺口检测
    - 从低周期重建
    - 从API恢复
    - 插值填充
    """

    def __init__(self, config: Optional[RebuildConfig] = None):
        self.config = config or RebuildConfig()

        self.clickhouse: Optional[ClickHouseManager] = None

        self.tasks: Dict[str, RebuildTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}

        self._lock = asyncio.Lock()
        self._running = False

    async def initialize(self):
        """初始化"""
        self.clickhouse = ClickHouseManager()
        self._running = True
        logger.info("RebuildManager initialized")

    async def create_task(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
        strategy: str = "rebuild",
    ) -> RebuildTask:
        """创建重建任务"""
        task_id = f"rebuild_{exchange}_{symbol}_{timeframe}_{start_time}_{uuid.uuid4().hex[:8]}"

        task = RebuildTask(
            task_id=task_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            strategy=strategy,
        )

        async with self._lock:
            self.tasks[task_id] = task

        logger.info(f"Created rebuild task: {task_id}")
        return task

    async def start_task(self, task_id: str) -> bool:
        """启动任务"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                logger.error(f"Task not found: {task_id}")
                return False

            if task.status == RebuildStatus.REBUILDING:
                logger.warning(f"Task already running: {task_id}")
                return False

            task.status = RebuildStatus.DETECTING
            task.started_at = int(datetime.now().timestamp() * 1000)

            async_task = asyncio.create_task(self._run_rebuild(task))
            self.running_tasks[task_id] = async_task

            return True

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task_id in self.running_tasks:
                self.running_tasks[task_id].cancel()
                del self.running_tasks[task_id]

            task.status = RebuildStatus.FAILED
            task.completed_at = int(datetime.now().timestamp() * 1000)
            return True

    async def _run_rebuild(self, task: RebuildTask):
        """执行重建"""
        logger.info(f"Starting rebuild: {task.task_id}")

        try:
            task.status = RebuildStatus.DETECTING

            gaps = await self._detect_gaps(
                task.exchange,
                task.symbol,
                task.timeframe,
                task.start_time,
                task.end_time,
            )

            task.gaps_found = len(gaps)
            task.gap_details = [g.to_dict() for g in gaps]

            logger.info(f"Found {len(gaps)} gaps for {task.task_id}")

            if not gaps:
                task.status = RebuildStatus.COMPLETED
                task.completed_at = int(datetime.now().timestamp() * 1000)
                return

            task.status = RebuildStatus.REBUILDING

            for gap in gaps:
                rebuilt = await self._rebuild_gap(task, gap)
                if rebuilt:
                    task.gaps_repaired += 1

            task.status = RebuildStatus.VERIFYING

            verification_passed = await self._verify_rebuild(
                task.exchange,
                task.symbol,
                task.timeframe,
                task.start_time,
                task.end_time,
            )

            if verification_passed:
                task.status = RebuildStatus.COMPLETED
            else:
                task.status = RebuildStatus.FAILED
                task.error = "Verification failed"

            task.completed_at = int(datetime.now().timestamp() * 1000)
            logger.info(f"Rebuild completed: {task.task_id}, repaired: {task.gaps_repaired}/{task.gaps_found}")

        except asyncio.CancelledError:
            logger.info(f"Rebuild cancelled: {task.task_id}")
            task.status = RebuildStatus.FAILED
            task.error = "Cancelled"

        except Exception as e:
            logger.error(f"Rebuild failed: {task.task_id} - {e}")
            task.status = RebuildStatus.FAILED
            task.error = str(e)

    async def _detect_gaps(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
    ) -> List[Any]:
        """检测缺口"""
        from runtimes.replay_runtime.detectors.gap_detector import GapDetector
        from runtimes.replay_runtime.models.repair_models import GapInfo, GapStatus

        detector = GapDetector()
        await detector.initialize()

        tf = Timeframe(timeframe)
        gaps = await detector.detect_gaps(exchange, symbol, tf, start_time, end_time)

        return gaps

    async def _rebuild_gap(self, task: RebuildTask, gap: Any) -> bool:
        """重建缺口"""
        try:
            if task.strategy == "rebuild":
                return await self._rebuild_from_lower_timeframe(task, gap)
            elif task.strategy == "restore":
                return await self._restore_from_api(task, gap)
            elif task.strategy == "interpolate":
                return await self._interpolate_gap(task, gap)
            else:
                logger.warning(f"Unknown strategy: {task.strategy}")
                return False
        except Exception as e:
            logger.error(f"Failed to rebuild gap: {e}")
            return False

    async def _rebuild_from_lower_timeframe(self, task: RebuildTask, gap: Any) -> bool:
        """从低周期重建"""
        timeframe = Timeframe(task.timeframe)

        if timeframe == Timeframe.M1:
            logger.warning("Cannot rebuild 1m from lower timeframe")
            return False

        lower_tf = self._get_lower_timeframe(timeframe)
        if not lower_tf:
            return False

        try:
            rows = await self._fetch_candles(
                task.exchange,
                task.symbol,
                lower_tf.value,
                gap.gap_start,
                gap.gap_end,
            )

            if not rows:
                logger.warning(f"No lower timeframe data found for gap")
                return False

            aggregated = self._aggregate_candles(rows, lower_tf, timeframe)

            if aggregated:
                await self._insert_candles(aggregated)
                task.candles_rebuilt += len(aggregated)
                logger.info(f"Rebuilt {len(aggregated)} candles from {lower_tf.value}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to rebuild from lower timeframe: {e}")
            return False

    async def _restore_from_api(self, task: RebuildTask, gap: Any) -> bool:
        """从API恢复"""
        return False

    async def _interpolate_gap(self, task: RebuildTask, gap: Any) -> bool:
        """插值填充"""
        timeframe = Timeframe(task.timeframe)

        before = await self._get_nearest_candle(
            task.exchange, task.symbol, timeframe,
            gap.gap_start, before=True
        )

        after = await self._get_nearest_candle(
            task.exchange, task.symbol, timeframe,
            gap.gap_end, before=False
        )

        if not before or not after:
            return False

        bucket_size = timeframe.seconds * 1000
        interpolated = []

        current = gap.gap_start
        while current < gap.gap_end:
            ratio = (current - before.open_time) / (after.open_time - before.open_time)

            candle = Candle(
                exchange=task.exchange,
                symbol=task.symbol,
                timeframe=timeframe,
                open_time=current,
                close_time=current + bucket_size - 1,
                open=before.close + ratio * (after.open - before.close),
                high=before.close + ratio * (after.high - before.high),
                low=before.close + ratio * (after.low - before.low),
                close=before.close + ratio * (after.close - before.close),
                volume=0,
                quote_volume=0,
                trade_count=0,
                is_closed=True,
            )
            interpolated.append(candle)
            current += bucket_size

        if interpolated:
            await self._insert_candles(interpolated)
            task.candles_rebuilt += len(interpolated)
            return True

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

    async def _fetch_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
    ) -> List[Candle]:
        """获取K线"""
        try:
            rows = await self.clickhouse.execute(
                """
                SELECT
                    exchange, symbol, timeframe,
                    open_time, close_time,
                    open, high, low, close,
                    volume, quote_volume, trade_count,
                    is_closed
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
                    "end_time": end_time,
                }
            )

            candles = []
            for row in rows:
                candles.append(Candle(
                    exchange=row[0],
                    symbol=row[1],
                    timeframe=Timeframe(row[2]),
                    open_time=row[3],
                    close_time=row[4],
                    open=float(row[5]),
                    high=float(row[6]),
                    low=float(row[7]),
                    close=float(row[8]),
                    volume=float(row[9]),
                    quote_volume=float(row[10]),
                    trade_count=int(row[11]),
                    is_closed=bool(row[12]),
                ))
            return candles

        except Exception as e:
            logger.error(f"Failed to fetch candles: {e}")
            return []

    def _aggregate_candles(
        self,
        source_candles: List[Candle],
        source_tf: Timeframe,
        target_tf: Timeframe,
    ) -> List[Candle]:
        """聚合K线"""
        if not source_candles:
            return []

        buckets = {}
        bucket_size = target_tf.seconds * 1000

        for candle in source_candles:
            bucket = (candle.open_time // bucket_size) * bucket_size

            if bucket not in buckets:
                buckets[bucket] = {
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "quote_volume": candle.quote_volume,
                    "trade_count": candle.trade_count,
                }
            else:
                buckets[bucket]["high"] = max(buckets[bucket]["high"], candle.high)
                buckets[bucket]["low"] = min(buckets[bucket]["low"], candle.low)
                buckets[bucket]["close"] = candle.close
                buckets[bucket]["volume"] += candle.volume
                buckets[bucket]["quote_volume"] += candle.quote_volume
                buckets[bucket]["trade_count"] += candle.trade_count

        aggregated = []
        for bucket, data in sorted(buckets.items()):
            aggregated.append(Candle(
                exchange=source_candles[0].exchange,
                symbol=source_candles[0].symbol,
                timeframe=target_tf,
                open_time=bucket,
                close_time=bucket + bucket_size - 1,
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                volume=data["volume"],
                quote_volume=data["quote_volume"],
                trade_count=data["trade_count"],
                is_closed=True,
            ))

        return aggregated

    async def _get_nearest_candle(
        self,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        time: int,
        before: bool,
    ) -> Optional[Candle]:
        """获取最近的K线"""
        try:
            op = "<" if before else ">"
            order = "DESC" if before else "ASC"

            rows = await self.clickhouse.execute(
                f"""
                SELECT
                    exchange, symbol, timeframe,
                    open_time, close_time,
                    open, high, low, close,
                    volume, quote_volume, trade_count,
                    is_closed
                FROM candles
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
                    "time": time,
                }
            )

            if rows:
                return Candle(
                    exchange=rows[0][0],
                    symbol=rows[0][1],
                    timeframe=Timeframe(rows[0][2]),
                    open_time=rows[0][3],
                    close_time=rows[0][4],
                    open=float(rows[0][5]),
                    high=float(rows[0][6]),
                    low=float(rows[0][7]),
                    close=float(rows[0][8]),
                    volume=float(rows[0][9]),
                    quote_volume=float(rows[0][10]),
                    trade_count=int(rows[0][11]),
                    is_closed=bool(rows[0][12]),
                )
            return None

        except Exception as e:
            logger.error(f"Failed to get nearest candle: {e}")
            return None

    async def _insert_candles(self, candles: List[Candle]):
        """插入K线"""
        if not candles:
            return

        try:
            rows = [candle_to_clickhouse_row(c) for c in candles]
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

    async def _verify_rebuild(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
    ) -> bool:
        """验证重建结果"""
        gaps = await self._detect_gaps(exchange, symbol, timeframe, start_time, end_time)
        return len(gaps) == 0

    async def get_task(self, task_id: str) -> Optional[RebuildTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    async def list_tasks(
        self,
        status: Optional[RebuildStatus] = None,
    ) -> List[RebuildTask]:
        """列出任务"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_stats(self) -> RebuildStats:
        """获取统计"""
        stats = RebuildStats()

        for task in self.tasks.values():
            stats.total_tasks += 1
            stats.total_gaps_found += task.gaps_found
            stats.total_gaps_repaired += task.gaps_repaired
            stats.total_candles_rebuilt += task.candles_rebuilt

            if task.status == RebuildStatus.REBUILDING:
                stats.running_tasks += 1
            elif task.status == RebuildStatus.COMPLETED:
                stats.completed_tasks += 1
            elif task.status == RebuildStatus.FAILED:
                stats.failed_tasks += 1

        return stats

    async def shutdown(self):
        """关闭"""
        self._running = False

        for task_id in list(self.running_tasks.keys()):
            await self.cancel_task(task_id)

        logger.info("RebuildManager shutdown")


_rebuild_manager: Optional[RebuildManager] = None


async def get_rebuild_manager(config: Optional[RebuildConfig] = None) -> RebuildManager:
    """获取重建管理器实例"""
    global _rebuild_manager
    if _rebuild_manager is None:
        _rebuild_manager = RebuildManager(config)
        await _rebuild_manager.initialize()
    return _rebuild_manager
