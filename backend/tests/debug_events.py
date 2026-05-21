"""
调试事件流 - 检查事件是否正确生成和处理
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def debug_event_flow():
    """调试事件流"""
    from shared.replay.market_event_emitter import MarketEventEmitter, EmitterConfig, EmitMode
    
    data_path = project_root / "data_lake" / "features" / "binance" / "BTCUSDT" / "features.parquet"
    
    emitter = MarketEventEmitter(EmitterConfig(
        emit_mode=EmitMode.INSTANT,
        include_trades=False,
        include_funding=True,
    ))
    
    start_time = int(datetime(2024, 1, 1).timestamp() * 1000)
    end_time = int(datetime(2024, 1, 2).timestamp() * 1000)  # 只测试 1 天
    
    event_count = 0
    event_types = {}
    feature_events = 0
    candle_events = 0
    
    print(f"测试时间范围: 2024-01-01")
    print()
    
    async for event in emitter.emit_from_feature_parquet(
        parquet_path=data_path,
        symbol="BTCUSDT",
        exchange="binance",
        start_time=start_time,
        end_time=end_time,
    ):
        event_count += 1
        event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        if event.event_type == "features":
            feature_events += 1
            if feature_events <= 3:
                features = event.data.get('features', {})
                print(f"Features event #{feature_events}:")
                print(f"  rsi_14: {features.get('rsi_14', 'N/A')}")
                print(f"  macd: {features.get('macd', 'N/A')}")
                print(f"  close: {event.data.get('close', 'N/A')}")
        
        if event.event_type == "candle_1m":
            candle_events += 1
    
    print(f"\n事件统计:")
    print(f"  总事件数: {event_count}")
    print(f"  事件类型: {event_types}")
    print(f"  K线事件: {candle_events}")
    print(f"  特征事件: {feature_events}")


if __name__ == "__main__":
    asyncio.run(debug_event_flow())
