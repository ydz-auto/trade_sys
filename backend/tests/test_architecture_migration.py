"""
测试架构迁移 - 验证新的无状态策略计算器和状态管理
"""
import sys
import os
from pathlib import Path

# 添加项目路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from engines.compute.strategy.calculators import (
    calculate_rsi_signal,
    calculate_macd_signal,
    calculate_trend_following_signal,
    calculate_bb_compression_signal,
)


def test_rsi_calculator():
    """测试 RSI 无状态计算器"""
    print("Testing RSI Calculator...")
    
    # 第一次调用：没有前值，应该只更新状态
    signal, state = calculate_rsi_signal(
        rsi_value=50.0,
        prev_rsi=None,
        oversold_threshold=30.0,
        overbought_threshold=70.0
    )
    assert signal is None
    assert state['prev_rsi'] == 50.0
    print("  ✓ First call: no signal, state updated")
    
    # 第二次调用：RSI 从 50 降到 25，超卖，应该产生买入信号
    signal, state = calculate_rsi_signal(
        rsi_value=25.0,
        prev_rsi=50.0,
        oversold_threshold=30.0,
        overbought_threshold=70.0
    )
    assert signal is not None
    assert signal['signal_type'] == 'buy'
    assert 0 < signal['confidence'] <= 1.0
    assert state['prev_rsi'] == 25.0
    print("  ✓ Buy signal generated correctly")
    
    # 第三次调用：RSI 从 25 升到 80，超买，应该产生卖出信号
    signal, state = calculate_rsi_signal(
        rsi_value=80.0,
        prev_rsi=25.0,
        oversold_threshold=30.0,
        overbought_threshold=70.0
    )
    assert signal is not None
    assert signal['signal_type'] == 'sell'
    print("  ✓ Sell signal generated correctly")
    
    print("✓ RSI Calculator tests passed!\n")


def test_macd_calculator():
    """测试 MACD 无状态计算器"""
    print("Testing MACD Calculator...")
    
    # 第一次调用
    signal, state = calculate_macd_signal(
        macd_value=0.1,
        signal_value=0.2,
        prev_macd=None,
        prev_signal=None
    )
    assert signal is None
    assert state['prev_macd'] == 0.1
    assert state['prev_signal'] == 0.2
    print("  ✓ First call: no signal, state updated")
    
    # MACD 金叉
    signal, state = calculate_macd_signal(
        macd_value=0.3,
        signal_value=0.2,
        prev_macd=0.1,
        prev_signal=0.2
    )
    assert signal is not None
    assert signal['signal_type'] == 'buy'
    print("  ✓ Golden cross buy signal generated")
    
    # MACD 死叉
    signal, state = calculate_macd_signal(
        macd_value=0.1,
        signal_value=0.3,
        prev_macd=0.3,
        prev_signal=0.2
    )
    assert signal is not None
    assert signal['signal_type'] == 'sell'
    print("  ✓ Death cross sell signal generated")
    
    print("✓ MACD Calculator tests passed!\n")


def test_trend_calculator():
    """测试趋势跟踪计算器"""
    print("Testing Trend Following Calculator...")
    
    # 第一次调用
    signal, state = calculate_trend_following_signal(
        ema_fast=100.0,
        ema_slow=95.0,
        prev_ema_fast=None,
        prev_ema_slow=None
    )
    assert signal is None
    assert state['prev_ema_fast'] == 100.0
    assert state['prev_ema_slow'] == 95.0
    print("  ✓ First call: no signal, state updated")
    
    print("✓ Trend Following Calculator tests passed!\n")


def test_bollinger_calculator():
    """测试布林带计算器"""
    print("Testing Bollinger Compression Calculator...")
    
    # 第一次调用
    signal, state = calculate_bb_compression_signal(
        bb_upper=105.0,
        bb_lower=95.0,
        bb_middle=100.0,
        close=99.0,
        prev_above_middle=None
    )
    assert signal is None
    assert 'prev_above_middle' in state
    print("  ✓ First call: no signal, state updated")
    
    print("✓ Bollinger Compression Calculator tests passed!\n")


def test_state_manager():
    """测试状态管理器"""
    print("Testing State Manager...")
    
    from runtime.strategy_runtime.strategy_state import StrategyStateManager
    
    manager = StrategyStateManager()
    
    # 获取或创建状态
    state = manager.get_or_create_state('test_strategy', 'BTCUSDT')
    assert state.strategy_id == 'test_strategy'
    assert state.symbol == 'BTCUSDT'
    assert state.enabled is True
    print("  ✓ State created/retrieved")
    
    # 更新状态
    manager.update_state('test_strategy', 'BTCUSDT', prev_rsi=50.0, enabled=False)
    state = manager.get_state('test_strategy', 'BTCUSDT')
    assert state.prev_rsi == 50.0
    assert state.enabled is False
    print("  ✓ State updated")
    
    # 列出所有状态
    all_states = manager.list_all_states()
    assert len(all_states) >= 1
    print("  ✓ List all states works")
    
    print("✓ State Manager tests passed!\n")


def main():
    """运行所有测试"""
    print("=" * 50)
    print("Architecture Migration Tests")
    print("=" * 50 + "\n")
    
    try:
        test_state_manager()
        test_rsi_calculator()
        test_macd_calculator()
        test_trend_calculator()
        test_bollinger_calculator()
        
        print("=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
