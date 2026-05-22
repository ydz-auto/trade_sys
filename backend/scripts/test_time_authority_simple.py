#!/usr/bin/env python3
"""
时间权威系统简单测试脚本
可通过 PYTHONPATH=. python scripts/test_time_authority_simple.py 运行
"""

import sys

from infrastructure.time_authority import (
    get_time_authority,
    normalize_time_ms,
    validate_time_ms,
    check_monotonic,
    to_datetime,
    format_time_ms,
    TimeSource
)

def main():
    print("=" * 60)
    print("⏰ 时间权威系统测试")
    print("=" * 60)
    
    ta = get_time_authority()
    all_pass = True
    
    # 测试1: 时间格式转换
    print("\n--- 测试1: 时间格式转换 ---")
    test_cases = [
        ('2025-01-01', 'ISO日期字符串'),
        ('2025-01-01 12:00:00', 'ISO日期时间'),
        (1746272000, '秒时间戳'),
        (1746272000000, '毫秒时间戳'),
        (1746272000.5, '浮点秒时间戳'),
    ]
    
    for value, desc in test_cases:
        try:
            result = normalize_time_ms(value, source='test')
            assert isinstance(result, int), f"结果不是int类型"
            print(f"✅ {desc}: {value!r} -> {result}")
            print(f"   -> datetime: {to_datetime(result)}")
            print(f"   -> formatted: {format_time_ms(result)}")
        except Exception as e:
            print(f"❌ {desc}: {value!r} -> ERROR: {e}")
            all_pass = False
        print()
    
    # 测试2: 单调递增检查
    print("\n--- 测试2: 单调递增检查 ---")
    ta.reset_monotonic()
    timestamps = [1000, 2000, 3000]
    
    for ts in timestamps:
        try:
            result = check_monotonic(ts)
            if result:
                print(f"✅ 时间戳 {ts}: 单调递增通过")
            else:
                print(f"❌ 时间戳 {ts}: 非单调递增")
                all_pass = False
        except Exception as e:
            print(f"❌ 时间戳 {ts}: ERROR: {e}")
            all_pass = False
    
    # 测试3: 时间验证
    print("\n--- 测试3: 时间验证 ---")
    valid_time = 1746272000000
    result = validate_time_ms(valid_time)
    
    if result.is_valid:
        print(f"✅ 时间验证通过: {valid_time}")
    else:
        print(f"❌ 时间验证失败: {valid_time}")
        all_pass = False
    
    # 测试4: 非单调时间检查（应该失败）
    print("\n--- 测试4: 非单调时间检查 ---")
    ta.reset_monotonic()
    check_monotonic(3000)
    
    try:
        check_monotonic(2000)  # 应该失败
        print("❌ 非单调检查未检测到错误")
        all_pass = False
    except ValueError as e:
        print(f"✅ 正确检测到非单调时间: {e}")
    
    print("\n" + "=" * 60)
    if all_pass:
        print("🎉 所有测试通过！时间权威系统工作正常！")
    else:
        print("⚠️ 部分测试失败！")
    print("=" * 60)
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())