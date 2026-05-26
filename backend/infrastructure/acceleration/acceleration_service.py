"""
Acceleration Service - 统一加速服务

统一入口，自动选择最佳执行设备：
- GPU 可用 -> GPU 执行
- GPU 不可用 -> CPU 多进程

用法：
    from infrastructure.acceleration import AccelerationService
    
    service = AccelerationService()
    
    # 并行计算
    results = service.parallel_map(func, tasks, executor="process")
    
    # GPU 特征计算
    features = service.compute_features(data, calculator)
    
    # 回测并行化
    results = service.parallel_backtest(params_list)
"""
from typing import Callable, List, Any, Optional, Dict
import logging
from dataclasses import dataclass

from .device_manager import DeviceManager, DeviceInfo
from .cpu_executor import CPUExecutor
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
    
    Example:
        service = AccelerationService()
        
        # 自动选择最佳设备
        result = service.parallel_map(
            func=my_func,
            tasks=[(arg1,), (arg2,)],
            executor="process"  # process | thread | sequential
        )
        
        # GPU 特征计算
        features = service.compute_features(
            data_batch,
            calculator=TorchFeatureCalculator()
        )
    """
    
    def __init__(self, config: Optional[AccelerationConfig] = None):
        """
        初始化加速服务
        
        Args:
            config: 加速配置
        """
        self.config = config or AccelerationConfig()
        
        self._device_info = DeviceManager.detect()
        self._cpu_executor = CPUExecutor(
            executor_type="process" if self.config.enable_multiprocess else "sequential",
            max_workers=self.config.max_workers
        )
        self._gpu_executor = GPUExecutor() if self._device_info.is_gpu and self.config.enable_gpu else None
        
        logger.info(
            f"AccelerationService initialized: "
            f"device={self._device_info.device_type}, "
            f"multiprocess={self.config.enable_multiprocess}, "
            f"gpu={self._gpu_executor is not None}"
        )
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备信息"""
        return self._device_info
    
    def is_gpu_available(self) -> bool:
        """检查 GPU 是否可用"""
        return self._gpu_executor is not None and self._gpu_executor.is_available()
    
    def parallel_map(
        self,
        func: Callable,
        tasks: List[tuple],
        executor: str = "process",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        并行映射
        
        Args:
            func: 执行函数（必须是模块级别，可被 pickle）
            tasks: 任务列表
            executor: 执行器类型，"process" | "thread" | "sequential"
            progress_callback: 进度回调
        
        Returns:
            结果列表
        """
        if executor == "sequential" or len(tasks) <= 1:
            cpu_exec = CPUExecutor(executor_type="sequential")
        else:
            cpu_exec = CPUExecutor(
                executor_type=executor,
                max_workers=self.config.max_workers
            )
        
        results = cpu_exec.execute(func, tasks, progress_callback)
        
        return [r.result if r.error is None else None for r in results]
    
    def compute_features(
        self,
        data_batch: List[Any],
        calculator: Callable,
        use_gpu: bool = True
    ) -> List[Any]:
        """
        批量特征计算
        
        Args:
            data_batch: 数据批次
            calculator: 特征计算函数
            use_gpu: 是否使用 GPU
        
        Returns:
            特征列表
        """
        if use_gpu and self._gpu_executor and self._gpu_executor.is_available():
            logger.debug(f"Computing features on GPU: {len(data_batch)} items")
            return self._gpu_executor.compute_batch(data_batch, calculator)
        
        logger.debug(f"Computing features on CPU: {len(data_batch)} items")
        return [calculator(data, device="cpu") for data in data_batch]
    
    def parallel_backtest(
        self,
        params_list: List[Dict[str, Any]],
        backtest_func: Callable,
        executor: str = "process"
    ) -> List[Dict[str, Any]]:
        """
        并行回测
        
        Args:
            params_list: 参数列表
            backtest_func: 回测函数
            executor: 执行器类型
        
        Returns:
            回测结果列表
        """
        tasks = [(params,) for params in params_list]
        
        results = self.parallel_map(backtest_func, tasks, executor)
        
        return results
    
    def batch_process(
        self,
        data: List[Any],
        process_func: Callable,
        batch_size: Optional[int] = None
    ) -> List[Any]:
        """
        批量处理
        
        Args:
            data: 数据列表
            process_func: 处理函数
            batch_size: 批次大小
        
        Returns:
            处理结果
        """
        if batch_size is None:
            batch_size = self.config.gpu_batch_size
        
        results = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            if self._gpu_executor and self._gpu_executor.is_available():
                batch_results = self._gpu_executor.compute_batch(batch, process_func)
            else:
                batch_results = [process_func(item) for item in batch]
            
            results.extend(batch_results)
        
        return results
    
    @staticmethod
    def create_for_optimization(
        enable_multiprocess: bool = True,
        enable_gpu: bool = True,
        max_workers: Optional[int] = None
    ) -> 'AccelerationService':
        """
        创建用于优化的加速服务
        
        Args:
            enable_multiprocess: 启用多进程
            enable_gpu: 启用 GPU
            max_workers: 最大工作进程数
        
        Returns:
            AccelerationService 实例
        """
        config = AccelerationConfig(
            enable_multiprocess=enable_multiprocess,
            enable_gpu=enable_gpu,
            max_workers=max_workers
        )
        return AccelerationService(config=config)
