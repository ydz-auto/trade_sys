"""
Acceleration Service - 统一加速服务

统一入口，自动选择最佳执行设备：
- GPU 可用 -> GPU 执行
- GPU 不可用 -> CPU 多进程/多线程

用法：
    from infrastructure.acceleration import AccelerationService

    service = AccelerationService()

    # 并行计算
    results = service.parallel_map(func, tasks, executor="process")

    # 灵活模式：submit + as_completed
    results = service.submit_map(func, kwargs_list, keys=["f1", "f2"])

    # GPU 特征计算
    features = service.compute_features(data, calculator)

    # 回测并行化
    results = service.parallel_backtest(params_list)

    # 获取 CPUExecutor 供其他模块直接使用
    cpu_exec = service.get_cpu_executor(executor_type="thread")
"""
from typing import Callable, List, Any, Optional, Dict
import logging
from dataclasses import dataclass

from .device_manager import DeviceManager, DeviceInfo
from .cpu_executor import CPUExecutor, SubmitResult, get_default_workers
from .gpu_executor import GPUExecutor

logger = logging.getLogger(__name__)


@dataclass
class AccelerationConfig:
    """加速配置"""
    enable_multiprocess: bool = True
    enable_gpu: bool = True
    max_workers: Optional[int] = None
    gpu_batch_size: int = 1000
    fallback_to_cpu: bool = True


class AccelerationService:
    """
    统一加速服务

    自动选择最佳执行策略：
    1. GPU 可用 -> GPU 加速
    2. GPU 不可用 + 多进程开启 -> CPU 多进程
    3. 否则 -> CPU 串行

    提供 get_cpu_executor() 供其他模块直接获取 CPUExecutor，
    避免各模块自行硬编码 ThreadPoolExecutor / ProcessPoolExecutor。

    Example:
        service = AccelerationService()

        result = service.parallel_map(
            func=my_func,
            tasks=[(arg1,), (arg2,)],
            executor="process"
        )

        features = service.compute_features(
            data_batch,
            calculator=TorchFeatureCalculator()
        )

        cpu_exec = service.get_cpu_executor(executor_type="thread")
        results = cpu_exec.submit_map(func, kwargs_list, keys=feature_names)
    """

    def __init__(self, config: Optional[AccelerationConfig] = None):
        self.config = config or AccelerationConfig()

        self._device_info = DeviceManager.detect()
        self._cpu_executor = CPUExecutor(
            executor_type="process" if self.config.enable_multiprocess else "sequential",
            max_workers=self.config.max_workers
        )
        self._thread_executor: Optional[CPUExecutor] = None
        self._gpu_executor = GPUExecutor(
            cpu_fallback_workers=self.config.max_workers
        ) if self._device_info.is_gpu and self.config.enable_gpu else None

        logger.info(
            f"AccelerationService initialized: "
            f"device={self._device_info.device_type}, "
            f"multiprocess={self.config.enable_multiprocess}, "
            f"gpu={self._gpu_executor is not None}"
        )

    def get_device_info(self) -> DeviceInfo:
        return self._device_info

    def is_gpu_available(self) -> bool:
        return self._gpu_executor is not None and self._gpu_executor.is_available()

    def get_cpu_executor(self, executor_type: str = "process") -> CPUExecutor:
        """
        获取 CPUExecutor 实例（复用，避免各模块自行 new）

        Args:
            executor_type: "process" | "thread" | "sequential"

        Returns:
            CPUExecutor 实例
        """
        if executor_type == "process" or executor_type == "sequential":
            if executor_type == self._cpu_executor.executor_type:
                return self._cpu_executor
            return CPUExecutor(
                executor_type=executor_type,
                max_workers=self.config.max_workers
            )

        if executor_type == "thread":
            if self._thread_executor is None:
                self._thread_executor = CPUExecutor(
                    executor_type="thread",
                    max_workers=self.config.max_workers
                )
            return self._thread_executor

        return self._cpu_executor

    def get_default_workers(self) -> int:
        """获取默认 worker 数量（全局配置入口）"""
        if self.config.max_workers is not None:
            return self.config.max_workers
        return get_default_workers()

    def parallel_map(
        self,
        func: Callable,
        tasks: List[tuple],
        executor: str = "process",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        if executor == "sequential" or len(tasks) <= 1:
            cpu_exec = CPUExecutor(executor_type="sequential")
        else:
            cpu_exec = self.get_cpu_executor(executor_type=executor)

        results = cpu_exec.execute(func, tasks, progress_callback)

        return [r.result if r.error is None else None for r in results]

    def submit_map(
        self,
        func: Callable,
        kwargs_list: List[Dict[str, Any]],
        keys: Optional[List[Any]] = None,
        executor_type: str = "thread",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[SubmitResult]:
        """
        灵活并行模式：submit + as_completed，支持自定义 key 映射

        Args:
            func: 执行函数，签名需匹配 kwargs 中的参数
            kwargs_list: 每个任务的关键字参数列表
            keys: 可选的 key 列表，用于标识每个任务
            executor_type: 执行器类型，"process" | "thread" | "sequential"
            progress_callback: 进度回调

        Returns:
            List[SubmitResult]: 结果列表
        """
        cpu_exec = self.get_cpu_executor(executor_type=executor_type)
        return cpu_exec.submit_map(func, kwargs_list, keys, progress_callback)

    def compute_features(
        self,
        data_batch: List[Any],
        calculator: Callable,
        use_gpu: bool = True
    ) -> List[Any]:
        if use_gpu and self._gpu_executor and self._gpu_executor.is_available():
            logger.debug(f"Computing features on GPU: {len(data_batch)} items")
            return self._gpu_executor.compute_batch(data_batch, calculator)

        logger.debug(f"Computing features on CPU: {len(data_batch)} items")
        cpu_exec = self.get_cpu_executor(executor_type="thread")
        kwargs_list = [{"data": data, "device": "cpu"} for data in data_batch]
        submit_results = cpu_exec.submit_map(calculator, kwargs_list)
        return [r.result for r in submit_results]

    def parallel_backtest(
        self,
        params_list: List[Dict[str, Any]],
        backtest_func: Callable,
        executor: str = "process"
    ) -> List[Dict[str, Any]]:
        tasks = [(params,) for params in params_list]
        results = self.parallel_map(backtest_func, tasks, executor)
        return results

    def batch_process(
        self,
        data: List[Any],
        process_func: Callable,
        batch_size: Optional[int] = None
    ) -> List[Any]:
        if batch_size is None:
            batch_size = self.config.gpu_batch_size

        results = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]

            if self._gpu_executor and self._gpu_executor.is_available():
                batch_results = self._gpu_executor.compute_batch(batch, process_func)
            else:
                cpu_exec = self.get_cpu_executor(executor_type="thread")
                kwargs_list = [{"item": item} for item in batch]
                submit_results = cpu_exec.submit_map(process_func, kwargs_list)
                batch_results = [r.result for r in submit_results]

            results.extend(batch_results)

        return results

    @staticmethod
    def create_for_optimization(
        enable_multiprocess: bool = True,
        enable_gpu: bool = True,
        max_workers: Optional[int] = None
    ) -> 'AccelerationService':
        config = AccelerationConfig(
            enable_multiprocess=enable_multiprocess,
            enable_gpu=enable_gpu,
            max_workers=max_workers
        )
        return AccelerationService(config=config)
