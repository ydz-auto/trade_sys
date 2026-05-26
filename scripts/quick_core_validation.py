#!/usr/bin/env python3
"""快速验证架构优化后的核心功能"""
import sys
import os
from pathlib import Path

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from infrastructure.acceleration import DeviceManager, CPUExecutor

logger = get_logger("quick_test")


def test_device_manager():
    """测试设备管理器"""
    print("=" * 80)
    print("测试 DeviceManager")
    print("=" * 80)
    
    device_info = DeviceManager.detect()
    print(f"设备类型: {device_info.device_type}")
    print(f"设备名称: {device_info.device_name}")
    print(f"是 GPU: {device_info.is_gpu}")
    print("=" * 80)
    print()


def test_cpu_executor_simple():
    """测试 CPUExecutor 的基本功能"""
    print("=" * 80)
    print("测试 CPUExecutor (简化版)")
    print("=" * 80)
    
    def simple_task(value):
        return value * 2
    
    executor = CPUExecutor(executor_type="process", max_workers=4)
    
    tasks = [1, 2, 3, 4, 5, 6, 7, 8]
    
    print(f"任务: {tasks}")
    
    # 简化执行
    import time
    start = time.time()
    results = executor.execute(
        func=lambda x: simple_task(x),
        tasks=tasks
    )
    elapsed = time.time() - start
    
    print(f"结果: {[r.result for r in results if r is not None and r.error is None]}")
    print(f"耗时: {elapsed:.3f}秒")
    print(f"错误: {[r.error for r in results if r is not None and r.error is not None]}")
    print("=" * 80)
    print()


def test_script_import():
    """测试脚本模块能否被正确导入"""
    print("=" * 80)
    print("测试脚本模块导入")
    print("=" * 80)
    
    try:
        from scripts.run_walkforward_fixed import (
            WalkForwardRunner,
            DEFAULT_PARAM_GRIDS,
            STRATEGY_MAPPING
        )
        print("✅ WalkForwardRunner 导入成功")
        print(f"策略数量: {len(STRATEGY_MAPPING)}")
        print(f"默认参数网格数量: {len(DEFAULT_PARAM_GRIDS)}")
        
        # 测试一个策略的参数网格
        strategy_id = "long_liquidation_bounce"
        param_grid = DEFAULT_PARAM_GRIDS.get(strategy_id, {})
        
        from itertools import product
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        num_combinations = len(list(product(*values)))
        print(f"{strategy_id} 的参数组合数: {num_combinations}")
        
        print("✅ 模块导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
    print("=" * 80)


if __name__ == "__main__":
    print("快速验证核心功能测试")
    print()
    
    test_device_manager()
    test_cpu_executor_simple()
    test_script_import()
    
    print("\n所有测试完成!")
