"""
Walk Forward - 滚动验证工具（非常重要）

核心：避免 curve fitting 的最有效方法

方法：
- train: 1个月
- test: 下一周
- rolling forward

验证的是策略的"时间外推能力"，而不是"历史拟合能力"

并行支持：
- window-level parallel: 多个滚动窗口并行执行（天然独立）
- strategy-level parallel: 多个策略并行
- symbol-level parallel: 多个交易对并行
- 使用 AccelerationService.parallel_backtest() 实现
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import pandas as pd
import numpy as np
from scipy import stats
import argparse

# 自动添加项目根目录到 sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engines.compute.strategy_v2 import StrategyV2, SignalType

try:
    from infrastructure.acceleration import AccelerationService
    ACCELERATION_AVAILABLE = True
except ImportError:
    AccelerationService = None
    ACCELERATION_AVAILABLE = False

try:
    from research.common.loaders import get_strategy_class, save_results_to_json
    from research.common.types import StrategyName
    from research.common.backtest_engine import (
        run_single_bar_backtest, run_holding_period_backtest,
        BacktestMetrics, SingleSignalResult,
    )
    from research.common.mock import generate_test_contexts
except ImportError:
    from common.loaders import get_strategy_class, save_results_to_json
    from common.types import StrategyName
    from common.backtest_engine import (
        run_single_bar_backtest, run_holding_period_backtest,
        BacktestMetrics, SingleSignalResult,
    )
    from common.mock import generate_test_contexts


@dataclass
class WalkForwardResult:
    """滚动验证结果"""
    
    # 基础信息
    total_windows: int
    train_period_days: int
    test_period_days: int
    
    # 按窗口的结果
    window_results: List['WindowResult']
    
    # 综合统计
    avg_hit_rate: float
    avg_return: float
    avg_sharpe: float
    
    # 稳定性指标
    hit_rate_std: float
    return_std: float
    sharpe_std: float
    
    # 最差/最佳窗口
    best_window_idx: int
    best_window_return: float
    worst_window_idx: int
    worst_window_return: float
    
    # 胜率一致性
    win_rate_consistency: float
    profit_factor: float
    
    def __repr__(self):
        return f"""WalkForwardResult:
  滚动窗口数: {self.total_windows}
  训练周期: {self.train_period_days}天
  测试周期: {self.test_period_days}天
  
  平均胜率: {self.avg_hit_rate:.2%}
  平均收益: {self.avg_return:.4f}
  平均 Sharpe: {self.avg_sharpe:.2f}
  
  收益稳定性 (标准差): {self.return_std:.4f}
  胜率一致性: {self.win_rate_consistency:.2%}
  盈利因子: {self.profit_factor:.2f}
  
  最佳窗口收益: {self.best_window_return:.4f}
  最差窗口收益: {self.worst_window_return:.4f}
