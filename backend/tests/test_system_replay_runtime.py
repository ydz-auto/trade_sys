#!/usr/bin/env python3
"""
测试系统内真实的 ReplayRuntime 回测能力
"""
import sys
sys.path.insert(0, '.')

import asyncio
from datetime import datetime
from pathlib import Path
from infrastructure.logging import get_logger

logger = get_logger("test_system_replay")


async def test_replay_backtest():
    """测试系统内真实的回测功能"""
    print("=" * 80)
    print("测试系统真实回测能力")
    print("=" * 80)
    
    # 1. 初始化 ReplayRuntime
    from runtimes.replay_runtime.runtime import get_replay_runtime, ReplayConfig
    runtime = get_replay_runtime(ReplayConfig(warmup_periods=0))
    
    # 2. 连接其他 Runtime
    from runtimes.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
    from runtimes.signal_runtime import get_signal_runtime
    from runtimes.execution_runtime import get_execution_runtime
    
    feature_config = FeatureConfig(symbol="BTCUSDT", mode=FeatureMode.REPLAY)
    runtime.attach_feature_runtime(get_feature_runtime(feature_config))
    runtime.attach_signal_runtime(get_signal_runtime())
    runtime.attach_execution_runtime(get_execution_runtime())
    
    # 3. 确定时间范围 - 2022年1月1日 1天 (使用 UTC 时区避免 8 小时偏移)
    from datetime import timezone, timedelta
    start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=24)
    
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    
    logger.info(f"时间范围: {start_time} ~ {end_time}")
    
    # 4. 生成合成 Kline 数据（不依赖外部文件）
    synthetic_klines = _generate_synthetic_klines(start_ms, end_ms)
    
    # 5. 创建异步事件迭代器
    from runtimes.replay_runtime.runtime import EventType, ReplayEvent
    
    async def kline_generator():
        for kline in synthetic_klines:
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
    
    # 6. 运行回测
    session_state = await runtime.run_backtest(
        symbol="BTCUSDT",
        strategy_id="rsi",
        params={"rsi_period": 14, "oversold": 30, "overbought": 70},
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        initial_capital=10000.0,
        event_iterator=kline_generator(),
    )
    
    # 7. 输出结果
    print("\n" + "=" * 80)
    print("回测结果")
    print("=" * 80)
    print(f"初始资金: ${session_state.capital:,.2f}")
    print(f"总交易次数: {len(session_state.trades)}")
    print(f"处理事件数: {session_state.processed_events}/{session_state.total_events}")
    print(f"最终权益: ${session_state.equity_curve[-1] if session_state.equity_curve else session_state.capital:,.2f}")
    
    if session_state.trades:
        print(f"\n前5笔交易:")
        for t in session_state.trades[:5]:
            print(f"  {t.get('timestamp', 'N/A')} {t.get('side', 'N/A')} qty={t.get('quantity', 0)} pnl=${t.get('pnl', 0):.2f}")
    else:
        print(f"\n无交易记录（策略未产生信号）")
    
    print("\n" + "=" * 80)
    if session_state.processed_events > 0:
        print("✅ 系统回测运行成功！")
    else:
        print("⚠️  系统回测未能处理事件，需排查")
    print("=" * 80)


def _generate_synthetic_klines(start_ms: int, end_ms: int, interval_ms: int = 60000):
    """生成合成 K 线数据用于测试"""
    import random
    klines = []
    price = 46500.0
    
    ts = start_ms
    i = 0
    while ts <= end_ms:
        change = random.uniform(-0.003, 0.004)
        open_p = price
        close_p = price * (1 + change)
        high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.001))
        low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.001))
        volume = random.uniform(50, 200)
        
        klines.append({
            'timestamp_ms': ts,
            'open': open_p,
            'high': high_p,
            'low': low_p,
            'close': close_p,
            'volume': volume,
        })
        
        price = close_p
        ts += interval_ms
        i += 1
    
    return klines


if __name__ == "__main__":
    try:
        asyncio.run(test_replay_backtest())
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        traceback.print_exc()
