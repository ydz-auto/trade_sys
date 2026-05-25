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
    from runtimes.replay_runtime.runtime import get_replay_runtime
    runtime = get_replay_runtime()
    
    # 2. 连接其他 Runtime
    from runtimes.feature_runtime.feature_matrix_runtime import get_feature_matrix_runtime
    from runtimes.signal_runtime import get_signal_runtime
    from runtimes.execution_runtime import get_execution_runtime
    
    runtime.attach_feature_runtime(get_feature_matrix_runtime(symbol="BTCUSDT"))
    runtime.attach_signal_runtime(get_signal_runtime())
    runtime.attach_execution_runtime(get_execution_runtime())
    
    # 3. 确定时间范围 - 2022年1月
    start_time = datetime(2022, 1, 1)
    end_time = datetime(2022, 1, 31)
    
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    
    logger.info(f"时间范围: {start_time} ~ {end_time}")
    
    # 4. 运行回测（使用系统真实策略）
    session_state = await runtime.run_backtest(
        symbol="BTCUSDT",
        strategy_id="rsi",
        params={"rsi_period": 14, "oversold": 30, "overbought": 70},
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        initial_capital=10000.0,
        data_path=str(Path("/Volumes/00_crypto/00_code/backend/data_lake"))
    )
    
    # 5. 输出结果
    print("\n" + "=" * 80)
    print("回测结果")
    print("=" * 80)
    print(f"初始资金: ${session_state.initial_capital:,.2f}")
    print(f"最终资金: ${session_state.current_capital:,.2f}")
    print(f"总收益: {(session_state.current_capital - session_state.initial_capital) / session_state.initial_capital * 100:.2f}%")
    print(f"总交易次数: {len(session_state.trades)}")
    print(f"盈亏交易数: {sum(1 for t in session_state.trades if t.profit > 0)} 胜 / {sum(1 for t in session_state.trades if t.profit < 0)} 负")
    
    if session_state.trades:
        print("\n前10笔交易:")
        for t in session_state.trades[:10]:
            print(f"  {t.entry_time} {t.direction} -> {t.exit_time} | 利润: ${t.profit:,.2f}")


if __name__ == "__main__":
    try:
        asyncio.run(test_replay_backtest())
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        traceback.print_exc()
