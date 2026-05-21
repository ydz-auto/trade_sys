"""
GPU Acceleration Layer - PyTorch 统一加速层

统一使用 PyTorch 作为 GPU 加速框架：
- CUDA (NVIDIA GPU) - Windows/Linux
- MPS (Apple Silicon) - Mac M1/M2/M3/M4
- CPU (fallback) - 任何平台

优势：
1. LSTM 深度学习原生支持
2. 技术指标计算也能 GPU 加速
3. 无需 GPU 内存拷贝
4. 统一技术栈

用法：
    from shared.acceleration import torch, device, is_gpu
    
    # 自动选择最佳设备
    tensor = torch.tensor([1, 2, 3], device=device)
    
    # 检查 GPU 状态
    print(f"Using: {device}, GPU: {is_gpu}")
"""

from typing import Optional, Tuple, Any, List, Union
import os
import warnings
import numpy as np

_torch = None
_device = None
_is_gpu = False
_device_info = {}


def _init_torch():
    """初始化 PyTorch 和设备"""
    global _torch, _device, _is_gpu, _device_info
    
    if _torch is not None:
        return
    
    try:
        import torch
        _torch = torch
    except ImportError:
        raise ImportError(
            "PyTorch is required. Install with:\n"
            "  pip install torch\n"
            "For GPU support:\n"
            "  NVIDIA: pip install torch --index-url https://download.pytorch.org/whl/cu121\n"
            "  Mac: pip install torch (MPS auto-enabled)"
        )
    
    env_device = os.environ.get("TORCH_DEVICE", "").lower()
    
    if env_device == "cpu":
        _device = _torch.device("cpu")
        _is_gpu = False
        _device_info = {"type": "cpu", "name": "PyTorch CPU"}
    
    elif env_device == "cuda":
        if _torch.cuda.is_available():
            _device = _torch.device("cuda")
            _is_gpu = True
            props = _torch.cuda.get_device_properties(0)
            _device_info = {
                "type": "cuda",
                "name": props.name,
                "memory_total_gb": props.total_memory / (1024**3),
                "multi_processor_count": props.multi_processor_count,
            }
        else:
            warnings.warn("CUDA requested but not available, falling back to CPU")
            _device = _torch.device("cpu")
            _is_gpu = False
    
    elif env_device == "mps":
        if hasattr(_torch.backends, 'mps') and _torch.backends.mps.is_available():
            _device = _torch.device("mps")
            _is_gpu = True
            _device_info = {"type": "mps", "name": "Apple Silicon GPU"}
        else:
            warnings.warn("MPS requested but not available, falling back to CPU")
            _device = _torch.device("cpu")
            _is_gpu = False
    
    else:
        if _torch.cuda.is_available():
            _device = _torch.device("cuda")
            _is_gpu = True
            props = _torch.cuda.get_device_properties(0)
            _device_info = {
                "type": "cuda",
                "name": props.name,
                "memory_total_gb": props.total_memory / (1024**3),
                "multi_processor_count": props.multi_processor_count,
            }
        elif hasattr(_torch.backends, 'mps') and _torch.backends.mps.is_available():
            _device = _torch.device("mps")
            _is_gpu = True
            _device_info = {"type": "mps", "name": "Apple Silicon GPU"}
        else:
            _device = _torch.device("cpu")
            _is_gpu = False
            _device_info = {"type": "cpu", "name": "PyTorch CPU"}
    
    _log_device_info()


def _log_device_info():
    """打印设备信息"""
    info = _device_info
    dtype = _device.type
    
    if dtype == "cuda":
        print(f"🚀 PyTorch GPU: CUDA ({info['name']}, {info['memory_total_gb']:.1f}GB)")
    elif dtype == "mps":
        print(f"🚀 PyTorch GPU: MPS (Apple Silicon)")
    else:
        print(f"💻 PyTorch CPU")


def get_torch():
    """获取 PyTorch 模块"""
    if _torch is None:
        _init_torch()
    return _torch


def get_device():
    """获取当前设备"""
    if _device is None:
        _init_torch()
    return _device


def is_gpu_available() -> bool:
    """检查是否使用 GPU"""
    if _device is None:
        _init_torch()
    return _is_gpu


def get_device_info() -> dict:
    """获取设备信息"""
    if _device_info is None:
        _init_torch()
    return _device_info.copy()


torch = get_torch()
device = get_device()
is_gpu = is_gpu_available()


def to_gpu(data: Union[np.ndarray, list]) -> "torch.Tensor":
    """
    将数据移动到 GPU
    
    Args:
        data: NumPy 数组或列表
    
    Returns:
        PyTorch Tensor（在 GPU 上，如果可用）
    """
    t = get_torch()
    d = get_device()
    
    if isinstance(data, np.ndarray):
        return t.from_numpy(data).float().to(d)
    return t.tensor(data, device=d)


def to_cpu(tensor: "torch.Tensor") -> np.ndarray:
    """
    将 Tensor 移动到 CPU 并转为 NumPy
    
    Args:
        tensor: PyTorch Tensor
    
    Returns:
        NumPy 数组
    """
    return tensor.detach().cpu().numpy()


def zeros(shape: Tuple[int, ...], dtype=None) -> "torch.Tensor":
    """创建零张量"""
    t = get_torch()
    d = get_device()
    dtype = dtype or t.float32
    return t.zeros(shape, dtype=dtype, device=d)


def ones(shape: Tuple[int, ...], dtype=None) -> "torch.Tensor":
    """创建一张量"""
    t = get_torch()
    d = get_device()
    dtype = dtype or t.float32
    return t.ones(shape, dtype=dtype, device=d)


def tensor(data: Any, dtype=None) -> "torch.Tensor":
    """创建张量"""
    t = get_torch()
    d = get_device()
    dtype = dtype or t.float32
    return t.tensor(data, dtype=dtype, device=d)


def from_numpy(arr: np.ndarray) -> "torch.Tensor":
    """从 NumPy 创建张量"""
    t = get_torch()
    d = get_device()
    return t.from_numpy(arr).to(d)


def get_accelerator_info() -> dict:
    """获取加速器完整信息"""
    return {
        "backend": "pytorch",
        "device_type": _device.type if _device else "unknown",
        "is_gpu": _is_gpu,
        "device_info": _device_info.copy() if _device_info else {},
        "torch_version": _torch.__version__ if _torch else "not loaded",
    }


def clear_cache():
    """清理 GPU 缓存"""
    if _device is None:
        return
    
    if _device.type == "cuda":
        _torch.cuda.empty_cache()
    elif _device.type == "mps":
        _torch.mps.empty_cache()


def synchronize():
    """同步 GPU"""
    if _device is None:
        return
    
    if _device.type == "cuda":
        _torch.cuda.synchronize()
    elif _device.type == "mps":
        _torch.mps.synchronize()
