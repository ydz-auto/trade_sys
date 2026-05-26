"""
测试加速基础设施

验证架构分层：
- infrastructure/acceleration/device_manager.py: 设备检测
- infrastructure/acceleration/cpu_executor.py: CPU执行器
- infrastructure/acceleration/gpu_executor.py: GPU执行器
- infrastructure/acceleration/acceleration_service.py: 统一服务
"""
import sys
import os
import time
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from infrastructure.acceleration import (
    DeviceManager,
    CPUExecutor,
    AccelerationService,
    AccelerationConfig
)


def test_device_manager():
    """测试设备管理器"""
    print("="*80)
    print("测试 DeviceManager")
    print("="*80)
    
    device = DeviceManager.detect()
    
    print(f"设备类型: {device.device_type}")
    print(f"设备名称: {device.device_name}")
    print(f"是否GPU: {device.is_gpu}")
    if device.memory_gb:
        print(f"内存: {device.memory_gb:.2f} GB")
    if device.cores:
        print(f"核心数: {device.cores}")
    if device.extra_info:
        print(f"额外信息: {device.extra_info}")
    
    print()
    return device


def simple_task(arg):
    """测试任务（模块级别）"""
    value = arg[0] if isinstance(arg, tuple) else arg
    time.sleep(0.05)
    return value * 2


def test_cpu_executor():
    """测试 CPU 执行器"""
    print("\n" + "="*80)
    print("测试 CPUExecutor (多进程)")
    print("="*80)
    
    executor = CPUExecutor(
        executor_type="process",
        max_workers=8
    )
    
    tasks = [(i,) for i in range(16)]
    
    print(f"任务数: {len(tasks)}")
    print(f"执行器: {executor.executor_type}")
    print(f"工作进程: {executor.max_workers}")
    
    start = time.time()
    results = executor.execute(
        func=simple_task,
        tasks=tasks,
        progress_callback=lambda done, total: print(f"  进度: {done}/{total}")
    )
    elapsed = time.time() - start
    
    print(f"\n执行完成!")
    print(f"耗时: {elapsed:.2f}秒")
    print(f"结果数: {len(results)}")
    print(f"首个结果: result={results[0].result}, error={results[0].error}")
    
    return elapsed


def test_acceleration_service():
    """测试统一加速服务"""
    print("\n" + "="*80)
    print("测试 AccelerationService")
    print("="*80)
    
    service = AccelerationService.create_for_optimization(
        enable_multiprocess=True,
        enable_gpu=True,
        max_workers=8
    )
    
    device_info = service.get_device_info()
    print(f"设备信息: {device_info.device_type} ({device_info.device_name})")
    print(f"GPU可用: {service.is_gpu_available()}")
    
    print("\n测试并行映射...")
    tasks = [(i,) for i in range(16)]
    
    start = time.time()
    results = service.parallel_map(
        func=simple_task,
        tasks=tasks,
        executor="process",
        progress_callback=lambda done, total: print(f"  进度: {done}/{total}")
    )
    elapsed = time.time() - start
    
    print(f"\n执行完成!")
    print(f"耗时: {elapsed:.2f}秒")
    print(f"结果数: {len(results)}")
    
    return elapsed


def test_sequential_vs_parallel():
    """对比串行和多进程"""
    print("\n" + "="*80)
    print("性能对比：串行 vs 多进程")
    print("="*80)
    
    tasks = [(i,) for i in range(20)]
    
    # 串行
    seq_executor = CPUExecutor(executor_type="sequential")
    start = time.time()
    seq_results = seq_executor.execute(simple_task, tasks)
    seq_time = time.time() - start
    
    # 多进程
    mp_executor = CPUExecutor(executor_type="process", max_workers=8)
    start = time.time()
    mp_results = mp_executor.execute(simple_task, tasks)
    mp_time = time.time() - start
    
    print(f"串行耗时: {seq_time:.2f}秒")
    print(f"多进程耗时: {mp_time:.2f}秒")
    if mp_time > 0:
        print(f"加速比: {seq_time/mp_time:.2f}x")
    
    return seq_time, mp_time


if __name__ == '__main__':
    device = test_device_manager()
    cpu_time = test_cpu_executor()
    acc_time = test_acceleration_service()
    seq_time, mp_time = test_sequential_vs_parallel()
    
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    print(f"设备: {device.device_type}")
    print(f"CPU执行器测试: {cpu_time:.2f}秒")
    print(f"加速服务测试: {acc_time:.2f}秒")
    print(f"串行: {seq_time:.2f}秒, 多进程: {mp_time:.2f}秒, 加速: {seq_time/mp_time:.2f}x")
    print("="*80)
