"""
GPU Executor - GPU 执行器

提供 GPU 加速执行能力：
- CUDA (NVIDIA GPU)
- MPS (Apple Silicon GPU)

GPU 不可用时，自动 fallback 到 CPUExecutor 并行执行（而非串行）。

用法：
    executor = GPUExecutor()
    results = executor.execute(func, data)
    batch_results = executor.compute_batch(data_list, compute_func)
"""
from typing import Callable, Any, Optional, List, Dict
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GPUResult:
    """GPU 执行结果"""
    result: Any
    device: str
    error: Optional[str] = None


class GPUExecutor:
    """
    GPU 执行器

    封装 GPU 操作：
    - 批量数据处理
    - 特征计算
    - 模型推理

    GPU 不可用时，fallback 到 CPUExecutor 多线程并行（而非串行）。

    Example:
        executor = GPUExecutor()

        features = executor.compute_batch(
            data_list,
            compute_func=torch_calculator
        )
    """

    def __init__(self, device_type: Optional[str] = None, cpu_fallback_workers: Optional[int] = None):
        from .device_manager import DeviceManager

        if device_type:
            self.device_type = device_type
        else:
            self.device_type = DeviceManager.get_device_type()

        self._torch = None
        self._device = None
        self._cpu_fallback_workers = cpu_fallback_workers

        if self.device_type in ["cuda", "mps"]:
            self._init_torch()

    def _init_torch(self):
        try:
            import torch
            self._torch = torch

            if self.device_type == "cuda":
                self._device = torch.device("cuda")
            elif self.device_type == "mps":
                self._device = torch.device("mps")
            else:
                self._device = torch.device("cpu")

            logger.info(f"GPUExecutor initialized: device={self._device}")

        except Exception as e:
            logger.warning(f"PyTorch initialization failed: {e}, falling back to CPU")
            self.device_type = "cpu"
            self._device = None

    def is_available(self) -> bool:
        return self.device_type in ["cuda", "mps"] and self._device is not None

    def _get_cpu_executor(self) -> 'CPUExecutor':
        from .cpu_executor import CPUExecutor
        return CPUExecutor(
            executor_type="thread",
            max_workers=self._cpu_fallback_workers
        )

    def execute(
        self,
        func: Callable,
        data: Any,
        use_batch: bool = True
    ) -> Any:
        if not self.is_available():
            logger.warning("GPU not available, falling back to CPU")
            return func(data, device="cpu")

        try:
            return func(data, device=self._device)
        except Exception as e:
            logger.error(f"GPU execution failed: {e}")
            return func(data, device="cpu")

    def compute_batch(
        self,
        data_list: List[Any],
        compute_func: Callable
    ) -> List[Any]:
        if not self.is_available():
            logger.warning("GPU not available, using CPUExecutor thread pool for batch compute")
            return self._compute_batch_cpu_parallel(data_list, compute_func)

        try:
            import torch

            tensors = []
            for data in data_list:
                if isinstance(data, list):
                    tensor = torch.tensor(data, device=self._device)
                elif hasattr(data, 'values'):
                    tensor = torch.from_numpy(data.values).float().to(self._device)
                else:
                    tensor = torch.tensor(data, device=self._device)
                tensors.append(tensor)

            results = []
            for tensor in tensors:
                result = compute_func(tensor)
                if isinstance(result, torch.Tensor):
                    result = result.cpu().numpy()
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"GPU batch compute failed: {e}, falling back to CPUExecutor")
            return self._compute_batch_cpu_parallel(data_list, compute_func)

    def _compute_batch_cpu_parallel(
        self,
        data_list: List[Any],
        compute_func: Callable
    ) -> List[Any]:
        """CPU 并行 fallback：用 CPUExecutor 多线程替代串行"""
        executor = self._get_cpu_executor()
        kwargs_list = [{"data": data, "device": "cpu"} for data in data_list]
        submit_results = executor.submit_map(compute_func, kwargs_list)
        return [r.result for r in submit_results]

    def to_device(self, data: Any) -> Any:
        if not self.is_available():
            return data

        try:
            import torch

            if isinstance(data, list):
                return torch.tensor(data, device=self._device)
            elif hasattr(data, 'values'):
                return torch.from_numpy(data.values).float().to(self._device)
            else:
                return torch.tensor(data, device=self._device)

        except Exception as e:
            logger.warning(f"Failed to move data to GPU: {e}")
            return data

    def synchronize(self):
        if self._torch and self.device_type == "cuda":
            self._torch.cuda.synchronize()
        elif self._torch and self.device_type == "mps":
            self._torch.mps.synchronize()

    def empty_cache(self):
        if self._torch and self.device_type == "cuda":
            self._torch.cuda.empty_cache()
        elif self._torch and self.device_type == "mps":
            self._torch.mps.empty_cache()
