"""
Replay Orchestrator - 回放协调器

⚠️ DEPRECATED: 此模块将在未来迁移到 runtime.replay_runtime。
新代码应使用 runtime.replay_runtime.runtime.TimeCausalReplayRuntime。
此模块仅为 backtest 兼容保留。
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import asyncio

from infrastructure.logging import get_logger

from .models import (
    ReplayTask,
    RebuildTask,
    ReplayStatus,
    RebuildStatus,
    ReplayStats,
    RebuildStats,
    EventType,
)
from .event_store import EventStore, get_event_store
from .replay_manager import ReplayManager, ReplayConfig, get_replay_manager
from .rebuild_manager import RebuildManager, RebuildConfig, get_rebuild_manager

logger = get_logger("shared.replay.orchestrator")


class ReplayOrchestrator:
    """回放协调器

    统一协调回放和重建操作，提供：
    - 统一的任务管理
    - 状态追踪
    - 进度监控
    - 错误处理
    """

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.replay_manager: Optional[ReplayManager] = None
        self.rebuild_manager: Optional[RebuildManager] = None

        self._initialized = False
        self._running = False

    async def initialize(self):
        """初始化"""
        if self._initialized:
            return

        self.event_store = await get_event_store()
        self.replay_manager = await get_replay_manager()
        self.rebuild_manager = await get_rebuild_manager()

        self._initialized = True
        self._running = True
        logger.info("ReplayOrchestrator initialized")

    async def create_replay_task(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
        speed: float = 1.0,
    ) -> ReplayTask:
        """创建回放任务"""
        return await self.replay_manager.create_task(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            speed=speed,
        )

    async def create_rebuild_task(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
        strategy: str = "rebuild",
    ) -> RebuildTask:
        """创建重建任务"""
        return await self.rebuild_manager.create_task(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            strategy=strategy,
        )

    async def start_replay(self, task_id: str) -> bool:
        """启动回放"""
        return await self.replay_manager.start_task(task_id)

    async def start_rebuild(self, task_id: str) -> bool:
        """启动重建"""
        return await self.rebuild_manager.start_task(task_id)

    async def pause_replay(self, task_id: str) -> bool:
        """暂停回放"""
        return await self.replay_manager.pause_task(task_id)

    async def resume_replay(self, task_id: str) -> bool:
        """恢复回放"""
        return await self.replay_manager.resume_task(task_id)

    async def cancel_replay(self, task_id: str) -> bool:
        """取消回放"""
        return await self.replay_manager.cancel_task(task_id)

    async def cancel_rebuild(self, task_id: str) -> bool:
        """取消重建"""
        return await self.rebuild_manager.cancel_task(task_id)

    async def get_replay_task(self, task_id: str) -> Optional[ReplayTask]:
        """获取回放任务"""
        return await self.replay_manager.get_task(task_id)

    async def get_rebuild_task(self, task_id: str) -> Optional[RebuildTask]:
        """获取重建任务"""
        return await self.rebuild_manager.get_task(task_id)

    async def list_replay_tasks(
        self,
        status: Optional[ReplayStatus] = None,
    ) -> List[ReplayTask]:
        """列出回放任务"""
        return await self.replay_manager.list_tasks(status)

    async def list_rebuild_tasks(
        self,
        status: Optional[RebuildStatus] = None,
    ) -> List[RebuildTask]:
        """列出重建任务"""
        return await self.rebuild_manager.list_tasks(status)

    def get_replay_stats(self) -> ReplayStats:
        """获取回放统计"""
        return self.replay_manager.get_stats()

    def get_rebuild_stats(self) -> RebuildStats:
        """获取重建统计"""
        return self.rebuild_manager.get_stats()

    async def replay_and_rebuild(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
        rebuild_strategy: str = "rebuild",
    ) -> Dict[str, Any]:
        """回放并重建

        先执行回放，然后检测并修复缺口
        """
        replay_task = await self.create_replay_task(
            exchange, symbol, timeframe, start_time, end_time
        )

        await self.start_replay(replay_task.task_id)

        while True:
            task = await self.get_replay_task(replay_task.task_id)
            if task.status in [ReplayStatus.COMPLETED, ReplayStatus.FAILED, ReplayStatus.CANCELLED]:
                break
            await asyncio.sleep(1)

        if task.status == ReplayStatus.FAILED:
            return {
                "success": False,
                "replay_task": task.to_dict(),
                "error": task.error,
            }

        rebuild_task = await self.create_rebuild_task(
            exchange, symbol, timeframe, start_time, end_time, rebuild_strategy
        )

        await self.start_rebuild(rebuild_task.task_id)

        while True:
            rtask = await self.get_rebuild_task(rebuild_task.task_id)
            if rtask.status in [RebuildStatus.COMPLETED, RebuildStatus.FAILED]:
                break
            await asyncio.sleep(1)

        return {
            "success": rtask.status == RebuildStatus.COMPLETED,
            "replay_task": task.to_dict(),
            "rebuild_task": rtask.to_dict(),
        }

    async def batch_replay(
        self,
        exchange: str,
        symbols: List[str],
        timeframe: str,
        start_time: int,
        end_time: int,
        max_concurrent: int = 5,
    ) -> Dict[str, Any]:
        """批量回放"""
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_single(symbol: str):
            async with semaphore:
                task = await self.create_replay_task(
                    exchange, symbol, timeframe, start_time, end_time
                )
                await self.start_replay(task.task_id)

                while True:
                    t = await self.get_replay_task(task.task_id)
                    if t.status in [ReplayStatus.COMPLETED, ReplayStatus.FAILED, ReplayStatus.CANCELLED]:
                        return t
                    await asyncio.sleep(0.5)

        tasks = [run_single(symbol) for symbol in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, completed):
            if isinstance(result, Exception):
                results[symbol] = {"success": False, "error": str(result)}
            else:
                results[symbol] = {"success": result.status == ReplayStatus.COMPLETED, "task": result.to_dict()}

        return results

    async def batch_rebuild(
        self,
        exchange: str,
        symbols: List[str],
        timeframe: str,
        start_time: int,
        end_time: int,
        strategy: str = "rebuild",
        max_concurrent: int = 3,
    ) -> Dict[str, Any]:
        """批量重建"""
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_single(symbol: str):
            async with semaphore:
                task = await self.create_rebuild_task(
                    exchange, symbol, timeframe, start_time, end_time, strategy
                )
                await self.start_rebuild(task.task_id)

                while True:
                    t = await self.get_rebuild_task(task.task_id)
                    if t.status in [RebuildStatus.COMPLETED, RebuildStatus.FAILED]:
                        return t
                    await asyncio.sleep(0.5)

        tasks = [run_single(symbol) for symbol in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, completed):
            if isinstance(result, Exception):
                results[symbol] = {"success": False, "error": str(result)}
            else:
                results[symbol] = {"success": result.status == RebuildStatus.COMPLETED, "task": result.to_dict()}

        return results

    def register_replay_handler(
        self,
        event_type: EventType,
        handler,
    ):
        """注册回放处理器"""
        self.replay_manager.register_handler(event_type, handler)

    async def get_status(self) -> Dict[str, Any]:
        """获取整体状态"""
        return {
            "running": self._running,
            "replay_stats": self.get_replay_stats().to_dict(),
            "rebuild_stats": self.get_rebuild_stats().to_dict(),
            "active_replay_tasks": len([t for t in await self.list_replay_tasks() if t.status == ReplayStatus.RUNNING]),
            "active_rebuild_tasks": len([t for t in await self.list_rebuild_tasks() if t.status == RebuildStatus.REBUILDING]),
        }

    async def shutdown(self):
        """关闭"""
        self._running = False

        if self.replay_manager:
            await self.replay_manager.shutdown()

        if self.rebuild_manager:
            await self.rebuild_manager.shutdown()

        logger.info("ReplayOrchestrator shutdown")


_orchestrator: Optional[ReplayOrchestrator] = None


async def get_replay_orchestrator() -> ReplayOrchestrator:
    """获取回放协调器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ReplayOrchestrator()
        await _orchestrator.initialize()
    return _orchestrator