"""


@dataclass
class WindowResult:
    """单个滚动窗口的结果"""
    window_idx: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    
    # 信号统计
    signals: int
    long_signals: int
    short_signals: int
    
    # 收益统计
    total_return: float
    avg_return: float
    median_return: float
    
    # 风险指标
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float


class WalkForwardAnalyzer:
    """
    滚动验证分析器
    
    核心职责：
    1. 划分滚动窗口（训练集 + 测试集）
    2. 在每个窗口上验证策略
    3. 分析策略的时间外推能力
    4. 检测过拟合
    """
    
    def __init__(
        self,
        train_period_days: int = 30,
        test_period_days: int = 7,
        gap_days: int = 0,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
        slippage_bps: float = 2.0,
        holding_bars: int = 1,
    ):
        """
        Args:
            train_period_days: 训练周期（天数）
            test_period_days: 测试周期（天数）
            gap_days: 训练集和测试集之间的间隔天数
            maker_fee: Maker手续费率
            taker_fee: Taker手续费率
            slippage_bps: 滑点（基点）
            holding_bars: 持仓bar数（1=单bar评估，>1=持仓周期回测）
        """
        self.train_period_days = train_period_days
        self.test_period_days = test_period_days
        self.gap_days = gap_days
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage_bps = slippage_bps
        self.holding_bars = holding_bars
        self.window_results: List[WindowResult] = []
    
    def analyze(
        self,
        strategy: StrategyV2,
        market_contexts: List[Any],
        timestamps: List[int],
        prices: np.ndarray
    ) -> WalkForwardResult:
        """
        执行滚动验证分析
        
        Args:
            strategy: 策略实例
            market_contexts: MarketContext 列表
            timestamps: 时间戳列表（毫秒）
            prices: 价格序列
        
        Returns:
            WalkForwardResult: 滚动验证结果
        """
        if len(market_contexts) != len(timestamps) or len(timestamps) != len(prices):
            raise ValueError("market_contexts, timestamps, prices 长度必须一致")
        
        if not market_contexts:
            raise ValueError("没有数据可分析")
        
        # 计算窗口大小（以 bar 为单位）
        train_bars = self._days_to_bars(self.train_period_days, timestamps)
        test_bars = self._days_to_bars(self.test_period_days, timestamps)
        gap_bars = self._days_to_bars(self.gap_days, timestamps)
        
        if train_bars + test_bars >= len(market_contexts):
            raise ValueError("数据不足以划分一个完整的训练-测试窗口")
        
        # 执行滚动验证
        idx = 0
        while idx + train_bars + gap_bars + test_bars <= len(market_contexts):
            train_end = idx + train_bars
            test_start = train_end + gap_bars
            test_end = test_start + test_bars
            
            # 获取窗口数据
            test_contexts = market_contexts[test_start:test_end]
            test_timestamps = timestamps[test_start:test_end]
            test_prices = prices[test_start:test_end]
            
            # 验证策略在测试集上的表现
            window_result = self._evaluate_window(
                strategy,
                test_contexts,
                test_timestamps,
                test_prices,
                idx,
                timestamps[idx],
                timestamps[train_end],
                timestamps[test_start],
                timestamps[test_end - 1],
                maker_fee=self.maker_fee,
                taker_fee=self.taker_fee,
                slippage_bps=self.slippage_bps,
                holding_bars=self.holding_bars
            )
            
            self.window_results.append(window_result)
            idx += test_bars  # 滚动到下一个窗口
        
        if not self.window_results:
            raise ValueError("无法划分任何有效窗口")
        
        return self._compute_summary()
    
    def _days_to_bars(self, days: int, timestamps: List[int]) -> int:
        """将天数转换为 bar 数量"""
        if days <= 0:
            return 0
        
        # 计算平均 bar 间隔（毫秒）
        intervals = np.diff(timestamps)
        avg_interval = np.mean(intervals) if len(intervals) > 0 else 60000  # 默认 1分钟
        
        # 计算天数对应的毫秒数
        days_ms = days * 24 * 60 * 60 * 1000
        
        return int(days_ms / avg_interval)
    
    def _evaluate_window(
        self,
        strategy: StrategyV2,
        contexts: List[Any],
        timestamps: List[int],
        prices: np.ndarray,
        window_idx: int,
        train_start: int,
        train_end: int,
        test_start: int,
        test_end: int,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
        slippage_bps: float = 2.0,
        holding_bars: int = 1,
    ) -> WindowResult:
        """
        在单个窗口上评估策略（使用统一的回测引擎）
        
        Returns:
            WindowResult: 窗口评估结果
        """
        if holding_bars <= 1:
            results, metrics = run_single_bar_backtest(
                strategy,
                contexts,
                timestamps,
                prices,
                start_idx=0,
                end_idx=None,
                maker_fee=maker_fee,
                taker_fee=taker_fee,
                slippage_bps=slippage_bps
            )
        else:
            results, metrics = run_holding_period_backtest(
                strategy,
                contexts,
                timestamps,
                prices,
                start_idx=0,
                end_idx=None,
                maker_fee=maker_fee,
                taker_fee=taker_fee,
                slippage_bps=slippage_bps,
                max_holding_bars=holding_bars
            )

        return WindowResult(
            window_idx=window_idx,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            signals=metrics.total_trades,
            long_signals=metrics.long_trades,
            short_signals=metrics.short_trades,
            total_return=metrics.total_pnl_pct,
            avg_return=metrics.avg_trade_return,
            median_return=metrics.median_trade_return,
            max_drawdown=metrics.max_drawdown,
            sharpe_ratio=metrics.sharpe_ratio,
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor
        )
    
    def _compute_summary(self) -> WalkForwardResult:
        """计算滚动验证的综合结果"""
        total_windows = len(self.window_results)
        
        # 提取统计数据
        hit_rates = [r.win_rate for r in self.window_results]
        returns = [r.total_return for r in self.window_results]
        sharpes = [r.sharpe_ratio for r in self.window_results]
        
        # 计算综合统计
        avg_hit_rate = np.mean(hit_rates) if hit_rates else 0
        avg_return = np.mean(returns) if returns else 0
        avg_sharpe = np.mean(sharpes) if sharpes else 0
        
        hit_rate_std = np.std(hit_rates) if hit_rates else 0
        return_std = np.std(returns) if returns else 0
        sharpe_std = np.std(sharpes) if sharpes else 0
        
        # 最佳/最差窗口
        best_idx = np.argmax(returns) if returns else 0
        worst_idx = np.argmin(returns) if returns else 0
        best_return = returns[best_idx] if returns else 0
        worst_return = returns[worst_idx] if returns else 0
        
        # 胜率一致性（所有窗口胜率的标准差）
        win_rate_consistency = 1 - hit_rate_std if hit_rates else 0
        
        # 盈利因子（综合）
        all_returns = []
        for r in self.window_results:
            # 模拟单个收益
            if r.signals > 0:
                all_returns.extend([r.avg_return] * r.signals)
        
        if all_returns:
            wins = [r for r in all_returns if r > 0]
            losses = [r for r in all_returns if r < 0]
            profit_factor = np.sum(wins) / abs(np.sum(losses)) if losses else float('inf')
        else:
            profit_factor = float('inf')
        
        return WalkForwardResult(
            total_windows=total_windows,
            train_period_days=self.train_period_days,
            test_period_days=self.test_period_days,
            window_results=self.window_results,
            avg_hit_rate=avg_hit_rate,
            avg_return=avg_return,
            avg_sharpe=avg_sharpe,
            hit_rate_std=hit_rate_std,
            return_std=return_std,
            sharpe_std=sharpe_std,
            best_window_idx=best_idx,
            best_window_return=best_return,
            worst_window_idx=worst_idx,
            worst_window_return=worst_return,
            win_rate_consistency=win_rate_consistency,
            profit_factor=profit_factor
        )
    
    def get_windows_df(self) -> pd.DataFrame:
        """获取窗口结果的 DataFrame"""
        data = []
        for result in self.window_results:
            data.append({
                "window_idx": result.window_idx,
                "signals": result.signals,
                "long_signals": result.long_signals,
                "short_signals": result.short_signals,
                "total_return": result.total_return,
                "avg_return": result.avg_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
            })
        return pd.DataFrame(data)


def run_walk_forward(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    train_period_days: int = 30,
    test_period_days: int = 7,
    gap_days: int = 0,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage_bps: float = 2.0,
    holding_bars: int = 1,
) -> WalkForwardResult:
    """
    运行滚动验证
    
    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        train_period_days: 训练周期（天数）
        test_period_days: 测试周期（天数）
        gap_days: 间隔天数
        maker_fee: Maker手续费率
        taker_fee: Taker手续费率
        slippage_bps: 滑点（基点）
        holding_bars: 持仓bar数（1=单bar评估，>1=持仓周期回测）
    
    Returns:
        WalkForwardResult: 滚动验证结果
    """
    analyzer = WalkForwardAnalyzer(
        train_period_days=train_period_days,
        test_period_days=test_period_days,
        gap_days=gap_days,
        maker_fee=maker_fee,
        taker_fee=taker_fee,
        slippage_bps=slippage_bps,
        holding_bars=holding_bars
    )
    
    return analyzer.analyze(strategy, market_contexts, timestamps, prices)


def compare_strategy_walk_forward(
    strategies: List[StrategyV2],
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    train_period_days: int = 30,
    test_period_days: int = 7
) -> pd.DataFrame:
    """
    比较多个策略的滚动验证结果（串行版本）
    
    Args:
        strategies: 策略列表
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        train_period_days: 训练周期
        test_period_days: 测试周期
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = []
    
    for strategy in strategies:
        result = run_walk_forward(
            strategy,
            market_contexts,
            timestamps,
            prices,
            train_period_days,
            test_period_days
        )
        
        results.append({
            "strategy": strategy.meta.name,
            "total_windows": result.total_windows,
            "avg_hit_rate": result.avg_hit_rate,
            "avg_return": result.avg_return,
            "avg_sharpe": result.avg_sharpe,
            "return_std": result.return_std,
            "win_rate_consistency": result.win_rate_consistency,
            "profit_factor": result.profit_factor,
            "best_return": result.best_window_return,
            "worst_return": result.worst_window_return,
        })
    
    return pd.DataFrame(results)


