"""
Device Manager - 设备管理器

统一设备检测和管理：
- CPU
- CUDA (NVIDIA GPU)
- MPS (Apple Silicon GPU)

用法：
    device = DeviceManager.detect()
    info = DeviceManager.get_info()
    
    if device.is_gpu:
        # 使用 GPU
    else:
        # 使用 CPU
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
import os
import ctypes
import platform
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """设备信息"""
    device_type: str
    device_name: str
    is_gpu: bool
    memory_gb: Optional[float] = None
    system_memory_gb: Optional[float] = None
    cores: Optional[int] = None
    extra_info: Optional[Dict[str, Any]] = None


class DeviceManager:
    """
    设备管理器
    
    统一检测和管理计算设备
    """
    
    _instance: Optional['DeviceManager'] = None
    _device_info: Optional[DeviceInfo] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_system_memory(cls) -> int:
        try:
            import psutil
            return psutil.virtual_memory().total
        except ImportError:
            pass

        try:
            if platform.system() == "Windows":
                kernel32 = ctypes.windll.kernel32
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                return stat.ullTotalPhys
            else:
                return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (OSError, AttributeError):
            pass

        return 0

    @classmethod
    def get_available_memory(cls) -> int:
        try:
            import psutil
            return psutil.virtual_memory().available
        except ImportError:
            pass

        try:
            if platform.system() == "Windows":
                kernel32 = ctypes.windll.kernel32
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                return stat.ullAvailPhys
        except (OSError, AttributeError):
            pass

        return 0

    @classmethod
    def detect(cls) -> DeviceInfo:
        """
        检测并返回最佳设备
        
        Returns:
            DeviceInfo: 设备信息
        """
        if cls._device_info is not None:
            return cls._device_info
        
        env_device = os.environ.get("TORCH_DEVICE", "").lower()
        
        if env_device == "cpu":
            cls._device_info = cls._detect_cpu()
        elif env_device == "cuda":
            cls._device_info = cls._detect_cuda()
        elif env_device == "mps":
            cls._device_info = cls._detect_mps()
        else:
            cls._device_info = cls._auto_detect()
        
        logger.info(f"Device detected: {cls._device_info}")
        return cls._device_info
    
    @classmethod
    def _detect_cpu(cls) -> DeviceInfo:
        """强制使用 CPU"""
        total_bytes = cls.get_system_memory()
        return DeviceInfo(
            device_type="cpu",
            device_name="CPU",
            is_gpu=False,
            system_memory_gb=total_bytes / (1024 ** 3) if total_bytes else None
        )
    
    @classmethod
    def _detect_cuda(cls) -> DeviceInfo:
        """检测 CUDA GPU"""
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                return DeviceInfo(
                    device_type="cuda",
                    device_name=props.name,
                    is_gpu=True,
                    memory_gb=props.total_memory / (1024**3),
                    cores=props.multi_processor_count,
                    extra_info={
                        "compute_capability": f"{props.major}.{props.minor}",
                        "device_count": torch.cuda.device_count()
                    }
                )
        except Exception as e:
            logger.warning(f"CUDA detection failed: {e}")
        
        logger.warning("CUDA requested but not available, falling back to CPU")
        return cls._detect_cpu()
    
    @classmethod
    def _detect_mps(cls) -> DeviceInfo:
        """检测 MPS (Apple Silicon)"""
        try:
            import torch
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return DeviceInfo(
                    device_type="mps",
                    device_name="Apple Silicon GPU",
                    is_gpu=True,
                    extra_info={"backend": "metal"}
                )
        except Exception as e:
            logger.warning(f"MPS detection failed: {e}")
        
        logger.warning("MPS requested but not available, falling back to CPU")
        return cls._detect_cpu()
    
    @classmethod
    def _auto_detect(cls) -> DeviceInfo:
        """自动检测最佳设备"""
        total_bytes = cls.get_system_memory()
        system_memory_gb = total_bytes / (1024 ** 3) if total_bytes else None

        try:
            import torch
            
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                return DeviceInfo(
                    device_type="cuda",
                    device_name=props.name,
                    is_gpu=True,
                    memory_gb=props.total_memory / (1024**3),
                    cores=props.multi_processor_count,
                    system_memory_gb=system_memory_gb
                )
            
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return DeviceInfo(
                    device_type="mps",
                    device_name="Apple Silicon GPU",
                    is_gpu=True,
                    system_memory_gb=system_memory_gb
                )
        
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
        
        return cls._detect_cpu()
    
    @classmethod
    def get_info(cls) -> DeviceInfo:
        """获取设备信息（兼容别名）"""
        return cls.detect()
    
    @classmethod
    def is_gpu(cls) -> bool:
        """检查是否使用 GPU"""
        return cls.detect().is_gpu
    
    @classmethod
    def get_device_type(cls) -> str:
        """获取设备类型"""
        return cls.detect().device_type
    
    @classmethod
    def reset(cls):
        """重置设备检测（用于测试）"""
        cls._device_info = None
