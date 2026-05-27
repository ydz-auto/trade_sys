"""
Infrastructure Acceleration Module

提供底层加速能力：
- DeviceManager: 设备检测和管理
- CPUExecutor: CPU 并行执行器
- GPUExecutor: GPU 执行器
- AccelerationService: 统一加速服务

PyTorch 辅助接口（用于 GPU 加速的特征计算和 LSTM）：
- torch: PyTorch 模块（可选）
- device: 当前设备
- is_gpu: 是否使用 GPU
- to_gpu: 将数据移动到 GPU
- to_cpu: 将数据移动到 CPU
- get_accelerator_info: 获取加速信息
- clear_cache: 清理 GPU 缓存
- synchronize: GPU 同步

架构：
    ReplayRuntime / SignalRuntime / ExecutionRuntime
            │
            ▼
        Engines (BacktestEngine, OptimizationEngine, FeatureEngine)
            │
            ▼
    AccelerationService (统一入口)
            │
     ┌──────┼──────┐
     ▼      ▼      ▼
    CPU   CUDA    MPS

用法：
    from infrastructure.acceleration import (
        AccelerationService,
        DeviceManager,
        CPUExecutor,
        GPUExecutor,
        # PyTorch 接口
        torch, device, is_gpu, to_gpu, to_cpu, get_accelerator_info
    )
    
    # 统一入口
    service = AccelerationService()
    results = service.parallel_map(func, tasks)
    
    # 设备检测
    device_info = DeviceManager.detect()
    if device_info.is_gpu:
        # 使用 GPU
"""

import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

# 尝试导入 PyTorch（可选）
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None
    _TORCH_AVAILABLE = False


from .device_manager import DeviceManager, DeviceInfo
from .cpu_executor import CPUExecutor, ExecutionResult
from .gpu_executor import GPUExecutor, GPUResult
from .acceleration_service import AccelerationService, AccelerationConfig


# 初始化设备信息
_device_info: Optional[DeviceInfo] = None


def _init_once():
    """初始化设备信息（只执行一次）"""
    global _device_info
    if _device_info is None:
        _device_info = DeviceManager.detect()


# 设备相关的变量和函数
def get_device():
    """获取当前设备"""
    _init_once()
    
    if _TORCH_AVAILABLE and _device_info:
        if _device_info.device_type == "cuda":
            return torch.device("cuda")
        elif _device_info.device_type == "mps":
            return torch.device("mps")
    
    return torch.device("cpu") if _TORCH_AVAILABLE else None


def get_accelerator_info() -> Dict[str, Any]:
    """获取加速信息"""
    _init_once()
    
    info = {
        "device_type": "cpu",
        "device_name": "CPU",
        "is_gpu": False,
        "memory_gb": None,
        "cores": None,
        "extra_info": {},
        "torch_available": _TORCH_AVAILABLE
    }
    
    if _device_info:
        info.update({
            "device_type": _device_info.device_type,
            "device_name": _device_info.device_name,
            "is_gpu": _device_info.is_gpu,
            "memory_gb": _device_info.memory_gb,
            "cores": _device_info.cores,
            "extra_info": _device_info.extra_info or {},
        })
    
    return info


def _get_is_gpu():
    """获取是否使用 GPU（延迟初始化）"""
    _init_once()
    return _device_info.is_gpu if _device_info else False


# 设备别名（用于 torch_calculator）
# 注意：使用函数而不是变量，避免初始化问题
device = None  # 将在第一次调用 get_device() 时设置
_is_gpu = False


def get_is_gpu() -> bool:
    """获取是否使用 GPU"""
    global _is_gpu
    _init_once()
    _is_gpu = _device_info.is_gpu if _device_info else False
    return _is_gpu


# 向后兼容的访问
is_gpu = False  # 默认值，实际值在第一次调用 get_is_gpu() 时设置


def to_gpu(data: Any) -> Any:
    """
    将数据移动到 GPU
    
    Args:
        data: 数据，支持 numpy.ndarray, torch.Tensor, list, float/int
        
    Returns:
        移动到 GPU 上的数据
    """
    if not _TORCH_AVAILABLE or not _device_info or not _device_info.is_gpu:
        return data
    
    import numpy as np
    
    if isinstance(data, np.ndarray):
        return torch.tensor(data, device=get_device())
    elif isinstance(data, torch.Tensor):
        return data.to(get_device())
    elif isinstance(data, list):
        return [to_gpu(item) for item in data]
    elif isinstance(data, (int, float)):
        return data
    else:
        return data


def to_cpu(data: Any) -> Any:
    """
    将数据移动到 CPU
    
    Args:
        data: 数据，支持 torch.Tensor
        
    Returns:
        移动到 CPU 上的数据
    """
    if not _TORCH_AVAILABLE:
        return data
    
    if isinstance(data, torch.Tensor):
        if data.is_cuda:
            return data.cpu().numpy()
        else:
            return data.numpy()
    else:
        return data


def clear_cache():
    """清理 GPU 缓存"""
    if _TORCH_AVAILABLE and torch.cuda.is_available():
        torch.cuda.empty_cache()


def synchronize():
    """GPU 同步"""
    if _TORCH_AVAILABLE:
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            # MPS 不需要显式同步
            pass


# 导出接口
__all__ = [
    "DeviceManager",
    "DeviceInfo",
    "CPUExecutor",
    "ExecutionResult",
    "GPUExecutor",
    "GPUResult",
    "AccelerationService",
    "AccelerationConfig",
    # PyTorch 相关
    "torch",
    "device",
    "is_gpu",
    "to_gpu",
    "to_cpu",
    "get_accelerator_info",
    "clear_cache",
    "synchronize",
]