# ==================== 并行版本 ====================

def _evaluate_window_task(
    strategy_class, symbol, contexts, timestamps, prices,
    window_idx, train_start, train_end, test_start, test_end,
    maker_fee=0.0002, taker_fee=0.0005, slippage_bps=2.0, holding_bars=1,
):
    """
    单个窗口评估任务（用于并行执行）

    使用统一回测引擎（与串行路径一致）。
    CPUExecutor 会以 func(*task) 方式调用，因此参数为独立位置参数。

    Returns:
        WindowResult
    """
    strategy = strategy_class(symbol)
    
    if holding_bars <= 1:
        _, metrics = run_single_bar_backtest(
            strategy, contexts, timestamps, prices,
            start_idx=0, end_idx=None,
            maker_fee=maker_fee, taker_fee=taker_fee, slippage_bps=slippage_bps
        )
    else:
        _, metrics = run_holding_period_backtest(
            strategy, contexts, timestamps, prices,
            start_idx=0, end_idx=None,
            maker_fee=maker_fee, taker_fee=taker_fee, slippage_bps=slippage_bps,
            max_holding_bars=holding_bars
        )
    
    return WindowResult(
        window_idx=window_idx,
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        signals=metrics.total_trades,
        long_signals=metrics.long_trades,
        short_signals=metrics.short_trades,
        total_return=metrics.total_pnl_pct,
        avg_return=metrics.avg_trade_return,
        median_return=metrics.median_trade_return,
        max_drawdown=metrics.max_drawdown,
        sharpe_ratio=metrics.sharpe_ratio,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor
    )


