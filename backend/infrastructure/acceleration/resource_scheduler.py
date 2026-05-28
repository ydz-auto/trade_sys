import math
import logging
import multiprocessing as mp
from dataclasses import dataclass
from typing import Optional

from .device_manager import DeviceManager

logger = logging.getLogger(__name__)


@dataclass
class TaskProfile:
    estimated_rows_per_task: int
    estimated_columns: int
    dtype_size: int = 4
    cpu_intensive: bool = True


@dataclass
class ExecutionPlan:
    max_workers: int
    use_gpu: bool
    batch_size: int
    executor_type: str
    memory_budget_per_worker: int


class ResourceScheduler:

    def __init__(self):
        self._device_info = DeviceManager.detect()
        self._system_memory = DeviceManager.get_system_memory()
        self._available_memory = DeviceManager.get_available_memory()
        self._cpu_cores = mp.cpu_count()

    def estimate_memory_per_worker(self, rows: int, columns: int, dtype_size: int = 4) -> int:
        return rows * columns * dtype_size

    def compute_max_workers(self, estimated_mem_per_worker: int, safety_factor: float = 0.8) -> int:
        if estimated_mem_per_worker <= 0:
            return 1
        max_by_memory = math.floor(self._available_memory * safety_factor / estimated_mem_per_worker)
        return max(1, min(self._cpu_cores, max_by_memory))

    def plan_execution(self, task_profile: TaskProfile) -> ExecutionPlan:
        estimated_mem_per_worker = self.estimate_memory_per_worker(
            rows=task_profile.estimated_rows_per_task,
            columns=task_profile.estimated_columns,
            dtype_size=task_profile.dtype_size,
        )
        safety_factor = 0.8
        max_workers = self.compute_max_workers(estimated_mem_per_worker, safety_factor=safety_factor)

        use_gpu = self._device_info.is_gpu and not task_profile.cpu_intensive

        if self._available_memory < estimated_mem_per_worker and estimated_mem_per_worker > 0:
            ratio = self._available_memory / estimated_mem_per_worker
            batch_size = max(1, int(task_profile.estimated_rows_per_task * ratio))
        else:
            batch_size = task_profile.estimated_rows_per_task

        executor_type = "process" if task_profile.cpu_intensive else "thread"

        return ExecutionPlan(
            max_workers=max_workers,
            use_gpu=use_gpu,
            batch_size=batch_size,
            executor_type=executor_type,
            memory_budget_per_worker=estimated_mem_per_worker,
        )
