#!/usr/bin/env python3
"""
快速验证：基础设施模块是否可以正确导入
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


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

    # 时间权威系统测试
    try:
        from infrastructure.time_authority import (
            get_time_authority,
            normalize_time_ms,
            ensure_time_ms,
            validate_time_ms,
            check_monotonic,
            to_datetime,
            format_time_ms,
            TimeSource
        )
        print("✅ 时间权威系统导入成功！")
        tests.append(("时间权威系统", True))
    except Exception as e:
        print(f"❌ 时间权威系统导入失败: {e}")
        tests.append(("时间权威系统", False))

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


def test_time_authority():
    """测试时间权威系统功能"""
    print("\n" + "=" * 80)
    print("⏰ 测试时间权威系统")
    print("=" * 80)

    from infrastructure.time_authority import (
        get_time_authority,
        normalize_time_ms,
        validate_time_ms,
        check_monotonic,
        to_datetime,
        format_time_ms
    )

    ta = get_time_authority()
    all_passed = True

    # 测试时间格式转换
    print("\n--- 测试时间格式转换 ---")
    test_cases = [
        ('2025-01-01', 'ISO日期字符串'),
        ('2025-01-01 12:00:00', 'ISO日期时间字符串'),
        (1746272000, '秒时间戳(int)'),
        (1746272000000, '毫秒时间戳(int)'),
        (1746272000.5, '秒时间戳(float)'),
    ]

    for value, desc in test_cases:
        try:
            result = normalize_time_ms(value, source='test')
            assert isinstance(result, int), f"结果不是int类型: {type(result)}"
            print(f"✅ {desc}: {value} -> {result}")
        except Exception as e:
            print(f"❌ {desc}: {value} -> ERROR: {e}")
            all_passed = False

    # 测试单调检查
    print("\n--- 测试单调递增检查 ---")
    ta.reset_monotonic()
    timestamps = [1000, 2000, 3000]
    for ts in timestamps:
        try:
            result = check_monotonic(ts)
            if result:
                print(f"✅ 时间戳 {ts}: 单调递增通过")
            else:
                print(f"❌ 时间戳 {ts}: 非单调递增")
                all_passed = False
        except Exception as e:
            print(f"❌ 时间戳 {ts}: ERROR: {e}")
            all_passed = False

    # 测试时间验证
    print("\n--- 测试时间验证 ---")
    valid_time = 1746272000000
    result = validate_time_ms(valid_time)
    if result.is_valid:
        print(f"✅ 时间验证通过: {valid_time}")
    else:
        print(f"❌ 时间验证失败: {valid_time}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 时间权威系统测试通过！")
    else:
        print("⚠️ 时间权威系统测试失败！")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    import_success = test_imports()
    time_auth_success = test_time_authority()
    sys.exit(0 if (import_success and time_auth_success) else 1)