def run_walk_forward_parallel(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    train_period_days: int = 30,
    test_period_days: int = 7,
    gap_days: int = 0,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage_bps: float = 2.0,
    holding_bars: int = 1,
    executor: str = "process",
    max_workers: Optional[int] = None
) -> WalkForwardResult:
    """
    并行运行滚动验证（窗口级别并行）
    
    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        train_period_days: 训练周期（天数）
        test_period_days: 测试周期（天数）
        gap_days: 间隔天数
        maker_fee: Maker手续费率
        taker_fee: Taker手续费率
        slippage_bps: 滑点（基点）
        holding_bars: 持仓bar数（1=单bar评估，>1=持仓周期回测）
        executor: 执行器类型 ("process" | "thread" | "sequential")
        max_workers: 最大工作进程数
    
    Returns:
        WalkForwardResult: 滚动验证结果
    """
    if len(market_contexts) != len(timestamps) or len(timestamps) != len(prices):
        raise ValueError("market_contexts, timestamps, prices 长度必须一致")
    
    if not market_contexts:
        raise ValueError("没有数据可分析")
    
    # 计算窗口大小
    intervals = np.diff(timestamps)
    avg_interval = np.mean(intervals) if len(intervals) > 0 else 60000
    day_ms = 24 * 60 * 60 * 1000
    
    train_bars = int(train_period_days * day_ms / avg_interval)
    test_bars = int(test_period_days * day_ms / avg_interval)
    gap_bars = int(gap_days * day_ms / avg_interval)
    
    if train_bars + test_bars >= len(market_contexts):
        raise ValueError("数据不足以划分一个完整的训练-测试窗口")
    
    # 构建窗口任务
    tasks = []
    idx = 0
    window_idx = 0
    
    while idx + train_bars + gap_bars + test_bars <= len(market_contexts):
        train_end = idx + train_bars
        test_start = train_end + gap_bars
        test_end = test_start + test_bars
        
        tasks.append((
            strategy.__class__,
            strategy.symbol,
            market_contexts[test_start:test_end],
            timestamps[test_start:test_end],
            prices[test_start:test_end],
            window_idx,
            timestamps[idx],
            timestamps[train_end],
            timestamps[test_start],
            timestamps[test_end - 1],
            maker_fee,
            taker_fee,
            slippage_bps,
            holding_bars,
        ))
        
        idx += test_bars
        window_idx += 1
    
    if not tasks:
        raise ValueError("无法划分任何有效窗口")
    
    # 并行执行窗口评估
    if not ACCELERATION_AVAILABLE or executor == "sequential":
        window_results = [_evaluate_window_task(*task) for task in tasks]
    else:
        service = AccelerationService.create_for_optimization(
            enable_multiprocess=executor != "sequential",
            max_workers=max_workers
        )
        window_results = service.parallel_map(_evaluate_window_task, tasks, executor=executor)
    
    # 计算综合结果
    hit_rates = [r.win_rate for r in window_results]
    returns = [r.total_return for r in window_results]
    sharpes = [r.sharpe_ratio for r in window_results]
    
    avg_hit_rate = np.mean(hit_rates) if hit_rates else 0
    avg_return = np.mean(returns) if returns else 0
    avg_sharpe = np.mean(sharpes) if sharpes else 0
    
    hit_rate_std = np.std(hit_rates) if hit_rates else 0
    return_std = np.std(returns) if returns else 0
    sharpe_std = np.std(sharpes) if sharpes else 0
    
    best_idx = np.argmax(returns) if returns else 0
    worst_idx = np.argmin(returns) if returns else 0
    best_return = returns[best_idx] if returns else 0
    worst_return = returns[worst_idx] if returns else 0
    
    win_rate_consistency = 1 - hit_rate_std if hit_rates else 0
    
    all_returns = []
    for r in window_results:
        if r.signals > 0:
            all_returns.extend([r.avg_return] * r.signals)
    
    if all_returns:
        wins = [r for r in all_returns if r > 0]
        losses = [r for r in all_returns if r < 0]
        profit_factor = np.sum(wins) / abs(np.sum(losses)) if losses else float('inf')
    else:
        profit_factor = float('inf')
    
    return WalkForwardResult(
        total_windows=len(window_results),
        train_period_days=train_period_days,
        test_period_days=test_period_days,
        window_results=window_results,
        avg_hit_rate=avg_hit_rate,
        avg_return=avg_return,
        avg_sharpe=avg_sharpe,
        hit_rate_std=hit_rate_std,
        return_std=return_std,
        sharpe_std=sharpe_std,
        best_window_idx=best_idx,
        best_window_return=best_return,
        worst_window_idx=worst_idx,
        worst_window_return=worst_return,
        win_rate_consistency=win_rate_consistency,
        profit_factor=profit_factor
    )


