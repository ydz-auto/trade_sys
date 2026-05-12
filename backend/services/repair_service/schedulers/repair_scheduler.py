"""
Repair Scheduler - 修复调度器
调度和管理修复任务
"""

from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
import asyncio
import heapq

from infrastructure.logging import get_logger

from ..models.repair_models import RepairTask, GapInfo, GapStatus, RepairStrategy
from ..detectors.gap_detector import GapDetector, get_gap_detector
from ..rebuilders.candle_rebuilder import CandleRebuilder, get_candle_rebuilder

logger = get_logger("repair_service.scheduler")


@dataclass(order=True)
class PriorityTask:
    """优先级任务"""
    priority: int
    task: RepairTask = None


class RepairScheduler:
    """修复调度器

    调度和管理修复任务
    """

    def __init__(self):
        self.detector: Optional[GapDetector] = None
        self.rebuilder: Optional[CandleRebuilder] = None

        self.pending_tasks: List[RepairTask] = []
        self.running_tasks: Dict[str, RepairTask] = {}
        self.completed_tasks: Dict[str, RepairTask] = {}
        self.failed_tasks: Dict[str, RepairTask] = {}

        self._running = False
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化"""
        self.detector = await get_gap_detector()
        self.rebuilder = await get_candle_rebuilder()

    async def add_task(self, task: RepairTask):
        """添加任务"""
        async with self._lock:
            self.pending_tasks.append(task)
            heapq.heappush(self.pending_tasks, task)

    async def add_gap(self, gap: GapInfo):
        """添加缺口"""
        task = RepairTask(
            task_id=f"repair_{gap.exchange}_{gap.symbol}_{gap.timeframe.value}_{gap.gap_start}",
            gap=gap,
            strategy=self._select_strategy(gap),
            priority=self._calculate_priority(gap),
        )
        await self.add_task(task)

    async def add_gaps(self, gaps: List[GapInfo]):
        """批量添加缺口"""
        for gap in gaps:
            await self.add_gap(gap)

    def _select_strategy(self, gap: GapInfo) -> RepairStrategy:
        """选择修复策略"""
        if gap.missing_count <= 5:
            return RepairStrategy.INTERPOLATE
        elif gap.missing_count <= 60:
            return RepairStrategy.RESTORE
        else:
            return RepairStrategy.REBUILD

    def _calculate_priority(self, gap: GapInfo) -> int:
        """计算优先级"""
        priority = 10

        if gap.timeframe == "1m":
            priority += 10
        elif gap.timeframe == "5m":
            priority += 5

        if gap.missing_count > 100:
            priority += 20
        elif gap.missing_count > 10:
            priority += 10

        return -priority

    async def run(self):
        """运行调度器"""
        self._running = True
        logger.info("Repair scheduler started")

        while self._running:
            await self._process_pending()
            await asyncio.sleep(10)

    async def _process_pending(self):
        """处理待处理任务"""
        async with self._lock:
            if not self.pending_tasks:
                return

            if len(self.running_tasks) >= 10:
                return

            task = heapq.heappop(self.pending_tasks)
            if not task:
                return

            self.running_tasks[task.task_id] = task
            task.status = GapStatus.REPAIRING
            task.started_at = int(datetime.now().timestamp() * 1000)

            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: RepairTask):
        """执行任务"""
        try:
            success = await self.rebuilder.rebuild(task)

            if success:
                task.status = GapStatus.REPAIRED
                task.completed_at = int(datetime.now().timestamp() * 1000)
                self.completed_tasks[task.task_id] = task
                logger.info(f"Task completed: {task.task_id}")
            else:
                await self._handle_failure(task)

        except Exception as e:
            logger.error(f"Task failed: {task.task_id} - {e}")
            task.error = str(e)
            await self._handle_failure(task)

        finally:
            async with self._lock:
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]

    async def _handle_failure(self, task: RepairTask):
        """处理失败"""
        task.retry_count += 1

        if task.retry_count < task.max_retries:
            task.status = GapStatus.PENDING
            await self.add_task(task)
            logger.warning(f"Task retry: {task.task_id} ({task.retry_count}/{task.max_retries})")
        else:
            task.status = GapStatus.FAILED
            self.failed_tasks[task.task_id] = task
            logger.error(f"Task failed permanently: {task.task_id}")

    async def scan_and_repair(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int
    ):
        """扫描并修复"""
        logger.info(f"Scanning: {exchange}:{symbol}:{timeframe}")

        gaps = await self.detector.detect_gaps(
            exchange, symbol, timeframe, start_time, end_time
        )

        if gaps:
            logger.info(f"Found {len(gaps)} gaps")
            await self.add_gaps(gaps)
        else:
            logger.info(f"No gaps found")

    async def shutdown(self):
        """关闭"""
        self._running = False
        logger.info("Repair scheduler stopped")

    @property
    def stats(self) -> Dict:
        return {
            "pending": len(self.pending_tasks),
            "running": len(self.running_tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
        }


_scheduler: Optional[RepairScheduler] = None


async def get_repair_scheduler() -> RepairScheduler:
    """获取修复调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = RepairScheduler()
        await _scheduler.initialize()
    return _scheduler
