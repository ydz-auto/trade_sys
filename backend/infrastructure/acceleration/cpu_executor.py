"""
CPU Executor - CPU 执行器

提供 CPU 并行执行能力：
- ProcessPoolExecutor
- ThreadPoolExecutor
- Sequential

用法：
    executor = CPUExecutor(executor_type="process", max_workers=8)
    results = executor.execute(func, tasks)
"""
from typing import Callable, List, Any, Optional, Dict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: int
    result: Any
    error: Optional[str] = None


class CPUExecutor:
    """
    CPU 执行器
    
    支持多种执行模式：
    - process: 多进程（CPU密集型）
    - thread: 多线程（I/O密集型）
    - sequential: 串行（调试用）
    
    Example:
        executor = CPUExecutor(
            executor_type="process",
            max_workers=mp.cpu_count() - 1
        )
        
        results = executor.execute(
            func=my_func,
            tasks=[(arg1,), (arg2,), ...]
        )
    """
    
    def __init__(
        self,
        executor_type: str = "process",
        max_workers: Optional[int] = None
    ):
        """
        初始化 CPU 执行器
        
        Args:
            executor_type: 执行器类型，"process" | "thread" | "sequential"
            max_workers: 最大工作进程/线程数
        """
        self.executor_type = executor_type
        
        if max_workers is None:
            self.max_workers = max(1, mp.cpu_count() - 1)
        else:
            self.max_workers = max_workers
        
        logger.info(f"CPUExecutor initialized: type={executor_type}, max_workers={self.max_workers}")
    
    def execute(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ExecutionResult]:
        """
        执行任务
        
        Args:
            func: 执行函数（必须是模块级别，可被 pickle）
            tasks: 任务参数列表，每个任务是一个 tuple
            progress_callback: 进度回调 callback(completed, total)
        
        Returns:
            List[ExecutionResult]: 结果列表
        """
        num_tasks = len(tasks)
        
        if self.executor_type == "sequential" or num_tasks <= 1:
            return self._execute_sequential(func, tasks, progress_callback)
        
        return self._execute_parallel(func, tasks, progress_callback)
    
    def _execute_sequential(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[ExecutionResult]:
        """串行执行"""
        logger.info(f"Sequential execution: {len(tasks)} tasks")
        
        results = []
        for i, task in enumerate(tasks):
            try:
                result = func(*task) if isinstance(task, tuple) else func(task)
                results.append(ExecutionResult(task_id=i, result=result))
            except Exception as e:
                logger.warning(f"Task {i} failed: {e}")
                results.append(ExecutionResult(task_id=i, result=None, error=str(e)))
            
            if progress_callback and (i + 1) % 10 == 0:
                progress_callback(i + 1, len(tasks))
        
        if progress_callback:
            progress_callback(len(tasks), len(tasks))
        
        return results
    
    def _execute_parallel(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[ExecutionResult]:
        """并行执行"""
        max_workers = min(self.max_workers, len(tasks))
        logger.info(f"Parallel execution: {len(tasks)} tasks, workers={max_workers}")
        
        if self.executor_type == "process":
            executor_class = ProcessPoolExecutor
        elif self.executor_type == "thread":
            executor_class = ThreadPoolExecutor
        else:
            return self._execute_sequential(func, tasks, progress_callback)
        
        results_dict: Dict[int, ExecutionResult] = {}
        
        with executor_class(max_workers=max_workers) as executor:
            futures = {}
            for i, task in enumerate(tasks):
                future = executor.submit(func, *task) if isinstance(task, tuple) else executor.submit(func, task)
                futures[future] = i
            
            completed = 0
            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result()
                    results_dict[task_id] = ExecutionResult(task_id=task_id, result=result)
                except Exception as e:
                    logger.warning(f"Task {task_id} failed: {e}")
                    results_dict[task_id] = ExecutionResult(task_id=task_id, result=None, error=str(e))
                
                completed += 1
                if progress_callback and completed % 10 == 0:
                    progress_callback(completed, len(tasks))
        
        if progress_callback:
            progress_callback(len(tasks), len(tasks))
        
        return [results_dict[i] for i in sorted(results_dict.keys())]
    
    @staticmethod
    def create_default(max_workers: Optional[int] = None) -> 'CPUExecutor':
        """
        创建默认执行器（多进程）
        
        Args:
            max_workers: 最大工作进程数
        
        Returns:
            CPUExecutor 实例
        """
        return CPUExecutor(
            executor_type="process",
            max_workers=max_workers
        )