def _run_walk_forward_full_task(args):
    """
    完整滚动验证任务（用于多策略/多交易对并行）
    
    Args:
        args: (strategy_class, symbol, market_contexts, timestamps, prices, train_period_days, test_period_days, gap_days)
    
    Returns:
        (strategy_name, symbol, WalkForwardResult)
    """
    strategy_class, symbol, market_contexts, timestamps, prices, train_period_days, test_period_days, gap_days = args
    
    strategy = strategy_class(symbol)
    try:
        result = run_walk_forward(
            strategy, market_contexts, timestamps, prices,
            train_period_days, test_period_days, gap_days
        )
        return (strategy.meta.name, symbol, result)
    except ValueError:
        return (strategy.meta.name, symbol, None)


def run_parallel_walk_forward(
    strategies: List,
    symbols: List[str],
    market_contexts_dict: Dict[str, List[Any]],
    timestamps_dict: Dict[str, List[int]],
    prices_dict: Dict[str, np.ndarray],
    train_period_days: int = 30,
    test_period_days: int = 7,
    gap_days: int = 0,
    executor: str = "process",
    max_workers: Optional[int] = None
) -> Dict[str, Dict[str, WalkForwardResult]]:
    """
    并行运行滚动验证（多策略 × 多交易对）
    
    Args:
        strategies: 策略类列表（不是实例）
        symbols: 交易对列表
        market_contexts_dict: 交易对 -> MarketContext 列表
        timestamps_dict: 交易对 -> 时间戳列表
        prices_dict: 交易对 -> 价格序列
        train_period_days: 训练周期
        test_period_days: 测试周期
        gap_days: 间隔天数
        executor: 执行器类型
        max_workers: 最大工作进程数
    
    Returns:
        Dict[symbol, Dict[strategy_name, WalkForwardResult]]: 结果字典
    """
    if not ACCELERATION_AVAILABLE:
        return _run_parallel_walk_forward_fallback(
            strategies, symbols, market_contexts_dict, timestamps_dict, prices_dict,
            train_period_days, test_period_days, gap_days
        )
    
    service = AccelerationService.create_for_optimization(
        enable_multiprocess=executor != "sequential",
        max_workers=max_workers
    )
    
    # 构建任务列表
    tasks = []
    for strategy_class in strategies:
        for symbol in symbols:
            tasks.append((
                strategy_class,
                symbol,
                market_contexts_dict[symbol],
                timestamps_dict[symbol],
                prices_dict[symbol],
                train_period_days,
                test_period_days,
                gap_days
            ))
    
    # 并行执行
    results = service.parallel_map(_run_walk_forward_full_task, tasks, executor=executor)
    
    # 整理结果
    result_dict = {symbol: {} for symbol in symbols}
    for strategy_name, symbol, result in results:
        if result is not None:
            result_dict[symbol][strategy_name] = result
    
    return result_dict


