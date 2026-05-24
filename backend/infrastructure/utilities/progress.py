"""
Progress Tracker - 进度追踪器

用于追踪长时间运行任务的进度，支持：
1. 特征计算进度
2. 回测进度
3. 参数优化进度
4. LSTM 训练进度

进度信息可通过 WebSocket 或 SSE 推送到前端。

用法：
    from infrastructure.utilities.progress import ProgressTracker, ProgressType
    
    tracker = ProgressTracker()
    
    # 创建任务
    task_id = tracker.create_task(ProgressType.BACKTEST, total=100)
    
    # 更新进度
    tracker.update(task_id, current=50, message="Processing...")
    
    # 完成
    tracker.complete(task_id, result={"sharpe": 1.5})
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import asyncio
import uuid
import time

from infrastructure.logging import get_logger

logger = get_logger("progress_tracker")


class ProgressType(Enum):
    """进度类型"""
    FEATURE_COMPUTE = "feature_compute"
    BACKTEST = "backtest"
    OPTIMIZATION = "optimization"
    LSTM_TRAIN = "lstm_train"
    DATA_DOWNLOAD = "data_download"


@dataclass
class ProgressTask:
    """进度任务"""
    task_id: str
    progress_type: ProgressType
    total: int
    current: int = 0
    message: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "running"  # running, completed, failed
    result: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total == 0:
            return 0.0
        return min(100.0, self.current / self.total * 100)
    
    @property
    def elapsed_seconds(self) -> float:
        """已用时间（秒）"""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """预估剩余时间（秒）"""
        if self.current == 0 or self.total == 0:
            return None
        
        elapsed = self.elapsed_seconds
        rate = self.current / elapsed if elapsed > 0 else 0
        
        if rate == 0:
            return None
        
        remaining_items = self.total - self.current
        return remaining_items / rate
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "type": self.progress_type.value,
            "total": self.total,
            "current": self.current,
            "progress_percent": round(self.progress_percent, 1),
            "message": self.message,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "estimated_remaining_seconds": round(self.estimated_remaining_seconds, 1) if self.estimated_remaining_seconds else None,
            "result": self.result,
            "metadata": self.metadata,
        }


class ProgressTracker:
    """
    进度追踪器
    
    支持多种进度类型，可通过回调函数推送进度更新。
    """
    
    def __init__(self):
        self._tasks: Dict[str, ProgressTask] = {}
        self._callbacks: List[Callable[[ProgressTask], None]] = []
        self._lock = asyncio.Lock()
    
    def add_callback(self, callback: Callable[[ProgressTask], None]):
        """添加进度更新回调"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[ProgressTask], None]):
        """移除进度更新回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def create_task(
        self,
        progress_type: ProgressType,
        total: int,
        message: str = "",
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        创建进度任务
        
        Args:
            progress_type: 进度类型
            total: 总数
            message: 初始消息
            metadata: 元数据
        
        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = ProgressTask(
            task_id=task_id,
            progress_type=progress_type,
            total=total,
            current=0,
            message=message,
            metadata=metadata or {},
        )
        
        self._tasks[task_id] = task
        self._notify_callbacks(task)
        
        logger.info(f"Task created: {task_id} ({progress_type.value}), total={total}")
        
        return task_id
    
    def update(
        self,
        task_id: str,
        current: Optional[int] = None,
        increment: int = 1,
        message: Optional[str] = None,
    ):
        """
        更新进度
        
        Args:
            task_id: 任务 ID
            current: 当前进度（绝对值）
            increment: 增量（如果 current 未指定）
            message: 更新消息
        """
        if task_id not in self._tasks:
            logger.warning(f"Task not found: {task_id}")
            return
        
        task = self._tasks[task_id]
        
        if current is not None:
            task.current = min(current, task.total)
        else:
            task.current = min(task.current + increment, task.total)
        
        if message:
            task.message = message
        
        self._notify_callbacks(task)
    
    def complete(
        self,
        task_id: str,
        result: Dict[str, Any] = None,
        message: str = "Completed",
    ):
        """
        标记任务完成
        
        Args:
            task_id: 任务 ID
            result: 结果数据
            message: 完成消息
        """
        if task_id not in self._tasks:
            logger.warning(f"Task not found: {task_id}")
            return
        
        task = self._tasks[task_id]
        task.current = task.total
        task.status = "completed"
        task.end_time = time.time()
        task.message = message
        task.result = result or {}
        
        self._notify_callbacks(task)
        
        logger.info(f"Task completed: {task_id}, elapsed={task.elapsed_seconds:.1f}s")
    
    def fail(
        self,
        task_id: str,
        error: str,
        message: str = "Failed",
    ):
        """
        标记任务失败
        
        Args:
            task_id: 任务 ID
            error: 错误信息
            message: 失败消息
        """
        if task_id not in self._tasks:
            logger.warning(f"Task not found: {task_id}")
            return
        
        task = self._tasks[task_id]
        task.status = "failed"
        task.end_time = time.time()
        task.message = message
        task.result = {"error": error}
        
        self._notify_callbacks(task)
        
        logger.error(f"Task failed: {task_id}, error={error}")
    
    def get_task(self, task_id: str) -> Optional[ProgressTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ProgressTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_active_tasks(self) -> List[ProgressTask]:
        """获取活跃任务"""
        return [t for t in self._tasks.values() if t.status == "running"]
    
    def clear_completed(self, max_age_seconds: int = 3600):
        """清理已完成的任务"""
        now = time.time()
        to_remove = [
            task_id for task_id, task in self._tasks.items()
            if task.status in ("completed", "failed") and (now - (task.end_time or 0)) > max_age_seconds
        ]
        
        for task_id in to_remove:
            del self._tasks[task_id]
        
        if to_remove:
            logger.info(f"Cleared {len(to_remove)} completed tasks")
    
    def _notify_callbacks(self, task: ProgressTask):
        """通知回调函数"""
        for callback in self._callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Callback error: {e}")


_tracker_instance: Optional[ProgressTracker] = None


def get_progress_tracker() -> ProgressTracker:
    """获取进度追踪器单例"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ProgressTracker()
    return _tracker_instance


