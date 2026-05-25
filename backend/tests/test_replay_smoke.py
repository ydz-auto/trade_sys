#!/usr/bin/env python3
"""
Replay Smoke Test - 验证回测链路能跑通
"""
import sys
sys.path.insert(0, '.')

import asyncio
from datetime import datetime, timezone, timedelta


async def test_replay_smoke():
    """测试回测基本功能是否正常"""
    print("=" * 80)
    print("Replay Smoke Test - 回测冒烟测试")
    print("=" * 80)
    
    from runtimes.replay_runtime.runtime import get_replay_runtime, ReplayConfig, EventType, ReplayEvent
    from runtimes.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
    from runtimes.signal_runtime import get_signal_runtime
    from runtimes.execution_runtime import get_execution_runtime
    
    # 初始化
    runtime = get_replay_runtime(ReplayConfig(warmup_periods=0))
    
    feature_config = FeatureConfig(symbol="BTCUSDT", mode=FeatureMode.REPLAY)
    runtime.attach_feature_runtime(get_feature_runtime(feature_config))
    runtime.attach_signal_runtime(get_signal_runtime())
    runtime.attach_execution_runtime(get_execution_runtime())
    
    # 时间范围 - 30分钟
    start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(minutes=30)
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    
    # 生成合成 K 线
    import random
    klines = []
    price = 46500.0
    ts = start_ms
    while ts <= end_ms:
        change = random.uniform(-0.002, 0.003)
        klines.append({
            'timestamp_ms': ts,
            'open': price,
            'high': price * (1 + abs(change) + 0.001),
            'low': price * (1 - abs(change) - 0.001),
            'close': price * (1 + change),
            'volume': random.uniform(50, 200),
        })
        price = klines[-1]['close']
        ts += 60000
    
    # 创建事件迭代器
    async def kline_generator():
        for kline in klines:
            yield ReplayEvent(
                event_id=f"kline_{kline['timestamp_ms']}",
                event_type=EventType.KLINE,
                timestamp_ms=int(kline['timestamp_ms']),
                data={
                    'open': float(kline['open']),
                    'high': float(kline['high']),
                    'low': float(kline['low']),
                    'close': float(kline['close']),
                    'volume': float(kline['volume']),
                    'symbol': 'BTCUSDT'
                }
            )
    
    # 运行回测
    session_state = await runtime.run_backtest(
        symbol="BTCUSDT",
        strategy_id="rsi",
        params={"oversold": 30, "overbought": 70},
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        initial_capital=10000.0,
        event_iterator=kline_generator(),
    )
    
    # 验证结果
    print(f"\n测试结果:")
    print(f"  处理事件数: {session_state.processed_events}")
    print(f"  交易次数: {len(session_state.trades)}")
    print(f"  初始资金: ${session_state.capital:,.2f}")
    
    success = session_state.processed_events > 0
    if success:
        print("\n✅ Replay Smoke Test PASSED")
        print("   - 事件处理正常")
        print("   - 回测链路完整")
    else:
        print("\n❌ Replay Smoke Test FAILED")
        
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(test_replay_smoke())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)