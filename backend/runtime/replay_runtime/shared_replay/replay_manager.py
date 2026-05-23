"""
Replay Manager - 回放管理器

⚠️ DEPRECATED: 此模块将在未来迁移到 runtime.replay_runtime。
新代码应使用 runtime.replay_runtime.runtime.TimeCausalReplayRuntime。
此模块仅为兼容保留。
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass
import asyncio
import uuid

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseManager

from domain.contracts import Timeframe, Exchange, Candle

from .models import (
    ReplayTask,
    ReplayStatus,
    ReplayCheckpoint,
    ReplayStats,
    EventRecord,
    EventType,
)
from .event_store import EventStore, get_event_store

logger = get_logger("shared.replay.replay_manager")


@dataclass
class ReplayConfig:
    """回放配置"""
    speed: float = 1.0
    batch_size: int = 1000
    checkpoint_interval: int = 10000
    enable_checkpoints: bool = True
    max_concurrent_tasks: int = 5


class ReplayManager:
    """回放管理器

    管理历史数据的回放，支持：
    - 从 ClickHouse 读取历史数据
    - 按时间顺序回放
    - 支持暂停/恢复
    - 支持检查点
    """

    def __init__(self, config: Optional[ReplayConfig] = None):
        self.config = config or ReplayConfig()

        self.clickhouse: Optional[ClickHouseManager] = None
        self.event_store: Optional[EventStore] = None

        self.tasks: Dict[str, ReplayTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}

        self._handlers: Dict[EventType, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._running = False

    async def initialize(self):
        """初始化"""
        self.clickhouse = ClickHouseManager()
        self.event_store = await get_event_store()
        self._running = True
        logger.info("ReplayManager initialized")

    def register_handler(
        self,
        event_type: EventType,
        handler: Callable[[Any], Any],
    ):
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def create_task(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
        speed: Optional[float] = None,
    ) -> ReplayTask:
        """创建回放任务"""
        task_id = f"replay_{exchange}_{symbol}_{timeframe}_{start_time}_{uuid.uuid4().hex[:8]}"

        task = ReplayTask(
            task_id=task_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            speed=speed or self.config.speed,
            batch_size=self.config.batch_size,
        )

        async with self._lock:
            self.tasks[task_id] = task

        logger.info(f"Created replay task: {task_id}")
        return task

    async def start_task(self, task_id: str) -> bool:
        """启动任务"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                logger.error(f"Task not found: {task_id}")
                return False

            if task.status == ReplayStatus.RUNNING:
                logger.warning(f"Task already running: {task_id}")
                return False

            task.status = ReplayStatus.RUNNING
            task.started_at = int(datetime.now().timestamp() * 1000)

            async_task = asyncio.create_task(self._run_replay(task))
            self.running_tasks[task_id] = async_task

            return True

    async def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status != ReplayStatus.RUNNING:
                return False

            task.status = ReplayStatus.PAUSED
            return True

    async def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status != ReplayStatus.PAUSED:
                return False

            task.status = ReplayStatus.RUNNING
            async_task = asyncio.create_task(self._run_replay(task))
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

            task.status = ReplayStatus.CANCELLED
            task.completed_at = int(datetime.now().timestamp() * 1000)
            return True

    async def _run_replay(self, task: ReplayTask):
        """执行回放"""
        logger.info(f"Starting replay: {task.task_id}")

        try:
            checkpoint = await self._load_or_create_checkpoint(task)

            timeframe = Timeframe(task.timeframe)
            event_type = self._get_event_type(timeframe)

            current_time = checkpoint.last_timestamp if checkpoint else task.start_time
            processed = checkpoint.processed_count if checkpoint else 0

            while current_time < task.end_time and task.status == ReplayStatus.RUNNING:
                candles = await self._fetch_candles(
                    task.exchange,
                    task.symbol,
                    task.timeframe,
                    current_time,
                    min(current_time + task.batch_size * timeframe.seconds * 1000, task.end_time),
                )

                if not candles:
                    break

                for candle in candles:
                    if task.status != ReplayStatus.RUNNING:
                        break

                    await self._process_candle(candle, event_type)
                    processed += 1
                    task.processed_count = processed

                    if processed % self.config.checkpoint_interval == 0:
                        await self._save_checkpoint(task, candle.open_time, processed)

                if candles:
                    current_time = candles[-1].open_time + timeframe.seconds * 1000

                task.progress = (current_time - task.start_time) / (task.end_time - task.start_time)

            if task.status == ReplayStatus.RUNNING:
                task.status = ReplayStatus.COMPLETED
                task.progress = 1.0

            task.completed_at = int(datetime.now().timestamp() * 1000)
            logger.info(f"Replay completed: {task.task_id}, processed: {processed}")

        except asyncio.CancelledError:
            logger.info(f"Replay cancelled: {task.task_id}")
            task.status = ReplayStatus.CANCELLED

        except Exception as e:
            logger.error(f"Replay failed: {task.task_id} - {e}")
            task.status = ReplayStatus.FAILED
            task.error = str(e)

    async def _fetch_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
    ) -> List[Candle]:
        """获取K线数据"""
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

    async def _process_candle(self, candle: Candle, event_type: EventType):
        """处理K线"""
        handlers = self._handlers.get(event_type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(candle)
                else:
                    handler(candle)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    def _get_event_type(self, timeframe: Timeframe) -> EventType:
        """获取事件类型"""
        mapping = {
            Timeframe.M1: EventType.CANDLE_1M,
            Timeframe.M5: EventType.CANDLE_5M,
            Timeframe.M15: EventType.CANDLE_15M,
            Timeframe.M30: EventType.CANDLE_15M,
            Timeframe.H1: EventType.CANDLE_1H,
            Timeframe.H4: EventType.CANDLE_4H,
            Timeframe.D1: EventType.CANDLE_1D,
        }
        return mapping.get(timeframe, EventType.CANDLE_1M)

    async def _load_or_create_checkpoint(self, task: ReplayTask) -> Optional[ReplayCheckpoint]:
        """加载或创建检查点"""
        if not self.config.enable_checkpoints:
            return None

        checkpoint = await self.event_store.load_checkpoint(
            task.task_id,
            task.exchange,
            task.symbol,
            task.timeframe,
        )

        if checkpoint:
            task.checkpoint = checkpoint
            logger.info(f"Loaded checkpoint: {checkpoint.checkpoint_id}")

        return checkpoint

    async def _save_checkpoint(
        self,
        task: ReplayTask,
        last_timestamp: int,
        processed_count: int,
    ):
        """保存检查点"""
        if not self.config.enable_checkpoints:
            return

        checkpoint = ReplayCheckpoint(
            checkpoint_id=f"cp_{task.task_id}_{processed_count}",
            replay_id=task.task_id,
            exchange=task.exchange,
            symbol=task.symbol,
            timeframe=task.timeframe,
            last_timestamp=last_timestamp,
            last_sequence=0,
            processed_count=processed_count,
        )

        await self.event_store.save_checkpoint(checkpoint)
        task.checkpoint = checkpoint
        logger.debug(f"Saved checkpoint: {checkpoint.checkpoint_id}")

    async def get_task(self, task_id: str) -> Optional[ReplayTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    async def list_tasks(
        self,
        status: Optional[ReplayStatus] = None,
    ) -> List[ReplayTask]:
        """列出任务"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_stats(self) -> ReplayStats:
        """获取统计"""
        stats = ReplayStats()

        for task in self.tasks.values():
            stats.total_tasks += 1
            stats.total_events_processed += task.processed_count
            stats.total_errors += task.error_count

            if task.status == ReplayStatus.RUNNING:
                stats.running_tasks += 1
            elif task.status == ReplayStatus.COMPLETED:
                stats.completed_tasks += 1
            elif task.status == ReplayStatus.FAILED:
                stats.failed_tasks += 1

        return stats

    async def shutdown(self):
        """关闭"""
        self._running = False

        for task_id in list(self.running_tasks.keys()):
            await self.cancel_task(task_id)

        logger.info("ReplayManager shutdown")


_replay_manager: Optional[ReplayManager] = None


async def get_replay_manager(config: Optional[ReplayConfig] = None) -> ReplayManager:
    """获取回放管理器实例"""
    global _replay_manager
    if _replay_manager is None:
        _replay_manager = ReplayManager(config)
        await _replay_manager.initialize()
    return _replay_manager
