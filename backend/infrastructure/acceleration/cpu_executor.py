"""
CPU Executor - CPU 执行器

提供 CPU 并行执行能力：
- ProcessPoolExecutor
- ThreadPoolExecutor
- Sequential

用法：
    executor = CPUExecutor(executor_type="process", max_workers=8)
    results = executor.execute(func, tasks)

    # 灵活模式：submit + as_completed，支持自定义 key 映射
    results = executor.submit_map(func, kwargs_list, keys=["f1", "f2"])
"""
from typing import Callable, List, Any, Optional, Dict, Tuple, Union
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DEFAULT_MEM_PER_TASK = 100 * 1024 * 1024


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: int
    result: Any
    error: Optional[str] = None


@dataclass
class SubmitResult:
    """submit_map 单条结果"""
    key: Any
    result: Any
    error: Optional[str] = None


def get_default_workers() -> int:
    """获取默认 worker 数量（全局唯一计算入口）"""
    return max(1, mp.cpu_count() - 1)


class CPUExecutor:
    """
    CPU 执行器

    支持多种执行模式：
    - process: 多进程（CPU密集型）
    - thread: 多线程（I/O密集型）
    - sequential: 串行（调试用）

    两种调用方式：
    1. execute(): 批量执行，tasks 为 List[tuple]，返回 List[ExecutionResult]
    2. submit_map(): 灵活执行，kwargs_list 为 List[dict]，支持自定义 key 映射

    Example:
        executor = CPUExecutor(
            executor_type="process",
            max_workers=mp.cpu_count() - 1
        )

        results = executor.execute(
            func=my_func,
            tasks=[(arg1,), (arg2,), ...]
        )

        results = executor.submit_map(
            func=my_func,
            kwargs_list=[{"x": 1}, {"x": 2}],
            keys=["task_a", "task_b"]
        )
    """

    def __init__(
        self,
        executor_type: str = "process",
        max_workers: Optional[int] = None,
        memory_budget: Optional[int] = None
    ):
        self.executor_type = executor_type
        self.memory_budget = memory_budget

        if max_workers is None:
            self.max_workers = get_default_workers()
        else:
            self.max_workers = max_workers

        if self.memory_budget is not None:
            self.max_workers = min(self.max_workers, max(1, self.memory_budget // _DEFAULT_MEM_PER_TASK))

        logger.info(f"CPUExecutor initialized: type={executor_type}, max_workers={self.max_workers}")

    def set_memory_budget(self, budget: int) -> None:
        self.memory_budget = budget
        self.max_workers = min(self.max_workers, max(1, self.memory_budget // _DEFAULT_MEM_PER_TASK))
        logger.info(f"Memory budget set: budget={budget}, max_workers={self.max_workers}")

    def execute(
        self,
        func: Callable,
        tasks: List[tuple],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ExecutionResult]:
        """
        执行任务（批量模式）

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

    def submit_map(
        self,
        func: Callable,
        kwargs_list: List[Dict[str, Any]],
        keys: Optional[List[Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[SubmitResult]:
        """
        灵活执行模式：submit + as_completed，支持自定义 key 映射

        适用于需要按 key 追踪每个 future 的场景（如 feature_name → result）。

        Args:
            func: 执行函数，签名需匹配 kwargs 中的参数
            kwargs_list: 每个任务的关键字参数列表
            keys: 可选的 key 列表，用于标识每个任务（默认用索引）
            progress_callback: 进度回调 callback(completed, total)

        Returns:
            List[SubmitResult]: 结果列表，每个结果包含 key / result / error

        Example:
            executor = CPUExecutor(executor_type="thread")
            results = executor.submit_map(
                func=process_feature,
                kwargs_list=[{"name": "rsi"}, {"name": "macd"}],
                keys=["rsi", "macd"]
            )
            for r in results:
                print(r.key, r.result, r.error)
        """
        if keys is None:
            keys = list(range(len(kwargs_list)))

        if len(kwargs_list) <= 1 or self.executor_type == "sequential":
            return self._submit_map_sequential(func, kwargs_list, keys, progress_callback)

        return self._submit_map_parallel(func, kwargs_list, keys, progress_callback)

    def _submit_map_sequential(
        self,
        func: Callable,
        kwargs_list: List[Dict[str, Any]],
        keys: List[Any],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[SubmitResult]:
        """串行执行 submit_map"""
        logger.info(f"Sequential submit_map: {len(kwargs_list)} tasks")
        results = []
        for i, kwargs in enumerate(kwargs_list):
            try:
                result = func(**kwargs)
                results.append(SubmitResult(key=keys[i], result=result))
            except Exception as e:
                logger.warning(f"Task {keys[i]} failed: {e}")
                results.append(SubmitResult(key=keys[i], result=None, error=str(e)))

            if progress_callback and (i + 1) % 10 == 0:
                progress_callback(i + 1, len(kwargs_list))

        if progress_callback:
            progress_callback(len(kwargs_list), len(kwargs_list))

        return results

    def _submit_map_parallel(
        self,
        func: Callable,
        kwargs_list: List[Dict[str, Any]],
        keys: List[Any],
        progress_callback: Optional[Callable[[int, int], None]]
    ) -> List[SubmitResult]:
        """并行执行 submit_map"""
        max_workers = min(self.max_workers, len(kwargs_list))
        if self.memory_budget is not None:
            max_workers = min(max_workers, max(1, self.memory_budget // _DEFAULT_MEM_PER_TASK))
        logger.info(f"Parallel submit_map: {len(kwargs_list)} tasks, workers={max_workers}")

        if self.executor_type == "process":
            executor_class = ProcessPoolExecutor
        elif self.executor_type == "thread":
            executor_class = ThreadPoolExecutor
        else:
            return self._submit_map_sequential(func, kwargs_list, keys, progress_callback)

        results_dict: Dict[Any, SubmitResult] = {}

        with executor_class(max_workers=max_workers) as executor:
            futures = {}
            for i, kwargs in enumerate(kwargs_list):
                future = executor.submit(func, **kwargs)
                futures[future] = keys[i]

            completed = 0
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                    results_dict[key] = SubmitResult(key=key, result=result)
                except Exception as e:
                    logger.warning(f"Task {key} failed: {e}")
                    results_dict[key] = SubmitResult(key=key, result=None, error=str(e))

                completed += 1
                if progress_callback and completed % 10 == 0:
                    progress_callback(completed, len(kwargs_list))

        if progress_callback:
            progress_callback(len(kwargs_list), len(kwargs_list))

        return [results_dict[k] for k in keys if k in results_dict]

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
        if self.memory_budget is not None:
            max_workers = min(max_workers, max(1, self.memory_budget // _DEFAULT_MEM_PER_TASK))
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