def _run_parallel_walk_forward_fallback(
    strategies: List,
    symbols: List[str],
    market_contexts_dict: Dict[str, List[Any]],
    timestamps_dict: Dict[str, List[int]],
    prices_dict: Dict[str, np.ndarray],
    train_period_days: int = 30,
    test_period_days: int = 7,
    gap_days: int = 0
) -> Dict[str, Dict[str, WalkForwardResult]]:
    """
    并行滚动验证的降级版本（无 AccelerationService）
    """
    result_dict = {symbol: {} for symbol in symbols}
    
    for strategy_class in strategies:
        for symbol in symbols:
            strategy = strategy_class(symbol)
            try:
                result = run_walk_forward(
                    strategy,
                    market_contexts_dict[symbol],
                    timestamps_dict[symbol],
                    prices_dict[symbol],
                    train_period_days,
                    test_period_days,
                    gap_days
                )
                result_dict[symbol][strategy.meta.name] = result
            except ValueError:
                pass
    
    return result_dict


def compare_strategy_walk_forward_parallel(
    strategies: List,
    symbols: List[str],
    market_contexts_dict: Dict[str, List[Any]],
    timestamps_dict: Dict[str, List[int]],
    prices_dict: Dict[str, np.ndarray],
    train_period_days: int = 30,
    test_period_days: int = 7,
    executor: str = "process"
) -> pd.DataFrame:
    """
    并行比较多个策略在多个交易对上的滚动验证结果
    
    Args:
        strategies: 策略类列表
        symbols: 交易对列表
        market_contexts_dict: 交易对 -> MarketContext 列表
        timestamps_dict: 交易对 -> 时间戳列表
        prices_dict: 交易对 -> 价格序列
        train_period_days: 训练周期
        test_period_days: 测试周期
        executor: 执行器类型
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = run_parallel_walk_forward(
        strategies, symbols, market_contexts_dict, timestamps_dict, prices_dict,
        train_period_days, test_period_days, executor=executor
    )
    
    all_rows = []
    for symbol in symbols:
        for strategy_name, result in results[symbol].items():
            all_rows.append({
                "symbol": symbol,
                "strategy": strategy_name,
                "total_windows": result.total_windows,
                "avg_hit_rate": result.avg_hit_rate,
                "avg_return": result.avg_return,
                "avg_sharpe": result.avg_sharpe,
                "return_std": result.return_std,
                "win_rate_consistency": result.win_rate_consistency,
                "profit_factor": result.profit_factor,
                "best_return": result.best_window_return,
                "worst_return": result.worst_window_return,
            })
    
    return pd.DataFrame(all_rows)


__all__ = [
    "WalkForwardResult",
    "WindowResult",
    "WalkForwardAnalyzer",
    "run_walk_forward",
    "compare_strategy_walk_forward",
    # 并行版本
    "run_walk_forward_parallel",
    "run_parallel_walk_forward",
]


# ==================== CLI 命令行接口 ====================

def main():
    """CLI 入口函数"""
    parser = argparse.ArgumentParser(description="Walk Forward Tool - 滚动验证工具")
    
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=StrategyName.ALL,
        help=f"策略名称: {', '.join(StrategyName.ALL)}"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="交易对 (默认: BTCUSDT)"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="测试天数 (默认: 90)"
    )
    
    parser.add_argument(
        "--train-days",
        type=int,
        default=30,
        help="训练周期天数 (默认: 30)"
    )
    
    parser.add_argument(
        "--test-days",
        type=int,
        default=7,
        help="测试周期天数 (默认: 7)"
    )
    
    parser.add_argument(
        "--gap-days",
        type=int,
        default=0,
        help="间隔天数 (默认: 0)"
    )
    
    parser.add_argument(
        "--holding-bars",
        type=int,
        default=1,
        help="持仓bar数 (1=单bar评估, >1=持仓周期回测, 默认: 1)"
    )
    
    parser.add_argument(
        "--taker-fee",
        type=float,
        default=0.0005,
        help="Taker手续费率 (默认: 0.0005)"
    )
    
    parser.add_argument(
        "--maker-fee",
        type=float,
        default=0.0002,
        help="Maker手续费率 (默认: 0.0002)"
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=2.0,
        help="滑点 (基点, 默认: 2.0)"
    )
    
    parser.add_argument(
        "--source",
        type=str,
        default="mock",
        choices=["mock", "datalake", "parquet"],
        help="数据源: mock(模拟), datalake(数据湖), parquet(本地parquet文件)"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="启用并行执行 (默认)"
    )
    parser.add_argument(
        "--no-parallel",
        dest="parallel",
        action="store_false",
        help="禁用并行执行"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径"
    )
    
    args = parser.parse_args()
    
    print(f"滚动验证: {args.strategy} | {args.symbol}")
    print(f"周期: 训练 {args.train_days}天, 测试 {args.test_days}天, 间隔 {args.gap_days}天")
    print(f"总测试天数: {args.days}")
    print(f"并行模式: {'启用' if args.parallel else '禁用'}")
    print("="*50)
    
    # 获取策略类
    strategy_class = get_strategy_class(args.strategy)
    if not strategy_class:
        print(f"错误: 未知策略 {args.strategy}")
        sys.exit(1)
    
    if args.source == "parquet":
        from research.common.loaders import load_from_parquet
        market_contexts, timestamps, prices = load_from_parquet(args.symbol, args.days)
        if not market_contexts:
            samples_per_day = 96
            num_samples = args.days * samples_per_day
            print(f"parquet 无数据，回退到 mock 生成 {num_samples} 个样本...")
            market_contexts, timestamps, prices = generate_test_contexts(num_samples)
        else:
            print(f"从 parquet 加载 {len(market_contexts)} 个样本")
    elif args.source == "datalake":
        samples_per_day = 96
        num_samples = args.days * samples_per_day
        print(f"生成 {num_samples} 个样本...")
        market_contexts, timestamps, prices = generate_test_contexts(num_samples)
    else:
        samples_per_day = 96
        num_samples = args.days * samples_per_day
        print(f"生成 {num_samples} 个样本...")
        market_contexts, timestamps, prices = generate_test_contexts(num_samples)
    
    # 创建策略实例并运行滚动验证
    strategy = strategy_class(args.symbol)
    
    try:
        if args.parallel:
            result = run_walk_forward_parallel(
                strategy,
                market_contexts,
                timestamps,
                prices,
                train_period_days=args.train_days,
                test_period_days=args.test_days,
                gap_days=args.gap_days,
                maker_fee=args.maker_fee,
                taker_fee=args.taker_fee,
                slippage_bps=args.slippage,
                holding_bars=args.holding_bars,
                executor="process"
            )
        else:
            result = run_walk_forward(
                strategy,
                market_contexts,
                timestamps,
                prices,
                train_period_days=args.train_days,
                test_period_days=args.test_days,
                gap_days=args.gap_days,
                maker_fee=args.maker_fee,
                taker_fee=args.taker_fee,
                slippage_bps=args.slippage,
                holding_bars=args.holding_bars
            )
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)
    
    # 打印结果
    print(result)
    
    # 验收检查
    print("\n验收检查:")
    checks = [
        ("窗口数 > 0", result.total_windows > 0),
        ("胜率一致性 > 50%", result.win_rate_consistency > 0.5),
        ("平均夏普 > 0", result.avg_sharpe > 0),
        ("收益稳定性 < 0.01", result.return_std < 0.01),
    ]
    
    all_pass = True
    for check, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_pass = False
    
    if all_pass:
        print("\n✓ 所有检查通过")
    else:
        print("\n✗ 部分检查未通过")
    
    # 保存结果
    if args.output:
        result_dict = {
            "strategy": args.strategy,
            "symbol": args.symbol,
            "days": args.days,
            "train_days": args.train_days,
            "test_days": args.test_days,
            "gap_days": args.gap_days,
            "total_windows": result.total_windows,
            "avg_hit_rate": result.avg_hit_rate,
            "avg_return": result.avg_return,
            "avg_sharpe": result.avg_sharpe,
            "return_std": result.return_std,
            "win_rate_consistency": result.win_rate_consistency,
            "profit_factor": result.profit_factor,
            "best_return": result.best_window_return,
            "worst_return": result.worst_window_return,
        }
        save_results_to_json(result_dict, args.output)


if __name__ == "__main__":
    main()
