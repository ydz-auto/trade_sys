"""
调试回测 - 检查信号生成和交易逻辑
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def debug_backtest():
    """调试回测"""
    from application.optimization_service.engine import (
        OptimizationBacktestEngine,
        BacktestConfig,
    )
    
    # 加载数据
    data_path = project_root / "data_lake" / "features" / "binance" / "BTCUSDT" / "features.parquet"
    df = pd.read_parquet(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 筛选 2024 年数据
    df_2024 = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] <= '2024-12-31')].copy()
    
    print(f"数据范围: {df_2024['timestamp'].min()} - {df_2024['timestamp'].max()}")
    print(f"数据量: {len(df_2024)}")
    
    # 检查 RSI 分布
    print(f"\nRSI_14 分布:")
    print(f"  Min: {df_2024['rsi_14'].min():.2f}")
    print(f"  Max: {df_2024['rsi_14'].max():.2f}")
    print(f"  Mean: {df_2024['rsi_14'].mean():.2f}")
    
    # 统计 RSI < 30 的次数
    rsi_oversold = df_2024[df_2024['rsi_14'] < 30]
    print(f"\nRSI < 30 (超卖) 次数: {len(rsi_oversold)}")
    
    rsi_overbought = df_2024[df_2024['rsi_14'] > 70]
    print(f"RSI > 70 (超买) 次数: {len(rsi_overbought)}")
    
    # 模拟信号生成
    signals = []
    for idx, row in df_2024.iterrows():
        rsi = row['rsi_14']
        if rsi < 30:
            signals.append(1)  # 买入
        elif rsi > 70:
            signals.append(-1)  # 卖出
        else:
            signals.append(0)
    
    print(f"\n信号统计:")
    print(f"  买入信号: {signals.count(1)}")
    print(f"  卖出信号: {signals.count(-1)}")
    print(f"  无信号: {signals.count(0)}")
    
    # 简单回测
    print("\n" + "="*60)
    print("简单回测模拟")
    print("="*60)
    
    capital = 10000.0
    position = None
    trades = []
    
    for i, (idx, row) in enumerate(df_2024.iterrows()):
        close = row['close']
        rsi = row['rsi_14']
        
        # 检查平仓
        if position:
            entry_price = position['entry_price']
            pnl_pct = (close - entry_price) / entry_price
            
            # 止损
            if pnl_pct <= -0.02:
                capital += position['quantity'] * entry_price * (1 + pnl_pct)
                trades.append({
                    'entry': entry_price,
                    'exit': close,
                    'pnl_pct': pnl_pct,
                    'reason': 'stop_loss'
                })
                position = None
            
            # 止盈
            elif pnl_pct >= 0.04:
                capital += position['quantity'] * entry_price * (1 + pnl_pct)
                trades.append({
                    'entry': entry_price,
                    'exit': close,
                    'pnl_pct': pnl_pct,
                    'reason': 'take_profit'
                })
                position = None
        
        # 开仓
        if position is None and rsi < 30:
            position_size = capital * 0.3
            position = {
                'entry_price': close,
                'quantity': position_size / close,
            }
            capital -= position_size
    
    # 最后平仓
    if position:
        final_price = df_2024.iloc[-1]['close']
        pnl_pct = (final_price - position['entry_price']) / position['entry_price']
        capital += position['quantity'] * position['entry_price'] * (1 + pnl_pct)
        trades.append({
            'entry': position['entry_price'],
            'exit': final_price,
            'pnl_pct': pnl_pct,
            'reason': 'end'
        })
    
    print(f"\n回测结果:")
    print(f"  初始资金: 10000.0")
    print(f"  最终资金: {capital:.2f}")
    print(f"  总收益: {(capital - 10000) / 10000:.2%}")
    print(f"  交易次数: {len(trades)}")
    
    if trades:
        wins = [t for t in trades if t['pnl_pct'] > 0]
        losses = [t for t in trades if t['pnl_pct'] <= 0]
        print(f"  盈利交易: {len(wins)}")
        print(f"  亏损交易: {len(losses)}")
        print(f"  胜率: {len(wins) / len(trades):.2%}")
    
    # 运行引擎回测
    print("\n" + "="*60)
    print("引擎回测")
    print("="*60)
    
    config = BacktestConfig(
        initial_capital=10000.0,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        stop_loss=0.02,
        take_profit=0.04,
        enable_slippage=True,
        enable_feature_guard=False,  # 禁用守卫来调试
    )
    
    engine = OptimizationBacktestEngine(config)
    await engine.initialize()
    
    start_time = int(datetime(2024, 1, 1).timestamp() * 1000)
    end_time = int(datetime(2024, 12, 31, 23, 59, 59).timestamp() * 1000)
    
    result = await engine.run(
        symbol="BTCUSDT",
        strategy_id="rsi_oversold",
        params={"period": 14, "oversold": 30},
        start_time=start_time,
        end_time=end_time,
    )
    
    print(f"\n引擎回测结果:")
    print(f"  总收益: {result.total_return:.2%}")
    print(f"  Sharpe: {result.sharpe_ratio:.2f}")
    print(f"  胜率: {result.win_rate:.2%}")
    print(f"  交易次数: {result.total_trades}")
    print(f"  泄漏统计: {result.leakage_stats}")


if __name__ == "__main__":
    asyncio.run(debug_backtest())
