#!/usr/bin/env python3
"""
Simple Warmup Test - 简单验证指标预热
"""
import sys
sys.path.insert(0, '.')

import asyncio


async def test_simple_warmup():
    """简单测试指标预热"""
    print("=" * 80)
    print("Simple Warmup Test")
    print("=" * 80)
    
    from runtimes.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
    
    # 初始化
    feature_config = FeatureConfig(symbol="BTCUSDT", mode=FeatureMode.REPLAY)
    feature_runtime = get_feature_runtime(feature_config)
    
    # 发送 K 线事件
    ts = 1640995200000
    
    for i in range(15):
        event = {
            'event_type': 'KLINE',
            'timestamp_ms': ts,
            'data': {
                'open': 46500 + i * 10,
                'high': 46520 + i * 10,
                'low': 46480 + i * 10,
                'close': 46500 + i * 10,
                'volume': 100,
                'symbol': 'BTCUSDT'
            }
        }
        await feature_runtime.update(event)
        
        features = feature_runtime.get_features_at(ts)
        rsi_14 = features.get('rsi_14')
        
        print(f'K线{i+1}: rsi_14={rsi_14}')
        
        ts += 60000
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_simple_warmup())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)