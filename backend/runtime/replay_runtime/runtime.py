"""
Replay Runtime - 回放运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集

业务逻辑：调用 shared/replay/ 和 services/repair_service/
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig, RuntimeState
from runtime.shared import (
    RuntimeLifecycle,
    RuntimeMetrics,
    RuntimeHealthCheck,
)
from infrastructure.logging import get_logger
from infrastructure.messaging import Topics


class ReplayConfig(RuntimeConfig):
    """Replay Runtime 配置"""
    name: str = "replay_runtime"
    
    default_speed: float = 1.0
    max_concurrent_tasks: int = 5
    checkpoint_interval: int = 1000
    
    enable_rebuild: bool = True
    enable_time_travel: bool = True


class ReplayRuntime(BaseRuntime):
    """
    Replay Runtime - 回放运行时
    
    只负责运行时编排，业务逻辑在：
    - shared/replay/ - 回放引擎
    - services/repair_service/ - 修复服务
    """
    
    def __init__(self, config: ReplayConfig = None):
        config = config or ReplayConfig.from_env()
        super().__init__(config)
        self.config: ReplayConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.orchestrator = None
        self.event_store = None
        self.time_travel_engine = None
        
        self._active_tasks: Dict[str, Any] = {}
        self._task_queue: asyncio.Queue = None
    
    async def initialize(self) -> None:
        """初始化运行时组件"""
        self.logger.info("Initializing Replay Runtime...")
        
        self.lifecycle = RuntimeLifecycle("replay")
        self.metrics = RuntimeMetrics("replay")
        self.health_check = RuntimeHealthCheck("replay")
        
        self._task_queue = asyncio.Queue(maxsize=100)
        
        try:
            from shared.replay.orchestrator import ReplayOrchestrator
            self.orchestrator = ReplayOrchestrator()
            await self.orchestrator.initialize()
            self.logger.info("Replay orchestrator initialized")
        except Exception as e:
            self.logger.warning(f"Replay orchestrator init failed: {e}")
        
        try:
            from shared.replay.event_store import EventStore, get_event_store
            self.event_store = await get_event_store()
            self.logger.info("Event store initialized")
        except Exception as e:
            self.logger.warning(f"Event store init failed: {e}")
        
        try:
            from infrastructure.replay.time_travel import TimeTravelEngine
            self.time_travel_engine = TimeTravelEngine(
                event_store=self.event_store
            )
            self.logger.info("Time travel engine initialized")
        except Exception as e:
            self.logger.warning(f"Time travel engine init failed: {e}")
        
        self.logger.info("Replay Runtime initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭运行时"""
        self.logger.info("Shutting down Replay Runtime...")
        
        for task_id, task in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        if self.orchestrator:
            try:
                await self.orchestrator.stop()
            except Exception as e:
                self.logger.warning(f"Orchestrator stop error: {e}")
        
        self.logger.info(f"Replay Runtime stopped. Stats: {self.context.stats}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Replay Runtime main loop...")
        
        self.create_task(self._process_task_queue(), "task_processor")
        self.create_task(self._periodic_checkpoint(), "checkpoint")
        
        await self.run_forever()
    
    async def _process_task_queue(self) -> None:
        """处理任务队列"""
        while self.state == RuntimeState.RUNNING:
            try:
                task_data = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                
                if len(self._active_tasks) >= self.config.max_concurrent_tasks:
                    await self._task_queue.put(task_data)
                    await asyncio.sleep(0.1)
                    continue
                
                task = self.create_task(
                    self._execute_replay_task(task_data),
                    f"replay_{task_data.get('task_id', 'unknown')}"
                )
                self._active_tasks[task_data.get('task_id', str(id(task)))] = task
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Task queue error: {e}")
    
    async def _execute_replay_task(self, task_data: Dict[str, Any]) -> None:
        """执行回放任务"""
        task_id = task_data.get('task_id', 'unknown')
        
        try:
            self.metrics.increment("tasks_started")
            
            if self.orchestrator:
                result = await self.orchestrator.create_replay_task(
                    exchange=task_data.get('exchange', 'binance'),
                    symbol=task_data.get('symbol', 'BTCUSDT'),
                    timeframe=task_data.get('timeframe', '1m'),
                    start_time=task_data.get('start_time', 0),
                    end_time=task_data.get('end_time', 0),
                    speed=task_data.get('speed', self.config.default_speed),
                )
                
                self.metrics.increment("tasks_completed")
                self.context.increment_stat("replays_completed")
                
        except Exception as e:
            self.logger.error(f"Replay task {task_id} failed: {e}")
            self.metrics.increment("tasks_failed")
            self.context.record_error(f"Task {task_id}: {e}")
            
        finally:
            self._active_tasks.pop(task_id, None)
    
    async def _periodic_checkpoint(self) -> None:
        """定期检查点"""
        while self.state == RuntimeState.RUNNING:
            try:
                await asyncio.sleep(self.config.checkpoint_interval)
                
                if self.event_store:
                    checkpoint = await self.event_store.create_checkpoint()
                    self.logger.info(f"Checkpoint created: {checkpoint}")
                    self.metrics.increment("checkpoints_created")
                    
            except Exception as e:
                self.logger.error(f"Checkpoint error: {e}")
    
    async def submit_replay_task(self, task_data: Dict[str, Any]) -> str:
        """提交回放任务"""
        task_id = f"replay_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{task_data.get('symbol', 'unknown')}"
        task_data['task_id'] = task_id
        
        await self._task_queue.put(task_data)
        self.metrics.increment("tasks_submitted")
        
        return task_id
    
    async def time_travel_to(self, timestamp: int) -> Optional[Dict[str, Any]]:
        """时间旅行到指定时间点"""
        if not self.time_travel_engine:
            self.logger.warning("Time travel engine not available")
            return None
        
        try:
            snapshot = await self.time_travel_engine.travel_to(timestamp)
            self.metrics.increment("time_travels")
            return snapshot.to_dict()
        except Exception as e:
            self.logger.error(f"Time travel error: {e}")
            return None
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self._active_tasks.get(task_id)
        if task:
            return {
                "task_id": task_id,
                "status": "running" if not task.done() else "completed",
                "active_tasks": len(self._active_tasks),
            }
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        base_health = await super().health_check()
        
        base_health.update({
            "orchestrator": self.orchestrator is not None,
            "event_store": self.event_store is not None,
            "time_travel": self.time_travel_engine is not None,
            "active_tasks": len(self._active_tasks),
            "queue_size": self._task_queue.qsize() if self._task_queue else 0,
        })
        
        return base_health


async def main():
    """主入口"""
    config = ReplayConfig.from_env()
    runtime = ReplayRuntime(config)
    
    try:
        await runtime.start()
    except KeyboardInterrupt:
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())
