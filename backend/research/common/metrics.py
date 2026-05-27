"""
Common Metrics - 通用指标计算

提供回测和研究中使用的标准指标计算函数。
"""

import numpy as np
from scipy import stats
from typing import List, Tuple, Optional


def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益序列
        risk_free_rate: 无风险利率
    
    Returns:
        float: 夏普比率
    """
    if len(returns) == 0:
        return 0.0
    
    excess_returns = returns - risk_free_rate / len(returns)
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns)
    
    if std_excess == 0:
        return 0.0
    
    return mean_excess / std_excess * np.sqrt(len(returns))


def calculate_max_drawdown(cumulative_returns: np.ndarray) -> float:
    """
    计算最大回撤
    
    Args:
        cumulative_returns: 累积收益序列
    
    Returns:
        float: 最大回撤
    """
    if len(cumulative_returns) == 0:
        return 0.0
    
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdowns = cumulative_returns - running_max
    return np.min(drawdowns)


def calculate_profit_factor(wins: List[float], losses: List[float]) -> float:
    """
    计算盈利因子
    
    Args:
        wins: 盈利交易列表
        losses: 亏损交易列表
    
    Returns:
        float: 盈利因子
    """
    total_wins = np.sum(wins) if wins else 0.0
    total_losses = abs(np.sum(losses)) if losses else 0.0
    
    if total_losses == 0:
        return float('inf')
    
    return total_wins / total_losses


def calculate_win_rate(wins: int, total: int) -> float:
    """
    计算胜率
    
    Args:
        wins: 盈利交易数
        total: 总交易数
    
    Returns:
        float: 胜率
    """
    if total == 0:
        return 0.0
    return wins / total


def calculate_mfe_mae(
    entry_price: float,
    prices: np.ndarray,
    direction: str
) -> Tuple[float, float]:
    """
    计算最大有利波动(MFE)和最大不利波动(MAE)
    
    Args:
        entry_price: 入场价格
        prices: 后续价格序列
        direction: 交易方向 ('long', 'short')
    
    Returns:
        Tuple[float, float]: (MFE, MAE)
    """
    if len(prices) == 0:
        return 0.0, 0.0
    
    price_changes = (prices - entry_price) / entry_price
    
    if direction == 'short':
        price_changes = -price_changes
    
    mfe = np.max(price_changes)
    mae = np.min(price_changes)
    
    return mfe, mae


def calculate_hit_rate(signals: List[str], returns: List[float]) -> float:
    """
    计算命中率
    
    Args:
        signals: 信号类型列表 ('long', 'short')
        returns: 对应收益列表
    
    Returns:
        float: 命中率
    """
    if len(signals) == 0 or len(signals) != len(returns):
        return 0.0
    
    hits = 0
    for signal, ret in zip(signals, returns):
        if signal == 'long' and ret > 0:
            hits += 1
        elif signal == 'short' and ret < 0:
            hits += 1
    
    return hits / len(signals)


def t_test_mean(returns: np.ndarray, expected_mean: float = 0.0) -> Tuple[float, float]:
    """
    执行 t 检验
    
    Args:
        returns: 收益序列
        expected_mean: 期望均值
    
    Returns:
        Tuple[float, float]: (t_statistic, p_value)
    """
    if len(returns) < 2:
        return 0.0, 1.0
    
    t_stat, p_value = stats.ttest_1samp(returns, expected_mean)
    return t_stat, p_value


def confidence_interval(
    data: np.ndarray,
    confidence_level: float = 0.95
) -> Tuple[float, float]:
    """
    计算置信区间
    
    Args:
        data: 数据序列
        confidence_level: 置信水平
    
    Returns:
        Tuple[float, float]: (lower_bound, upper_bound)
    """
    if len(data) == 0:
        return 0.0, 0.0
    
    n = len(data)
    mean = np.mean(data)
    std = np.std(data)
    
    if std == 0:
        return mean, mean
    
    z_score = stats.norm.ppf((1 + confidence_level) / 2)
    margin = z_score * std / np.sqrt(n)
    
    return mean - margin, mean + margin


def calculate_kelly_criterion(win_rate: float, win_loss_ratio: float) -> float:
    """
    计算 Kelly 准则仓位
    
    Args:
        win_rate: 胜率
        win_loss_ratio: 盈亏比
    
    Returns:
        float: Kelly 仓位比例
    """
    if win_loss_ratio <= 0:
        return 0.0
    
    return win_rate - (1 - win_rate) / win_loss_ratio


__all__ = [
    'calculate_sharpe_ratio',
    'calculate_max_drawdown',
    'calculate_profit_factor',
    'calculate_win_rate',
    'calculate_mfe_mae',
    'calculate_hit_rate',
    't_test_mean',
    'confidence_interval',
    'calculate_kelly_criterion',
]
