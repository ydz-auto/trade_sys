"""
时间权威系统测试脚本
测试各种时间格式转换和验证功能
"""
import sys
sys.path.insert(0, 'E:\\00_crypto\\00_code\\backend')

from infrastructure.time_authority import (
    get_time_authority,
    normalize_time_ms,
    ensure_time_ms,
    check_monotonic,
    to_datetime,
    format_time_ms,
    validate_time_ms
)

print('=' * 60)
print('时间权威系统测试')
print('=' * 60)

# 测试1: 各种时间格式转换
print('\n--- 测试1: 时间格式转换 ---')
ta = get_time_authority()

test_cases = [
    ('2025-01-01', 'ISO日期字符串'),
    ('2025-01-01 12:00:00', 'ISO日期时间字符串'),
    ('2025-01-01T12:00:00', 'ISO带T字符串'),
    ('2025/01/01', '斜杠日期字符串'),
    (1746272000, '秒时间戳(int)'),
    (1746272000000, '毫秒时间戳(int)'),
    (1746272000.5, '秒时间戳(float)'),
]

all_pass = True
for value, desc in test_cases:
    try:
        result = normalize_time_ms(value, source='test')
        assert isinstance(result, int), f"结果不是int类型: {type(result)}"
        print(f"✓ {desc}: {value} -> {result}")
        print(f"   -> datetime: {to_datetime(result)}")
        print(f"   -> formatted: {format_time_ms(result)}")
    except Exception as e:
        print(f"✗ {desc}: {value} -> ERROR: {e}")
        all_pass = False
    print()

# 测试2: 单调检查
print('\n--- 测试2: 单调递增检查 ---')
ta.reset_monotonic()
timestamps = [1000, 2000, 3000, 2500, 4000]

for ts in timestamps:
    try:
        result = check_monotonic(ts)
        if result:
            print(f"✓ 时间戳 {ts}: 单调递增通过")
        else:
            print(f"✗ 时间戳 {ts}: 非单调递增")
    except ValueError as e:
        print(f"✗ 时间戳 {ts}: ERROR: {e}")

# 测试3: 时间验证
print('\n--- 测试3: 时间验证 ---')
valid_times = [1746272000000, 1000, 2524607999000]  # 有效范围
invalid_times = ['string', 0, -1, 2524608000000, 3000000000000]  # 无效

for time_val in valid_times:
    result = validate_time_ms(time_val)
    status = "✓" if result.is_valid else "✗"
    print(f"{status} 验证 {time_val}: {result.is_valid}")

for time_val in invalid_times:
    try:
        result = validate_time_ms(time_val)
        status = "✓" if result.is_valid else "✗"
        print(f"{status} 验证 {time_val} ({type(time_val).__name__}): {result.is_valid}")
    except Exception as e:
        print(f"✗ 验证 {time_val} ({type(time_val).__name__}): ERROR: {e}")

# 测试4: 会话管理
print('\n--- 测试4: 会话管理 ---')
try:
    ta.start_session(1746272000000)
    print("✓ 会话启动成功")
    
    # 测试单调检查在会话内工作
    check_monotonic(1746272000001)
    check_monotonic(1746272000002)
    print("✓ 会话内单调检查通过")
    
    ta.end_session()
    print("✓ 会话结束成功")
except Exception as e:
    print(f"✗ 会话管理失败: {e}")

print('\n' + '=' * 60)
if all_pass:
    print('所有测试通过!')
else:
    print('部分测试失败!')
print('=' * 60)