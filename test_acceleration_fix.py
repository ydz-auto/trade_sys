"""
快速测试：验证 acceleration 模块是否正常工作
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from infrastructure.acceleration import (
        DeviceManager,
        AccelerationService,
        get_accelerator_info,
        get_is_gpu,
        get_device,
        to_gpu,
        to_cpu,
        clear_cache,
        synchronize,
        torch,
    )
    
    print("=" * 80)
    print("Acceleration Module Test")
    print("=" * 80)
    print()
    
    # 1. 测试 get_accelerator_info
    print("1. Testing get_accelerator_info()")
    info = get_accelerator_info()
    print(f"   Device type: {info['device_type']}")
    print(f"   Device name: {info['device_name']}")
    print(f"   Is GPU: {info['is_gpu']}")
    print(f"   Torch available: {info['torch_available']}")
    if info['memory_gb']:
        print(f"   Memory: {info['memory_gb']:.2f} GB")
    print()
    
    # 2. 测试 DeviceManager
    print("2. Testing DeviceManager")
    device_info = DeviceManager.detect()
    print(f"   Device detected: {device_info}")
    print(f"   Type: {device_info.device_type}")
    print(f"   Is GPU: {device_info.is_gpu}")
    print()
    
    # 3. 测试 get_is_gpu 和 get_device
    print("3. Testing get_is_gpu() and get_device()")
    print(f"   is_gpu: {get_is_gpu()}")
    if torch is not None:
        dev = get_device()
        print(f"   PyTorch device: {dev}")
    else:
        print("   PyTorch not available")
    print()
    
    # 4. 测试 AccelerationService
    print("4. Testing AccelerationService")
    service = AccelerationService()
    print(f"   Service initialized")
    print(f"   Device info from service: {service.get_device_info().device_type}")
    print(f"   GPU available: {service.is_gpu_available()}")
    print()
    
    # 5. 简单的测试函数
    print("5. Testing basic functions")
    if get_is_gpu() and torch is not None:
        import numpy as np
        test_data = np.array([1, 2, 3, 4, 5], dtype=np.float32)
        print(f"   Original data (numpy): {test_data}")
        
        gpu_data = to_gpu(test_data)
        print(f"   Data on GPU (tensor): {gpu_data}")
        
        cpu_data = to_cpu(gpu_data)
        print(f"   Data back to CPU (numpy): {cpu_data}")
        
        print()
        print("GPU operations successful!")
    else:
        print("GPU not available or PyTorch not installed, skipping GPU test")
    
    print()
    print("=" * 80)
    print("All tests passed!")
    print("=" * 80)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
