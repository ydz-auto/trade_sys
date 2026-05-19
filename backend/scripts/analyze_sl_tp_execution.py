#!/usr/bin/env python3
"""
止盈止损执行质量分析
====================

分析维度:
1. 止损后价格走势 - 是否被洗
2. 止盈后价格走势 - 是否过早
3. 盈亏分布与触发频率
4. 最优止盈止损位反推
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
import pandas as pd
import numpy as np
from collections import defaultdict


def load_trades(strategy_name: str) -> pd.DataFrame:
    """加载交易数据"""
    file_path = backend_path / f"data_lake/research/_tmp_{strategy_name}_trades.json"
    with open(file_path, 'r') as f:
        trades = json.load(f)
    return pd.DataFrame(trades)


def analyze_stop_loss_quality(df: pd.DataFrame, fe, bars_after: int = 12):
    """
    分析止损质量 - 止损后价格是否继续下跌
    
    bars_after: 止损后看多少根bar (12 = 12分钟)
    """
    sl_trades = df[df['exit_reason'] == 'stop_loss'].copy()
    if len(sl_trades) == 0:
        return None
    
    results = {
        'total_sl': len(sl_trades),
        'price_continue_down': 0,  # 止损后价格继续下跌(正确)
        'price_reverse_up': 0,     # 止损后价格反弹(被洗)
        'avg_move_after_sl': [],   # 止损后价格变动
    }
    
    for _, trade in sl_trades.iterrows():
        # 找到交易在数据中的位置
        # 这里简化处理，用exit_time估算
        exit_price = trade['exit_price']
        direction = trade.get('direction', 'long')  # 默认做多
        
        # 简化: 用max_adverse估算
        # 如果max_adverse接近止损位，说明止损执行正确
        max_adverse = trade['max_adverse']
        max_favorable = trade['max_favorable']
        
        # 判断: 如果最大有利波动很小，说明入场后立刻反向
        if max_favorable < 50:  # 小于50点
            results['price_continue_down'] += 1
        else:
            results['price_reverse_up'] += 1
            
        results['avg_move_after_sl'].append(max_adverse)
    
    results['avg_move_after_sl'] = np.mean(results['avg_move_after_sl'])
    results['correct_sl_pct'] = results['price_continue_down'] / results['total_sl'] * 100
    
    return results


def analyze_take_profit_quality(df: pd.DataFrame, bars_after: int = 12):
    """
    分析止盈质量 - 止盈后价格是否继续上涨
    
    关键指标:
    - 止盈后价格继续上涨的比例(过早止盈)
    - 最大有利波动 vs 实际止盈位差距
    """
    tp_trades = df[df['exit_reason'] == 'trailing_tp'].copy()
    if len(tp_trades) == 0:
        return None
    
    results = {
        'total_tp': len(tp_trades),
        'early_tp': 0,              # 过早止盈(价格继续上涨)
        'perfect_tp': 0,            # 完美止盈(价格反转)
        'max_favorable_avg': tp_trades['max_favorable'].mean(),
        'trailing_tp_hit_avg': tp_trades['trailing_tp_hit'].mean(),
        'unrealized_profit': [],    # 未实现利润(本可以赚更多)
    }
    
    for _, trade in tp_trades.iterrows():
        max_fav = trade['max_favorable']
        tp_hit = trade['trailing_tp_hit']
        
        # 如果最大有利波动 > 止盈位 * 1.2，说明过早止盈
        if max_fav > tp_hit * 1.2:
            results['early_tp'] += 1
            results['unrealized_profit'].append(max_fav - tp_hit)
        else:
            results['perfect_tp'] += 1
    
    results['early_tp_pct'] = results['early_tp'] / results['total_tp'] * 100
    results['unrealized_profit_avg'] = np.mean(results['unrealized_profit']) if results['unrealized_profit'] else 0
    
    return results


def calculate_optimal_levels(df: pd.DataFrame):
    """
    反推最优止盈止损位
    
    基于历史数据，计算:
    - 最优止损位: 使止损后反转最少
    - 最优止盈位: 使过早止盈最少
    """
    results = {}
    
    # 止损分析
    sl_df = df[df['exit_reason'] == 'stop_loss']
    if len(sl_df) > 0:
        results['sl_analysis'] = {
            'avg_max_adverse': sl_df['max_adverse'].mean(),
            'median_max_adverse': sl_df['max_adverse'].median(),
            'p95_max_adverse': sl_df['max_adverse'].quantile(0.95),
            'suggestion': f"当前止损约200点，实际平均不利波动{sl_df['max_adverse'].mean():.0f}点"
        }
    
    # 止盈分析
    tp_df = df[df['exit_reason'] == 'trailing_tp']
    if len(tp_df) > 0:
        results['tp_analysis'] = {
            'avg_max_favorable': tp_df['max_favorable'].mean(),
            'median_max_favorable': tp_df['max_favorable'].median(),
            'p95_max_favorable': tp_df['max_favorable'].quantile(0.95),
            'p99_max_favorable': tp_df['max_favorable'].quantile(0.99),
            'current_tp_hit_avg': tp_df['trailing_tp_hit'].mean(),
            'suggestion': f"当前止盈位{tp_df['trailing_tp_hit'].mean():.0f}点，但价格平均只走到{tp_df['max_favorable'].mean():.0f}点"
        }
    
    return results


def print_detailed_report(strategy_name: str, df: pd.DataFrame):
    """打印详细分析报告"""
    print(f"\n{'='*100}")
    print(f"  【{strategy_name.replace('_', ' ')}】止盈止损执行质量分析")
    print(f"{'='*100}")
    
    # 1. 基础统计
    print(f"\n📊 基础统计:")
    print(f"   总交易数: {len(df)}")
    print(f"   止损次数: {(df['exit_reason']=='stop_loss').sum()} ({(df['exit_reason']=='stop_loss').mean()*100:.1f}%)")
    print(f"   止盈次数: {(df['exit_reason']=='trailing_tp').sum()} ({(df['exit_reason']=='trailing_tp').mean()*100:.1f}%)")
    print(f"   超时次数: {(df['exit_reason']=='time_exit').sum()} ({(df['exit_reason']=='time_exit').mean()*100:.1f}%)")
    
    # 2. 止损质量分析
    print(f"\n📉 止损质量分析:")
    sl_df = df[df['exit_reason'] == 'stop_loss']
    if len(sl_df) > 0:
        # 判断止损是否正确
        immediate_reverse = (sl_df['max_favorable'] > 100).sum()  # 止损前有过100点以上有利波动
        correct_sl = len(sl_df) - immediate_reverse
        
        print(f"   止损次数: {len(sl_df)}")
        print(f"   正确止损(趋势继续): {correct_sl} ({correct_sl/len(sl_df)*100:.1f}%)")
        print(f"   被洗止损(立即反转): {immediate_reverse} ({immediate_reverse/len(sl_df)*100:.1f}%)")
        print(f"   平均最大不利波动: {sl_df['max_adverse'].mean():.0f}点")
        print(f"   平均最大有利波动: {sl_df['max_favorable'].mean():.0f}点")
        
        if immediate_reverse / len(sl_df) > 0.3:
            print(f"   ⚠️ 警告: 超过30%止损被洗，建议放宽止损或调整入场时机")
    
    # 3. 止盈质量分析
    print(f"\n📈 止盈质量分析:")
    tp_df = df[df['exit_reason'] == 'trailing_tp']
    if len(tp_df) > 0:
        # 判断是否过早止盈
        early_tp = (tp_df['max_favorable'] > tp_df['trailing_tp_hit'] * 1.3).sum()
        perfect_tp = len(tp_df) - early_tp
        
        print(f"   止盈次数: {len(tp_df)}")
        print(f"   过早止盈(价格继续): {early_tp} ({early_tp/len(tp_df)*100:.1f}%)")
        print(f"   完美止盈(价格反转): {perfect_tp} ({perfect_tp/len(tp_df)*100:.1f}%)")
        print(f"   平均实际止盈位: {tp_df['trailing_tp_hit'].mean():.0f}点")
        print(f"   平均最大有利波动: {tp_df['max_favorable'].mean():.0f}点")
        print(f"   有利/止盈比: {tp_df['max_favorable'].mean()/tp_df['trailing_tp_hit'].mean():.2f}x")
        
        # 止盈档位分析
        print(f"\n   止盈档位分布:")
        for level in [500, 1000, 1500, 2000, 2500, 3000]:
            count = (tp_df['trailing_tp_hit'] >= level).sum()
            if count > 0:
                print(f"      ≥{level}点: {count}笔 ({count/len(tp_df)*100:.1f}%)")
        
        if tp_df['trailing_tp_hit'].mean() > tp_df['max_favorable'].mean() * 1.5:
            print(f"   ⚠️ 警告: 止盈位远高于价格实际能达到的波动，建议降低止盈位")
    
    # 4. 最优参数反推
    print(f"\n🎯 最优参数反推:")
    opt = calculate_optimal_levels(df)
    if 'sl_analysis' in opt:
        sl = opt['sl_analysis']
        print(f"   止损分析:")
        print(f"      当前: ~200点 (10%本金 @ 50x)")
        print(f"      实际平均不利: {sl['avg_max_adverse']:.0f}点")
        print(f"      P95不利: {sl['p95_max_adverse']:.0f}点")
        print(f"      建议: {'维持当前' if sl['avg_max_adverse'] < 250 else '考虑放宽'}")
    
    if 'tp_analysis' in opt:
        tp = opt['tp_analysis']
        print(f"   止盈分析:")
        print(f"      当前平均止盈位: {tp['current_tp_hit_avg']:.0f}点")
        print(f"      价格实际能走到: {tp['avg_max_favorable']:.0f}点 (平均)")
        print(f"      P95波动: {tp['p95_max_favorable']:.0f}点")
        print(f"      P99波动: {tp['p99_max_favorable']:.0f}点")
        print(f"      建议止盈位: {tp['p95_max_favorable']*0.8:.0f}点 (P95的80%)")
    
    # 5. 时间分析
    print(f"\n⏱️ 持仓时间分析:")
    print(f"   平均持仓: {df['hold_bars'].mean():.1f} bars")
    print(f"   中位数持仓: {df['hold_bars'].median():.0f} bars")
    print(f"   持仓≤1 bar: {(df['hold_bars']<=1).sum()} ({(df['hold_bars']<=1).mean()*100:.1f}%)")
    print(f"   持仓>10 bars: {(df['hold_bars']>10).sum()} ({(df['hold_bars']>10).mean()*100:.1f}%)")
    
    if df['hold_bars'].mean() < 2:
        print(f"   ⚠️ 警告: 平均持仓时间极短，可能过度交易")


def compare_strategies():
    """对比三个策略"""
    strategies = ['Liquidation_Cascade', 'Short_Squeeze', 'Fake_Breakout_Trap']
    
    summary = {}
    for strat in strategies:
        try:
            df = load_trades(strat)
            summary[strat] = {
                'total_trades': len(df),
                'sl_count': (df['exit_reason']=='stop_loss').sum(),
                'tp_count': (df['exit_reason']=='trailing_tp').sum(),
                'win_rate': (df['pnl_pct'] > 0).mean(),
                'avg_hold_bars': df['hold_bars'].mean(),
            }
        except Exception as e:
            print(f"加载 {strat} 失败: {e}")
    
    print(f"\n{'='*100}")
    print(f"  三策略对比")
    print(f"{'='*100}")
    print(f"\n{'策略':<25} | {'交易数':>8} | {'胜率':>8} | {'止损率':>8} | {'止盈率':>8} | {'持仓bars':>10}")
    print(f"{'-'*100}")
    for strat, data in summary.items():
        sl_pct = data['sl_count'] / data['total_trades'] * 100
        tp_pct = data['tp_count'] / data['total_trades'] * 100
        print(f"{strat.replace('_', ' '):<25} | {data['total_trades']:>8} | {data['win_rate']*100:>7.1f}% | {sl_pct:>7.1f}% | {tp_pct:>7.1f}% | {data['avg_hold_bars']:>10.1f}")


def main():
    print("="*100)
    print("  止盈止损执行质量深度分析")
    print("="*100)
    
    strategies = ['Liquidation_Cascade', 'Short_Squeeze', 'Fake_Breakout_Trap']
    
    for strat in strategies:
        try:
            df = load_trades(strat)
            print_detailed_report(strat, df)
        except Exception as e:
            print(f"\n分析 {strat} 失败: {e}")
    
    # 对比
    compare_strategies()
    
    print(f"\n{'='*100}")
    print("  分析完成")
    print(f"{'='*100}")


if __name__ == "__main__":
    main()
