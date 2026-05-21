"""
完整调试 - 检查信号生成和交易逻辑
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def full_debug():
    """完整调试"""
    from shared.replay.market_event_emitter import MarketEventEmitter, EmitterConfig, EmitMode
    
    data_path = project_root / "data_lake" / "features" / "binance" / "BTCUSDT" / "features.parquet"
    
    emitter = MarketEventEmitter(EmitterConfig(
        emit_mode=EmitMode.INSTANT,
        include_trades=False,
        include_funding=True,
    ))
    
    start_time = int(datetime(2024, 1, 1).timestamp() * 1000)
    end_time = int(datetime(2024, 1, 31).timestamp() * 1000)  # 测试 1 个月
    
    # 模拟回测
    capital = 10000.0
    position = None
    trades = []
    current_price = 0.0
    signals_generated = 0
    
    # 信号处理器
    def signal_handler(features, price):
        rsi = features.get('rsi_14', 50)
        if rsi < 30:
            return 1
        elif rsi > 70:
            return -1
        return 0
    
    async for event in emitter.emit_from_feature_parquet(
        parquet_path=data_path,
        symbol="BTCUSDT",
        exchange="binance",
        start_time=start_time,
        end_time=end_time,
    ):
        if event.event_type == "candle_1m":
            current_price = event.data.get('close', 0)
            
            # 检查平仓
            if position:
                entry_price = position['entry_price']
                pnl_pct = (current_price - entry_price) / entry_price
                
                if pnl_pct <= -0.02:
                    capital += position['quantity'] * entry_price * (1 + pnl_pct)
                    trades.append({'pnl_pct': pnl_pct, 'reason': 'stop_loss'})
                    position = None
                elif pnl_pct >= 0.04:
                    capital += position['quantity'] * entry_price * (1 + pnl_pct)
                    trades.append({'pnl_pct': pnl_pct, 'reason': 'take_profit'})
                    position = None
        
        elif event.event_type == "features":
            features = event.data.get('features', {})
            signal = signal_handler(features, current_price)
            
            if signal != 0:
                signals_generated += 1
            
            if signal != 0 and position is None and current_price > 0:
                position_size = capital * 0.3
                position = {
                    'entry_price': current_price,
                    'quantity': position_size / current_price,
                }
                capital -= position_size
    
    # 最后平仓
    if position:
        pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        capital += position['quantity'] * position['entry_price'] * (1 + pnl_pct)
        trades.append({'pnl_pct': pnl_pct, 'reason': 'end'})
    
    print(f"回测结果 (2024-01):")
    print(f"  初始资金: 10000.0")
    print(f"  最终资金: {capital:.2f}")
    print(f"  总收益: {(capital - 10000) / 10000:.2%}")
    print(f"  信号生成次数: {signals_generated}")
    print(f"  交易次数: {len(trades)}")
    
    if trades:
        wins = [t for t in trades if t['pnl_pct'] > 0]
        print(f"  盈利交易: {len(wins)}")
        print(f"  胜率: {len(wins) / len(trades):.2%}")


if __name__ == "__main__":
    asyncio.run(full_debug())
