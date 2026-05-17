"""
Scheduler Runtime - 定时调度运行时实现

定时任务调度和执行监控
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig, RuntimeState
from infrastructure.logging import get_logger


class SchedulerConfig(RuntimeConfig):
    """Scheduler Runtime 配置"""
    name: str = "scheduler_runtime"
    
    max_concurrent_tasks: int = 10
    retry_attempts: int = 3
    retry_delay: float = 5.0


class SchedulerRuntime(BaseRuntime):
    """
    Scheduler Runtime
    
    职责：
    1. 定时任务调度
    2. 任务执行监控
    3. 任务失败重试
    """
    
    def __init__(self, config: SchedulerConfig = None):
        config = config or SchedulerConfig.from_env()
        super().__init__(config)
        self.config: SchedulerConfig = config
        
        self.scheduler = None
    
    async def initialize(self) -> None:
        """初始化"""
        self.logger.info("Initializing Scheduler Runtime...")
        
        from services.data_service.pipeline.scheduler import get_scheduler
        self.scheduler = get_scheduler()
        
        self.logger.info("Scheduler Runtime initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭"""
        self.logger.info("Shutting down Scheduler Runtime...")
        
        if self.scheduler:
            await self.scheduler.stop()
        
        self.logger.info(f"Scheduler Runtime stopped. Stats: {self.context.stats}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Scheduler Runtime...")
        
        if self.scheduler:
            await self.scheduler.start()
        
        while not self.context.is_shutdown_requested():
            await asyncio.sleep(10)
            
            if self.scheduler:
                stats = self.scheduler.get_all_stats()
                self.context.record_stat("active_tasks", len(stats))
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "scheduler_running": self.scheduler is not None,
        })
        return health


_scheduler_runtime: Optional[SchedulerRuntime] = None


def get_scheduler_runtime() -> SchedulerRuntime:
    """获取 Scheduler Runtime 单例"""
    global _scheduler_runtime
    if _scheduler_runtime is None:
        _scheduler_runtime = SchedulerRuntime()
    return _scheduler_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Scheduler Runtime - Task Scheduling")
    print("=" * 60)
    
    runtime = get_scheduler_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
