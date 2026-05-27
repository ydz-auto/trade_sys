#!/usr/bin/env python3
"""
Indicator Warmup Test - 验证指标在数据不足时返回 None
"""
import sys
sys.path.insert(0, '.')

import asyncio
from datetime import datetime, timezone, timedelta


async def test_indicator_warmup():
    """测试指标预热行为"""
    print("=" * 80)
    print("Indicator Warmup Test - 指标预热测试")
    print("=" * 80)
    
    # 先清空所有单例状态
    from infrastructure.storage.point_in_time_store import clear_all_stores
    clear_all_stores()
    
    # 强制重置FeatureRuntime的_instance（hack for test
    from runtime.feature_runtime import FeatureRuntime
    FeatureRuntime._instance = None
    
    from engines.compute.feature.unified_calculator import _calculator_instance
    globals()['_calculator_instance'] = None
    
    from runtime.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
    
    # 初始化 - 直接使用 FeatureRuntime，不通过 ReplayRuntime
    feature_config = FeatureConfig(symbol="BTCUSDT", mode=FeatureMode.REPLAY, use_gpu=False)
    feature_runtime = get_feature_runtime(feature_config)
    
    # 时间范围 - 25根K线
    start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
    ts = int(start_time.timestamp() * 1000)
    
    # 生成固定的合成 K 线（已知价格序列）
    prices = [46500.0 + i * 10 for i in range(25)]
    
    # 测试结果
    test_results = []
    
    # 逐条处理K线
    for i, price in enumerate(prices):
        event = {
            'event_type': 'KLINE',
            'timestamp_ms': ts,
            'data': {
                'open': price,
                'high': price + 20,
                'low': price - 20,
                'close': price,
                'volume': 100,
                'symbol': 'BTCUSDT'
            }
        }
        
        await feature_runtime.update(event)
        
        # 检查特征状态
        features = feature_runtime.get_features_at(ts)
        rsi_14 = features.get('rsi_14')
        sma_20 = features.get('sma_20')
        
        test_results.append({
            'kline_num': i + 1,
            'rsi_14': rsi_14,
            'sma_20': sma_20,
            'rsi_14_is_none': rsi_14 is None,
            'sma_20_is_none': sma_20 is None,
        })
        
        ts += 60000
    
    # 验证结果
    print("\n" + "=" * 80)
    print("验证指标预热行为：")
    print("=" * 80)
    
    all_passed = True
    
    # 1. 第10根K线时，RSI_14和SMA_20都应该是None
    print("\n[测试1] 第10根K线时：")
    result_10 = test_results[9]
    print(f"  RSI_14 = {result_10['rsi_14']} (预期: None)")
    print(f"  SMA_20 = {result_10['sma_20']} (预期: None)")
    
    if result_10['rsi_14_is_none'] and result_10['sma_20_is_none']:
        print("  ✅ 通过")
    else:
        print("  ❌ 失败")
        all_passed = False
    
    # 2. 第15根K线时，RSI_14应该有值，SMA_20应该是None
    print("\n[测试2] 第15根K线时：")
    result_15 = test_results[14]
    print(f"  RSI_14 = {result_15['rsi_14']} (预期: 有值)")
    print(f"  SMA_20 = {result_15['sma_20']} (预期: None)")
    
    if not result_15['rsi_14_is_none'] and result_15['sma_20_is_none']:
        print("  ✅ 通过")
    else:
        print("  ❌ 失败")
        all_passed = False
    
    # 3. 第20根K线时，RSI_14和SMA_20都应该有值
    print("\n[测试3] 第20根K线时：")
    result_20 = test_results[19]
    print(f"  RSI_14 = {result_20['rsi_14']} (预期: 有值)")
    print(f"  SMA_20 = {result_20['sma_20']} (预期: 有值)")
    
    if not result_20['rsi_14_is_none'] and not result_20['sma_20_is_none']:
        print("  ✅ 通过")
    else:
        print("  ❌ 失败")
        all_passed = False
    
    # 总结
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ Indicator Warmup Test PASSED")
        print("   - RSI_14 在数据不足时正确返回 None")
        print("   - SMA_20 在数据不足时正确返回 None")
        print("   - 指标在足够数据后正确计算")
    else:
        print("❌ Indicator Warmup Test FAILED")
    
    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(test_indicator_warmup())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)