"""
Infrastructure Acceleration Module

提供底层加速能力：
- DeviceManager: 设备检测和管理
- CPUExecutor: CPU 并行执行器
- GPUExecutor: GPU 执行器
- AccelerationService: 统一加速服务

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
        GPUExecutor
    )
    
    # 统一入口
    service = AccelerationService()
    results = service.parallel_map(func, tasks)
    
    # 设备检测
    device = DeviceManager.detect()
    if device.is_gpu:
        # 使用 GPU
"""

from .device_manager import DeviceManager, DeviceInfo
from .cpu_executor import CPUExecutor, ExecutionResult
from .gpu_executor import GPUExecutor, GPUResult
from .acceleration_service import AccelerationService, AccelerationConfig

__all__ = [
    "DeviceManager",
    "DeviceInfo",
    "CPUExecutor",
    "ExecutionResult",
    "GPUExecutor",
    "GPUResult",
    "AccelerationService",
    "AccelerationConfig",
]
