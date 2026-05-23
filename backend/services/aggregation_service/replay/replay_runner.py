"""
Replay Runner - 回放器
从原始数据重新生成聚合K线

已重构为使用统一的 ReplayOrchestrator
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger

from domain.contracts import Timeframe, Exchange, Candle

logger = get_logger("aggregation_service.replay")


class ReplayRunner:
    """回放运行器

    用于从原始数据重新生成聚合K线
    现在委托给统一的 ReplayOrchestrator
    """

    def __init__(
        self,
        exchange: str,
        symbol: str,
        start_time: int,
        end_time: int,
        source_timeframe: str = "1m",
        replay_orchestrator=None,
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.start_time = start_time
        self.end_time = end_time
        self.source_timeframe = Timeframe(source_timeframe)

        self.orchestrator = replay_orchestrator
        self._task_id: Optional[str] = None

        self.stats = {
            "processed": 0,
            "aggregated": 0,
            "published": 0,
            "errors": 0
        }

    async def initialize(self):
        if self.orchestrator is None:
            from runtime.replay_runtime.shared_replay import get_replay_orchestrator
            self.orchestrator = await get_replay_orchestrator()

    async def run(self):
        from runtime.replay_runtime.shared_replay import ReplayStatus

        logger.info(f"Starting replay: {self.exchange}:{self.symbol} {self.start_time} - {self.end_time}")

        task = await self.orchestrator.create_replay_task(
            exchange=self.exchange,
            symbol=self.symbol,
            timeframe=self.source_timeframe.value,
            start_time=self.start_time,
            end_time=self.end_time,
        )
        
        self._task_id = task.task_id
        
        await self.orchestrator.start_replay(task.task_id)
        
        while True:
            current_task = await self.orchestrator.get_replay_task(task.task_id)
            if not current_task:
                break
            
            self.stats["processed"] = current_task.processed_count
            self.stats["errors"] = current_task.error_count
            
            if current_task.status in [ReplayStatus.COMPLETED, ReplayStatus.FAILED, ReplayStatus.CANCELLED]:
                break
            
            await asyncio.sleep(0.5)
        
        final_task = await self.orchestrator.get_replay_task(task.task_id)
        if final_task:
            self.stats["processed"] = final_task.processed_count
            self.stats["errors"] = final_task.error_count
        
        logger.info(f"Replay completed: {self.stats}")

    async def pause(self):
        """暂停回放"""
        if self._task_id and self.orchestrator:
            await self.orchestrator.pause_replay(self._task_id)

    async def resume(self):
        """恢复回放"""
        if self._task_id and self.orchestrator:
            await self.orchestrator.resume_replay(self._task_id)

    async def cancel(self):
        """取消回放"""
        if self._task_id and self.orchestrator:
            await self.orchestrator.cancel_replay(self._task_id)

    async def shutdown(self):
        """关闭"""
        pass


async def run_replay(
    exchange: str,
    symbol: str,
    start_time: int,
    end_time: int,
    source_timeframe: str = "1m"
):
    """运行回放"""
    runner = ReplayRunner(
        exchange=exchange,
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        source_timeframe=source_timeframe
    )

    await runner.initialize()
    await runner.run()
    await runner.shutdown()
