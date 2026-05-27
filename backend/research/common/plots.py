"""
Common Plots - 通用可视化工具

提供研究结果的可视化功能。
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional


def plot_signal_distribution(
    signal_counts: Dict[str, int],
    confidence_dist: List[float],
    output_path: Optional[str] = None
):
    """
    绘制信号分布
    
    Args:
        signal_counts: 信号类型计数 {'long': int, 'short': int, 'none': int}
        confidence_dist: 置信度分布列表
        output_path: 输出路径（可选）
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # 信号类型分布
    labels = list(signal_counts.keys())
    counts = list(signal_counts.values())
    ax1.pie(counts, labels=labels, autopct='%1.1f%%', startangle=90)
    ax1.set_title('Signal Type Distribution')
    
    # 置信度分布
    ax2.hist(confidence_dist, bins=20, alpha=0.7)
    ax2.set_title('Confidence Distribution')
    ax2.set_xlabel('Confidence')
    ax2.set_ylabel('Count')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150)
    else:
        plt.show()


def plot_event_study_results(
    window_results: Dict[int, Dict[str, float]],
    output_path: Optional[str] = None
):
    """
    绘制事件研究结果
    
    Args:
        window_results: 窗口结果 {window: {'hit_rate': float, 'avg_return': float}}
        output_path: 输出路径（可选）
    """
    windows = sorted(window_results.keys())
    hit_rates = [window_results[w]['hit_rate'] for w in windows]
    avg_returns = [window_results[w]['avg_return'] for w in windows]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    ax1.bar([str(w) for w in windows], hit_rates)
    ax1.axhline(0.5, color='red', linestyle='--', label='50%')
    ax1.set_title('Hit Rate by Forward Window')
    ax1.set_ylabel('Hit Rate')
    ax1.legend()
    
    ax2.bar([str(w) for w in windows], avg_returns)
    ax2.axhline(0, color='red', linestyle='--')
    ax2.set_title('Average Return by Forward Window')
    ax2.set_xlabel('Forward Bars')
    ax2.set_ylabel('Return')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150)
    else:
        plt.show()


def plot_backtest_results(
    equity_curve: np.ndarray,
    drawdown: np.ndarray,
    output_path: Optional[str] = None
):
    """
    绘制回测结果
    
    Args:
        equity_curve: 权益曲线
        drawdown: 回撤曲线
        output_path: 输出路径（可选）
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    ax1.plot(equity_curve)
    ax1.set_title('Equity Curve')
    ax1.set_ylabel('Equity')
    ax1.grid(True)
    
    ax2.fill_between(range(len(drawdown)), drawdown, 0, color='red', alpha=0.3)
    ax2.plot(drawdown, color='red')
    ax2.set_title('Drawdown')
    ax2.set_xlabel('Trade')
    ax2.set_ylabel('Drawdown')
    ax2.grid(True)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150)
    else:
        plt.show()


def plot_walk_forward_results(
    window_returns: List[float],
    window_sharpes: List[float],
    output_path: Optional[str] = None
):
    """
    绘制滚动验证结果
    
    Args:
        window_returns: 各窗口收益
        window_sharpes: 各窗口夏普比率
        output_path: 输出路径（可选）
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    ax1.plot(window_returns, marker='o', linestyle='-')
    ax1.axhline(0, color='red', linestyle='--')
    ax1.set_title('Walk Forward Returns')
    ax1.set_ylabel('Return')
    ax1.grid(True)
    
    ax2.plot(window_sharpes, marker='o', linestyle='-')
    ax2.axhline(0, color='red', linestyle='--')
    ax2.set_title('Walk Forward Sharpe Ratios')
    ax2.set_xlabel('Window')
    ax2.set_ylabel('Sharpe')
    ax2.grid(True)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150)
    else:
        plt.show()


def plot_regime_results(
    regime_results: Dict[str, Dict[str, float]],
    output_path: Optional[str] = None
):
    """
    绘制状态测试结果
    
    Args:
        regime_results: 状态结果 {regime: {'hit_rate': float, 'avg_return': float}}
        output_path: 输出路径（可选）
    """
    regimes = list(regime_results.keys())
    hit_rates = [regime_results[r]['hit_rate'] for r in regimes]
    avg_returns = [regime_results[r]['avg_return'] for r in regimes]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    ax1.bar(regimes, hit_rates)
    ax1.axhline(0.5, color='red', linestyle='--')
    ax1.set_title('Hit Rate by Regime')
    ax1.set_ylabel('Hit Rate')
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    ax2.bar(regimes, avg_returns)
    ax2.axhline(0, color='red', linestyle='--')
    ax2.set_title('Average Return by Regime')
    ax2.set_xlabel('Regime')
    ax2.set_ylabel('Return')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150)
    else:
        plt.show()


def print_results_table(results: pd.DataFrame, title: str = ''):
    """
    打印结果表格
    
    Args:
        results: 结果 DataFrame
        title: 标题
    """
    if title:
        print(f"\n{title}")
        print("=" * len(title))
    
    print(results.to_string())


__all__ = [
    'plot_signal_distribution',
    'plot_event_study_results',
    'plot_backtest_results',
    'plot_walk_forward_results',
    'plot_regime_results',
    'print_results_table',
]