class ProgressContext:
    """
    进度上下文管理器
    
    用于简化进度追踪的使用。
    
    用法：
        with ProgressContext(ProgressType.BACKTEST, total=100) as progress:
            for i in range(100):
                # 处理
                progress.update(message=f"Processing {i}")
    """
    
    def __init__(
        self,
        progress_type: ProgressType,
        total: int,
        message: str = "",
        metadata: Dict[str, Any] = None,
    ):
        self.tracker = get_progress_tracker()
        self.progress_type = progress_type
        self.total = total
        self.message = message
        self.metadata = metadata
        self.task_id: Optional[str] = None
    
    def __enter__(self):
        self.task_id = self.tracker.create_task(
            self.progress_type,
            self.total,
            self.message,
            self.metadata,
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.tracker.fail(self.task_id, str(exc_val))
        else:
            self.tracker.complete(self.task_id)
        return False
    
    def update(self, current: Optional[int] = None, increment: int = 1, message: Optional[str] = None):
        """更新进度"""
        self.tracker.update(self.task_id, current, increment, message)
    
    def complete(self, result: Dict[str, Any] = None, message: str = "Completed"):
        """完成"""
        self.tracker.complete(self.task_id, result, message)


class ProgressBar:
    """
    终端进度条
    
    用于在终端显示进度条。
    
    用法：
        bar = ProgressBar(total=100, desc="Processing")
        for i in range(100):
            bar.update(1)
        bar.close()
    """
    
    def __init__(
        self,
        total: int,
        desc: str = "",
        width: int = 50,
        task_id: Optional[str] = None,
    ):
        self.total = total
        self.desc = desc
        self.width = width
        self.task_id = task_id
        self.current = 0
        self.start_time = time.time()
        self.last_update = 0
    
    def update(self, n: int = 1, message: Optional[str] = None):
        """更新进度"""
        self.current = min(self.current + n, self.total)
        
        now = time.time()
        if now - self.last_update < 0.1 and self.current < self.total:
            return
        
        self.last_update = now
        
        elapsed = now - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0
        eta = (self.total - self.current) / rate if rate > 0 else 0
        
        percent = self.current / self.total * 100
        filled = int(self.width * self.current / self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        
        desc = self.desc
        if message:
            desc = f"{self.desc} - {message}"
        
        line = f"\r{desc}: |{bar}| {percent:5.1f}% {self.current}/{self.total} [{elapsed:.1f}s<{eta:.1f}s, {rate:.1f}it/s]"
        
        print(line, end="", flush=True)
        
        if self.current >= self.total:
            print()
    
    def close(self):
        """关闭进度条"""
        if self.current < self.total:
            self.current = self.total
            self.update(0)


def create_progress_bar(
    total: int,
    desc: str = "",
    task_id: Optional[str] = None,
) -> ProgressBar:
    """创建进度条"""
    return ProgressBar(total, desc, task_id=task_id)
