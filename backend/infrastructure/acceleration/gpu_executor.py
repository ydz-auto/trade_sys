"""
GPU Executor - GPU 执行器

提供 GPU 加速执行能力：
- CUDA (NVIDIA GPU)
- MPS (Apple Silicon GPU)

用法：
    executor = GPUExecutor()
    results = executor.execute(func, data)
"""
from typing import Callable, Any, Optional, List
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
    
    Example:
        executor = GPUExecutor()
        
        features = executor.compute_features(
            data_batch,
            feature_func=torch_calculator
        )
    """
    
    def __init__(self, device_type: Optional[str] = None):
        """
        初始化 GPU 执行器
        
        Args:
            device_type: 强制设备类型，"cuda" | "mps" | "cpu"
        """
        from .device_manager import DeviceManager
        
        if device_type:
            self.device_type = device_type
        else:
            self.device_type = DeviceManager.get_device_type()
        
        self._torch = None
        self._device = None
        
        if self.device_type in ["cuda", "mps"]:
            self._init_torch()
    
    def _init_torch(self):
        """初始化 PyTorch"""
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
        """检查 GPU 是否可用"""
        return self.device_type in ["cuda", "mps"] and self._device is not None
    
    def execute(
        self,
        func: Callable,
        data: Any,
        use_batch: bool = True
    ) -> Any:
        """
        执行 GPU 操作
        
        Args:
            func: GPU 函数
            data: 输入数据
            use_batch: 是否批量处理
        
        Returns:
            GPU 计算结果
        """
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
        """
        批量计算
        
        Args:
            data_list: 数据列表
            compute_func: 计算函数
        
        Returns:
            计算结果列表
        """
        if not self.is_available():
            logger.warning("GPU not available, using CPU for batch compute")
            return [compute_func(data, device="cpu") for data in data_list]
        
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
            logger.error(f"GPU batch compute failed: {e}")
            return [compute_func(data, device="cpu") for data in data_list]
    
    def to_device(self, data: Any) -> Any:
        """
        将数据移动到 GPU
        
        Args:
            data: 输入数据
        
        Returns:
            GPU 上的数据
        """
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
        """同步 GPU"""
        if self._torch and self.device_type == "cuda":
            self._torch.cuda.synchronize()
        elif self._torch and self.device_type == "mps":
            self._torch.mps.synchronize()
    
    def empty_cache(self):
        """清空 GPU 缓存"""
        if self._torch and self.device_type == "cuda":
            self._torch.cuda.empty_cache()
        elif self._torch and self.device_type == "mps":
            self._torch.mps.empty_cache()
