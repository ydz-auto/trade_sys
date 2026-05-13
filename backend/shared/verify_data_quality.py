"""
Data Quality Verification Script
验证数据质量检测功能
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.data_quality import (
    DataQualityChecker,
    CandleDataQualityChecker,
    QualityStatus,
    IssueType,
    get_data_quality_checker,
    get_candle_quality_checker,
)


def verify_data_quality():
    """验证数据质量检查器"""
    print("=" * 60)
    print("Data Quality Verification")
    print("=" * 60)
    
    checker = get_data_quality_checker()
    
    test_records = [
        {"id": "1", "name": "Alice", "age": 25, "email": "alice@example.com"},
        {"id": "2", "name": "Bob", "age": 30, "email": "bob@example.com"},
        {"id": "3", "name": "Charlie", "age": None, "email": "charlie@example.com"},
        {"id": "4", "name": "", "age": 35, "email": "david@example.com"},
        {"id": "5", "name": "Eve", "age": 28, "email": "eve@example.com"},
    ]
    
    print("\n[1] Testing completeness check...")
    completeness, null_count, issues = checker.calculate_completeness(
        test_records,
        ["name", "age", "email"]
    )
    print(f"    Completeness: {completeness:.2%}")
    print(f"    Null count: {null_count}")
    print(f"    Issues found: {len(issues)}")
    
    print("\n[2] Testing outlier detection...")
    values = [10, 12, 14, 15, 13, 11, 100]
    outliers = checker.detect_outliers(values, method="iqr")
    print(f"    Values: {values}")
    print(f"    Outlier indices: {outliers}")
    print(f"    Outlier values: {[values[i] for i in outliers]}")
    
    print("\n[3] Testing duplicate detection...")
    records_with_dup = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "3", "name": "Alice"},
    ]
    dup_count, dup_issues = checker.detect_duplicates(records_with_dup, ["name"])
    print(f"    Duplicate count: {dup_count}")
    print(f"    Issues: {[i.message for i in dup_issues]}")
    
    print("\n[4] Testing quality assessment...")
    validation_func = lambda r: (r.get("age", 0) or 0) > 0 and (r.get("age", 0) or 0) < 150
    
    quality = checker.assess_quality(
        records=test_records,
        required_fields=["name", "age", "email"],
        validation_func=validation_func,
        key_fields=["name"],
    )
    
    print(f"    Total records: {quality.total_records}")
    print(f"    Valid records: {quality.valid_records}")
    print(f"    Status: {quality.status.value}")
    print(f"    Completeness: {quality.completeness:.2%}")
    print(f"    Accuracy: {quality.accuracy:.2%}")
    print(f"    Consistency: {quality.consistency:.2%}")
    print(f"    Issues: {len(quality.issues)}")
    
    print("\n[5] Testing field profiling...")
    profile = checker.profile_field([10, 20, 30, 40, 50, None, 60])
    print(f"    Count: {profile.count}")
    print(f"    Null count: {profile.null_count}")
    print(f"    Unique count: {profile.unique_count}")
    print(f"    Min: {profile.min_value}")
    print(f"    Max: {profile.max_value}")
    print(f"    Mean: {profile.mean_value}")
    print(f"    Median: {profile.median_value}")
    
    print("\n" + "=" * 60)
    print("✅ Data Quality Verification Complete!")
    print("=" * 60)
    
    return True


def verify_candle_quality():
    """验证K线数据质量检查器"""
    print("\n[K线 Data Quality Verification]")
    
    checker = get_candle_quality_checker()
    
    test_candles = [
        {"open_time": 1700000000, "close_time": 1700000060, "open": 50000, "high": 50100, "low": 49900, "close": 50050, "volume": 100},
        {"open_time": 1700000060, "close_time": 1700000120, "open": 50050, "high": 50200, "low": 50000, "close": 50100, "volume": 150},
        {"open_time": 1700000120, "close_time": 1700000180, "open": 50100, "high": 50000, "low": 49900, "close": 49950, "volume": 200},
        {"open_time": 1700000180, "close_time": 1700000240, "open": 49950, "high": 50050, "low": 49900, "close": 50000, "volume": 0},
        {"open_time": 1700000240, "close_time": 1700000300, "open": 50000, "high": 50200, "low": 49900, "close": 50150, "volume": 180},
    ]
    
    print("\n  Testing candle consistency checks...")
    
    for i, candle in enumerate(test_candles):
        price_ok = checker.check_price_consistency(candle)
        volume_ok = checker.check_volume_positive(candle)
        time_ok = checker.check_time_consistency(candle)
        print(f"    Candle {i+1}: price={price_ok}, volume={volume_ok}, time={time_ok}")
    
    print("\n  Testing candle quality assessment...")
    quality = checker.check_candles(test_candles)
    
    print(f"    Status: {quality.status.value}")
    print(f"    Completeness: {quality.completeness:.2%}")
    print(f"    Issues: {len(quality.issues)}")
    
    for issue in quality.issues:
        print(f"      - [{issue.issue_type.value}] {issue.field}: {issue.message}")
    
    print("  ✅ K线 Data Quality verified!")
    return True


def main():
    """主函数"""
    try:
        verify_data_quality()
        verify_candle_quality()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
