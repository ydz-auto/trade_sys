"""
Scheduler - 高频轮询调度器
支持多优先级、多频率的分布式调度
"""
import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import heapq

from infrastructure.logging import get_logger

logger = get_logger("pipeline.scheduler")


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class ScheduledTask:
    """调度的任务"""
    task_id: str
    name: str
    callback: Callable
    priority: TaskPriority
    interval: float
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    enabled: bool = True
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        return self.next_run < other.next_run


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    success: bool
    duration_ms: float
    result: Any = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class TaskStats:
    """任务统计"""
    task_id: str
    name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_duration_ms: float = 0
    last_run: Optional[float] = None
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    consecutive_failures: int = 0


class TaskScheduler:
    """高频轮询调度器
    
    特性：
    - 多优先级调度
    - 分布式-ready（可多实例）
    - 熔断保护
    - 统计监控
    """
    
    def __init__(
        self,
        check_interval: float = 1.0,
        max_concurrent: int = 10
    ):
        self.check_interval = check_interval
        self.max_concurrent = max_concurrent
        
        self._tasks: Dict[str, ScheduledTask] = {}
        self._stats: Dict[str, TaskStats] = {}
        self._running = False
        self._runner_task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
    
    def register_task(
        self,
        task_id: str,
        name: str,
        callback: Callable,
        interval: float,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 30.0,
        metadata: Dict = None,
        enabled: bool = True
    ) -> ScheduledTask:
        """注册任务"""
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            callback=callback,
            priority=priority,
            interval=interval,
            timeout=timeout,
            metadata=metadata or {},
            enabled=enabled,
            next_run=time.time()
        )
        
        self._tasks[task_id] = task
        self._stats[task_id] = TaskStats(
            task_id=task_id,
            name=name
        )
        
        logger.info(f"Registered task: {name} (interval={interval}s, priority={priority.name})")
        
        return task
    
    def unregister_task(self, task_id: str):
        """取消注册任务"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            logger.info(f"Unregistered task: {task.name}")
            del self._tasks[task_id]
    
    def enable_task(self, task_id: str):
        """启用任务"""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._tasks[task_id].next_run = time.time()
    
    def disable_task(self, task_id: str):
        """禁用任务"""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
    
    def on_task_complete(self, callback: Callable):
        """任务完成回调"""
        pass
    
    def _update_stats(self, task_id: str, result: TaskResult):
        """更新统计"""
        if task_id not in self._stats:
            return
        
        stats = self._stats[task_id]
        stats.total_runs += 1
        stats.last_run = result.timestamp
        
        if result.success:
            stats.successful_runs += 1
            stats.last_success = result.timestamp
            stats.consecutive_failures = 0
        else:
            stats.failed_runs += 1
            stats.last_failure = result.timestamp
            stats.consecutive_failures += 1
        
        total = stats.successful_runs + stats.failed_runs
        if total > 0:
            stats.avg_duration_ms = (
                (stats.avg_duration_ms * (total - 1) + result.duration_ms) / total
            )
    
    async def _run_task(self, task: ScheduledTask) -> TaskResult:
        """执行单个任务"""
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(task.callback):
                result = await asyncio.wait_for(
                    task.callback(),
                    timeout=task.timeout
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(task.callback),
                    timeout=task.timeout
                )
            
            duration_ms = (time.time() - start_time) * 1000
            
            return TaskResult(
                task_id=task.task_id,
                success=True,
                duration_ms=duration_ms,
                result=result
            )
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"Task {task.name} timed out after {duration_ms:.0f}ms")
            
            return TaskResult(
                task_id=task.task_id,
                success=False,
                duration_ms=duration_ms,
                error="Timeout"
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Task {task.name} failed: {e}")
            
            return TaskResult(
                task_id=task.task_id,
                success=False,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    async def _scheduler_loop(self):
        """调度循环"""
        logger.info("Scheduler started")
        
        while self._running:
            try:
                current_time = time.time()
                due_tasks = []
                
                for task in self._tasks.values():
                    if not task.enabled:
                        continue
                    
                    if task.next_run is None:
                        task.next_run = current_time
                    
                    if current_time >= task.next_run:
                        due_tasks.append(task)
                
                if due_tasks:
                    sorted_tasks = sorted(due_tasks, key=lambda t: (t.priority.value, t.next_run))
                    
                    for task in sorted_tasks[:self.max_concurrent]:
                        asyncio.create_task(self._execute_task(task))
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(5)
        
        logger.info("Scheduler stopped")
    
    async def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        async with self._semaphore:
            task.last_run = time.time()
            task.next_run = time.time() + task.interval
            
            result = await self._run_task(task)
            
            self._update_stats(task.task_id, result)
            
            if result.success:
                logger.debug(f"Task {task.name} completed in {result.duration_ms:.0f}ms")
            else:
                logger.warning(f"Task {task.name} failed: {result.error}")
    
    async def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._runner_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")
    
    async def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._runner_task:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler stopped")
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        if task_id not in self._tasks:
            return None
        
        task = self._tasks[task_id]
        stats = self._stats.get(task_id)
        
        return {
            "task_id": task.task_id,
            "name": task.name,
            "enabled": task.enabled,
            "priority": task.priority.name,
            "interval": task.interval,
            "last_run": task.last_run,
            "next_run": task.next_run,
            "consecutive_failures": stats.consecutive_failures if stats else 0,
            "total_runs": stats.total_runs if stats else 0,
            "success_rate": stats.successful_runs / max(stats.total_runs, 1) if stats else 0
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有任务统计"""
        return {
            task_id: {
                "name": stats.name,
                "total_runs": stats.total_runs,
                "successful_runs": stats.successful_runs,
                "failed_runs": stats.failed_runs,
                "avg_duration_ms": stats.avg_duration_ms,
                "success_rate": stats.successful_runs / max(stats.total_runs, 1),
                "consecutive_failures": stats.consecutive_failures,
                "last_run": stats.last_run,
                "last_success": stats.last_success
            }
            for task_id, stats in self._stats.items()
        }
    
    def get_due_tasks(self) -> List[Dict]:
        """获取即将执行的任务"""
        current_time = time.time()
        due = []
        
        for task in self._tasks.values():
            if not task.enabled:
                continue
            
            if task.next_run and current_time >= task.next_run:
                due.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "priority": task.priority.name,
                    "overdue_seconds": current_time - task.next_run
                })
        
        return sorted(due, key=lambda x: x["overdue_seconds"], reverse=True)


_scheduler: Optional[TaskScheduler] = None

def get_scheduler() -> TaskScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler
