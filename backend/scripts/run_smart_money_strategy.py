"""
智能策略回测 - 基于数据特征的策略组合
包含：
1. Smart Money Detection（聪明钱检测）
2. Trend Exhaustion Reversal（趋势衰竭反转）
3. 等等
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

# 项目路径
project_root = Path(__file__).parent.parent


def load_data():
    """加载数据"""
    print("📊 加载数据...")
    features_path = project_root / "data_lake" / "features" / "binance" / "BTCUSDT" / "features_with_structure.parquet"
    
    df = pd.read_parquet(features_path)
    print(f"✅ 数据加载完成: {len(df)} 条")
    return df


def smart_money_signal(df, i):
    """
    Smart Money Detection - 聪明钱检测策略
    逻辑：高资金费率 + 持仓增加 + 缩量 + 高波动 = 聪明钱在建仓
    """
    score = 0
    
    # 1. 高资金费率 - 空头被套
    if df['funding_rate'].iloc[i] > 0.0001:
        score += 2
    
    # 2. 持仓增加 - 资金流入
    if df['oi_delta'].iloc[i] > 0.01:
        score += 2
    
    # 3. 缩量 - 悄悄建仓
    if df['volume_ratio'].iloc[i] < 1.2:
        score += 1
    
    # 4. 高波动环境
    if df['regime_code'].iloc[i] == 1:  # volatile
        score += 1
    
    return score >= 4  # 做多信号


def trend_exhaustion_signal(df, i):
    """
    Trend Exhaustion Reversal - 趋势衰竭反转
    """
    if i < 10:
        return False
    
    if (
        df['trend_exhaustion'].iloc[i] == 1 and 
        df['momentum_shift'].iloc[i] == 1
    ):
        if df['trend_direction_12h'].iloc[i] > 0:
            return 'short'  # 上涨衰竭，做空
        else:
            return 'long'   # 下跌衰竭，做多
    
    return False


def regime_transition_signal(df, i):
    """
    Regime Transition - 市场状态转换
    """
    if i < 60:  # 需要前1小时数据
        return False
    
    prev_regime = df['regime_code'].iloc[i-12]
    curr_regime = df['regime_code'].iloc[i]
    
    # 从震荡转高波动
    if prev_regime == 0 and curr_regime == 1:
        if df['return_1h'].iloc[i] > 0:
            return 'long'
        else:
            return 'short'
    
    return False


def panic_reversal_signal(df, i):
    """
    Panic Reversal - 恐慌反转（已验证的策略）
    """
    score = 0
    
    # 超卖
    if df['rsi_14'].iloc[i] < 30:
        score += 2
    
    # 恐慌状态
    if df['state_panic_dump'].iloc[i] > 0:
        score += 2
    
    # 低波动即将结束
    if df['state_accumulation'].iloc[i] > 0:
        score += 1
    
    # 波动率放大
    if df['volatility_ratio'].iloc[i] > 1.5:
        score += 1
    
    return score >= 4


def run_backtest(df, start_date=None, end_date=None):
    """运行回测"""
    if start_date:
        df = df[df.index >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df.index <= pd.to_datetime(end_date)]
    
    initial_capital = 10000
    capital = initial_capital
    position = 0
    entry_price = 0
    trades = []
    
    leverage = 50
    take_profit_pct = 0.03  # 3% 止盈
    stop_loss_pct = 0.02    # 2% 止损
    
    print(f"\n🚀 开始回测...")
    print(f"📅 时间范围: {df.index[0]} ~ {df.index[-1]}")
    
    for i in range(60, len(df)):  # 跳过前60根K线做预热
        current_price = df['close'].iloc[i]
        
        # 有持仓时检查止盈止损
        if position != 0:
            pct_change = (current_price - entry_price) / entry_price if position == 1 else (entry_price - current_price) / entry_price
            
            if pct_change >= take_profit_pct:
                # 止盈
                profit = (current_price - entry_price) * position * leverage
                capital += profit
                trades.append({
                    'type': 'close',
                    'direction': 'long' if position == 1 else 'short',
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'profit': profit,
                    'reason': 'take_profit'
                })
                position = 0
            
            elif pct_change <= -stop_loss_pct:
                # 止损
                loss = (current_price - entry_price) * position * leverage
                capital += loss
                trades.append({
                    'type': 'close',
                    'direction': 'long' if position == 1 else 'short',
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'profit': loss,
                    'reason': 'stop_loss'
                })
                position = 0
        
        # 无持仓时寻找机会
        if position == 0:
            # 策略1: Smart Money Detection - 做多
            if smart_money_signal(df, i):
                position = 1
                entry_price = current_price
                trades.append({
                    'type': 'open',
                    'direction': 'long',
                    'strategy': 'smart_money',
                    'price': current_price
                })
            
            # 策略2: Panic Reversal - 做多
            elif panic_reversal_signal(df, i):
                position = 1
                entry_price = current_price
                trades.append({
                    'type': 'open',
                    'direction': 'long',
                    'strategy': 'panic_reversal',
                    'price': current_price
                })
            
            # 策略3: 趋势衰竭做空
            elif trend_exhaustion_signal(df, i) == 'short':
                position = -1
                entry_price = current_price
                trades.append({
                    'type': 'open',
                    'direction': 'short',
                    'strategy': 'trend_exhaustion',
                    'price': current_price
                })
            
            # 策略4: 趋势衰竭做多
            elif trend_exhaustion_signal(df, i) == 'long':
                position = 1
                entry_price = current_price
                trades.append({
                    'type': 'open',
                    'direction': 'long',
                    'strategy': 'trend_exhaustion',
                    'price': current_price
                })
    
    # 回测结束
    closed_trades = [t for t in trades if t['type'] == 'close']
    
    if len(closed_trades) > 0:
        wins = [t for t in closed_trades if t['profit'] > 0]
        total_profit = sum(t['profit'] for t in closed_trades)
        win_rate = len(wins) / len(closed_trades)
        
        # 计算最大回撤
        equity_curve = [initial_capital]
        current_equity = initial_capital
        for trade in closed_trades:
            current_equity += trade['profit']
            equity_curve.append(current_equity)
        
        max_drawdown = 0
        peak = equity_curve[0]
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        print(f"\n{'='*60}")
        print(f"📊 回测结果")
        print(f"{'='*60}")
        print(f"初始资金: ${initial_capital:,.2f}")
        print(f"最终资金: ${capital:,.2f}")
        print(f"总收益: ${total_profit:,.2f} ({(total_profit/initial_capital*100):.1f}%)")
        print(f"交易次数: {len(closed_trades)}")
        print(f"胜率: {win_rate:.1%}")
        print(f"最大回撤: {max_drawdown:.1%}")
        print(f"盈亏比: {(abs(total_profit/len(wins)) if len(wins) > 0 else 0)/(abs((total_profit - sum(t['profit'] for t in wins))/(len(closed_trades)-len(wins))) if len(closed_trades) > len(wins) else 1):.2f}")
        
        # 策略统计
        strategy_stats = {}
        for trade in closed_trades:
            strategy = trade.get('strategy', 'unknown')
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {'count': 0, 'profit': 0}
            strategy_stats[strategy]['count'] += 1
            strategy_stats[strategy]['profit'] += trade['profit']
        
        print(f"\n📈 各策略表现:")
        for strategy, stats in strategy_stats.items():
            print(f"  {strategy}: {stats['count']}次, 收益 ${stats['profit']:.0f}")
        
        # 保存结果
        results = {
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_profit': total_profit,
            'return_pct': total_profit / initial_capital * 100,
            'trade_count': len(closed_trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': closed_trades,
            'strategy_stats': strategy_stats
        }
        
        output_file = project_root / "data_lake" / "research" / "smart_money_backtest_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✅ 结果已保存到: {output_file}")
    
    return capital


def main():
    print("=" * 60)
    print("🚀 智能策略回测系统")
    print("=" * 60)
    
    df = load_data()
    
    print("\n" + "="*60)
    print("📊 全部数据回测 (2024-2026)")
    print("="*60)
    run_backtest(df)
    
    print("\n" + "="*60)
    print("📊 近5个月回测")
    print("="*60)
    start_5mo = datetime.now() - timedelta(days=150)
    run_backtest(df, start_date=start_5mo.strftime('%Y-%m-%d'))


if __name__ == "__main__":
    main()
