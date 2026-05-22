#!/usr/bin/env python3
"""
快速验证：基础设施模块是否可以正确导入
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    print("=" * 80)
    print("📦 验证基础设施模块导入")
    print("=" * 80)

    tests = []

    try:
        from infrastructure import (
            torch, device, is_gpu,
            get_clock, set_clock_mode, ClockMode,
            get_systematic_guard,
            get_label_store, set_label_store_mode,
            safe_dataframe, assert_safe_dataframe,
            get_point_in_time_store,
            get_immutable_snapshot_store,
            get_warmup_manager,
            get_feature_lineage,
            create_consistency_verifier,
            get_unified_event_processor,
            get_event_converter
        )

        print("✅ 核心基础设施导入成功！")
        tests.append(("核心基础设施", True))
    except Exception as e:
        print(f"❌ 核心基础设施导入失败: {e}")
        tests.append(("核心基础设施", False))

    try:
        from infrastructure.runtime_clock import RuntimeClock
        from infrastructure.feature_availability import SystematicAvailabilityGuard
        from infrastructure.label_isolation import StrictLabelStore
        print("✅ 核心类导入成功！")
        tests.append(("核心类", True))
    except Exception as e:
        print(f"❌ 核心类导入失败: {e}")
        tests.append(("核心类", False))

    try:
        from services.strategy_service.feature_matrix_v2 import TimeCausalFeatureMatrix
        print("✅ 业务模块导入成功！")
        tests.append(("业务模块", True))
    except Exception as e:
        print(f"❌ 业务模块导入失败: {e}")
        tests.append(("业务模块", False))

    print("\n" + "=" * 80)
    print("📊 测试结果")
    print("=" * 80)

    all_passed = True
    for name, passed in tests:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 所有测试通过！基础设施已就绪！")
    else:
        print("⚠️ 有测试失败，请检查模块路径！")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
