"""
Candle Rebuilder - K线重建器
重建缺失的K线数据

已重构为使用统一的 ReplayOrchestrator
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger

from shared.replay import (
    ReplayOrchestrator,
    get_replay_orchestrator,
    RebuildStatus,
)
from shared.contracts import Timeframe, Candle

logger = get_logger("repair_service.rebuilder")


class CandleRebuilder:
    """K线重建器

    重建缺失的K线数据
    现在委托给统一的 ReplayOrchestrator
    """

    def __init__(self):
        self.orchestrator: Optional[ReplayOrchestrator] = None

    async def initialize(self):
        """初始化"""
        self.orchestrator = await get_replay_orchestrator()

    async def rebuild(self, task) -> bool:
        """重建K线
        
        Args:
            task: RepairTask from repair_service.models
            
        Returns:
            bool: 是否成功
        """
        gap = task.gap
        
        rebuild_task = await self.orchestrator.create_rebuild_task(
            exchange=gap.exchange,
            symbol=gap.symbol,
            timeframe=gap.timeframe.value,
            start_time=gap.gap_start,
            end_time=gap.gap_end,
            strategy=task.strategy.value if hasattr(task.strategy, 'value') else str(task.strategy),
        )
        
        await self.orchestrator.start_rebuild(rebuild_task.task_id)
        
        while True:
            current = await self.orchestrator.get_rebuild_task(rebuild_task.task_id)
            if not current:
                break
            
            if current.status in [RebuildStatus.COMPLETED, RebuildStatus.FAILED]:
                break
            
            await asyncio.sleep(0.5)
        
        final = await self.orchestrator.get_rebuild_task(rebuild_task.task_id)
        if final:
            return final.status == RebuildStatus.COMPLETED
        
        return False


_rebuilder: Optional[CandleRebuilder] = None


async def get_candle_rebuilder() -> CandleRebuilder:
    """获取K线重建器"""
    global _rebuilder
    if _rebuilder is None:
        _rebuilder = CandleRebuilder()
        await _rebuilder.initialize()
    return _rebuilder
