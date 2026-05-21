"""
调试引擎 - 检查引擎的事件处理
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def debug_engine():
    """调试引擎"""
    from application.optimization_service.engine import (
        OptimizationBacktestEngine,
        BacktestConfig,
    )
    
    config = BacktestConfig(
        initial_capital=10000.0,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        stop_loss=0.02,
        take_profit=0.04,
        enable_slippage=True,
        enable_feature_guard=False,
    )
    
    engine = OptimizationBacktestEngine(config)
    await engine.initialize()
    
    # 添加调试
    original_process_event = engine._process_event
    
    event_count = [0]
    feature_event_count = [0]
    signal_count = [0]
    
    async def debug_process_event(event):
        event_count[0] += 1
        
        if event.event_type == "features":
            feature_event_count[0] += 1
            features = event.data.get('features', {})
            rsi = features.get('rsi_14', 50)
            if rsi < 30 or rsi > 70:
                signal_count[0] += 1
        
        await original_process_event(event)
    
    engine._process_event = debug_process_event
    
    start_time = int(datetime(2024, 1, 1).timestamp() * 1000)
    end_time = int(datetime(2024, 1, 31).timestamp() * 1000)
    
    result = await engine.run(
        symbol="BTCUSDT",
        strategy_id="rsi_oversold",
        params={"period": 14, "oversold": 30},
        start_time=start_time,
        end_time=end_time,
    )
    
    print(f"调试信息:")
    print(f"  总事件数: {event_count[0]}")
    print(f"  特征事件数: {feature_event_count[0]}")
    print(f"  信号条件满足次数: {signal_count[0]}")
    
    print(f"\n引擎回测结果:")
    print(f"  总收益: {result.total_return:.2%}")
    print(f"  交易次数: {result.total_trades}")
    print(f"  泄漏统计: {result.leakage_stats}")


if __name__ == "__main__":
    asyncio.run(debug_engine())
