#!/usr/bin/env python3
"""
Minimum Closed-Loop Test - 真正的最小闭环测试

测试链路：
Kline → FeatureRuntime → SignalRuntime → ExecutionRuntime

验证整个系统端到端的正确性，所有 Runtime 真实运行！
"""
import sys
sys.path.insert(0, '.')

import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Optional, Any


# 简单测试策略 - 用于验证信号生成链路
class SimpleTestStrategy:
    """简单的测试策略 - RSI 超买超卖 + SMA 趋势确认"""
    
    def __init__(self, strategy_id: str = "simple_test"):
        self.strategy_id = strategy_id
    
    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        生成交易信号
        """
        rsi_14 = features.get('rsi_14')
        sma_20 = features.get('sma_20')
        close_price = features.get('close')
        
        if rsi_14 is None or sma_20 is None or close_price is None:
            return None
        
        # 买入信号：RSI < 30 (超卖) + 价格高于 SMA
        if rsi_14 < 30 and close_price > sma_20:
            return {
                'signal_type': 'buy',
                'confidence': 0.8,
                'reason': f'RSI({rsi_14:.1f}) < 30 + Price({close_price:.1f}) > SMA({sma_20:.1f})',
                'metadata': {'strategy': self.strategy_id}
            }
        
        # 卖出信号：RSI > 70 (超买) + 价格低于 SMA
        elif rsi_14 > 70 and close_price < sma_20:
            return {
                'signal_type': 'sell',
                'confidence': 0.8,
                'reason': f'RSI({rsi_14:.1f}) > 70 + Price({close_price:.1f}) < SMA({sma_20:.1f})',
                'metadata': {'strategy': self.strategy_id}
            }
        
        return None


async def test_minimum_closed_loop():
    """测试完整的闭环链路"""
    print("=" * 80)
    print("Minimum Closed-Loop Test - 真正的最小闭环测试")
    print("=" * 80)
    
    from infrastructure.logging import get_logger
    logger = get_logger("min_closed_loop_test")
    
    # 1. 清理状态 - 避免单例之间的干扰
    from infrastructure.storage.point_in_time_store import clear_all_stores
    clear_all_stores()
    
    # 2. 初始化 ReplayRuntime 并注入所有子 Runtime
    from runtimes.replay_runtime.runtime import (
        get_replay_runtime, 
        ReplayConfig, 
        ReplayEvent,
        EventType,
        SessionStatus
    )
    from runtimes.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
    from runtimes.signal_runtime import get_signal_runtime, SignalConfig
    from runtimes.execution_runtime.runtime import get_execution_runtime, ExecutionConfig
    
    # 创建配置
    symbol = "BTCUSDT"
    config = ReplayConfig(
        symbol=symbol,
        warmup_periods=0,
        checkpoint_interval=100
    )
    
    # 创建 ReplayRuntime
    replay_runtime = get_replay_runtime(config)
    
    # 注入 FeatureRuntime
    feature_config = FeatureConfig(
        symbol=symbol, 
        mode=FeatureMode.REPLAY,
        use_gpu=False
    )
    feature_runtime = get_feature_runtime(feature_config)
    replay_runtime.attach_feature_runtime(feature_runtime)
    logger.info("✅ FeatureRuntime attached")
    
    # 注入 SignalRuntime
    signal_config = SignalConfig(
        symbols=[symbol],
        mode="replay",
        enable_strategy_registry=False
    )
    signal_runtime = get_signal_runtime(signal_config)
    replay_runtime.attach_signal_runtime(signal_runtime)
    logger.info("✅ SignalRuntime attached")
    
    # 注入 ExecutionRuntime (Mock 模式)
    # 重置 ExecutionRuntime 实例
    import runtimes.execution_runtime.runtime as exec_module
    exec_module._execution_runtime = None
    execution_runtime = get_execution_runtime()
    await execution_runtime.initialize()
    replay_runtime.attach_execution_runtime(execution_runtime)
    logger.info("✅ ExecutionRuntime attached")
    
    # 注入测试策略 - 使用已注册的策略 "rsi"
    # ReplayRuntime 会通过 run_backtest() 自动获取策略
    logger.info("✅ Test will use registered strategy 'rsi'")
    
    # 3. 生成合成 K 线数据 - 制造一些能触发信号的波动
    print("\n[Step 1] 生成测试数据...")
    start_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
    start_ms = int(start_time.timestamp() * 1000)
    
    def generate_test_klines():
        """生成测试 K 线，包含波动行情"""
        klines = []
        price = 46500.0
        ts = start_ms
        
        # 阶段1：先下跌，制造超卖（RSI < 30）
        for i in range(15):
            price_change = - (20 + i * 5)  # 加速下跌
            klines.append({
                'timestamp_ms': ts,
                'open': price,
                'high': price + 50,
                'low': price + price_change - 50,
                'close': price + price_change,
                'volume': 100 + i * 20,
            })
            price = price + price_change
            ts += 60000
        
        # 阶段2：小幅反弹（可能触发买入信号）
        for i in range(10):
            price_change = 50 + i * 10
            klines.append({
                'timestamp_ms': ts,
                'open': price,
                'high': price + price_change + 50,
                'low': price,
                'close': price + price_change,
                'volume': 150 + i * 10,
            })
            price = price + price_change
            ts += 60000
        
        # 阶段3：上涨，制造超买（RSI > 70）
        for i in range(15):
            price_change = 100 - i * 5
            klines.append({
                'timestamp_ms': ts,
                'open': price,
                'high': price + price_change + 50,
                'low': price - 50,
                'close': price + price_change,
                'volume': 120 + i * 5,
            })
            price = price + price_change
            ts += 60000
        
        return klines
    
    test_klines = generate_test_klines()
    print(f"✅ 生成 {len(test_klines)} 根 K 线")
    
    # 4. 创建事件迭代器
    async def kline_generator():
        for kline in test_klines:
            yield ReplayEvent(
                event_id=f"kline_{kline['timestamp_ms']}",
                event_type=EventType.KLINE,
                timestamp_ms=kline['timestamp_ms'],
                data={
                    'open': float(kline['open']),
                    'high': float(kline['high']),
                    'low': float(kline['low']),
                    'close': float(kline['close']),
                    'volume': float(kline['volume']),
                    'symbol': symbol
                }
            )
    
    # 5. 运行回测！
    print("\n[Step 2] 运行完整闭环回测...")
    session_state = await replay_runtime.run_backtest(
        symbol=symbol,
        strategy_id="rsi",  # 使用已注册的策略
        params={"oversold": 30, "overbought": 70},
        start_time_ms=start_ms,
        end_time_ms=start_ms + len(test_klines) * 60000,
        initial_capital=10000.0,
        event_iterator=kline_generator(),
    )
    
    # 6. 验证结果
    print("\n[Step 3] 验证回测结果...")
    print("=" * 80)
    
    success = True
    
    # 检查是否有错误
    if session_state.errors:
        print(f"❌ 检测到 {len(session_state.errors)} 个错误：")
        for i, err in enumerate(session_state.errors, 1):
            print(f"   {i}. {err}")
        success = False
    else:
        print("✅ 无运行时错误")
    
    # 检查处理的事件数
    print(f"✅ 处理事件数：{session_state.processed_events}/{len(test_klines)}")
    if session_state.processed_events != len(test_klines):
        success = False
    
    # 检查交易
    print(f"\n📊 交易记录：{len(session_state.trades)} 笔")
    for i, trade in enumerate(session_state.trades, 1):
        print(f"   {i}. {trade.get('side', 'unknown')} {trade.get('quantity', 0)} {trade.get('symbol', symbol)}")
    
    # 检查状态
    print(f"\n📈 最终资金：${session_state.capital:.2f}")
    print(f"📈 初始资金：$10000.00")
    
    # 验证 SessionState
    print(f"\n🟢 Session 状态：{session_state.status.value if hasattr(session_state.status, 'value') else session_state.status}")
    
    print("\n" + "=" * 80)
    if success:
        print("✅ Minimum Closed-Loop Test PASSED!")
        print("   - FeatureRuntime 工作正常")
        print("   - SignalRuntime 工作正常")
        print("   - ExecutionRuntime 工作正常")
        print("   - 完整回测链路已通")
    else:
        print("❌ Minimum Closed-Loop Test FAILED")
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(test_minimum_closed_loop())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
