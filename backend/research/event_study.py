"""
Event Study - 事件研究工具（最关键）

核心：验证 signal 触发后，未来走势到底怎样

验证时间窗口：
- +1 bar
- +3 bars
- +5 bars
- +10 bars

核心指标：
- hit_rate: 胜率
- avg_return: 平均收益
- median_return: 中位数收益
- MFE: 最大有利波动 (Maximum Favorable Excursion)
- MAE: 最大不利波动 (Maximum Adverse Excursion)

这是验证策略 edge 的最直接方法。

并行支持：
- symbol-level parallel: 多个交易对并行
- strategy-level parallel: 多个策略并行
- 使用 AccelerationService.parallel_map() 实现
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

from engines.compute.strategy_v2 import Signal, StrategyV2, SignalType

try:
    from infrastructure.acceleration import AccelerationService
    ACCELERATION_AVAILABLE = True
except ImportError:
    AccelerationService = None
    ACCELERATION_AVAILABLE = False

try:
    from research.common.loaders import get_strategy_class, save_results_to_json
    from research.common.types import StrategyName
except ImportError:
    from common.loaders import get_strategy_class, save_results_to_json
    from common.types import StrategyName


@dataclass
class EventResult:
    """单个事件的结果"""
    timestamp: int
    signal_type: str
    confidence: float
    reason: str
    returns: np.ndarray
    mfe: float
    mae: float
    direction_correct: bool


@dataclass
class EventStudyResult:
    """事件研究结果"""
    
    # 基础统计
    total_events: int
    long_events: int
    short_events: int
    
    # 按时间窗口的统计
    window_results: Dict[str, 'WindowResult']
    
    # 综合统计
    overall_hit_rate: float
    long_hit_rate: float
    short_hit_rate: float
    
    overall_avg_return: float
    long_avg_return: float
    short_avg_return: float
    
    overall_median_return: float
    long_median_return: float
    short_median_return: float
    
    # MFE/MAE
    avg_mfe: float
    avg_mae: float
    mfe_mae_ratio: float
    
    # 统计显著性
    t_stat: float
    p_value: float
    
    # 盈利分布
    win_distribution: Dict[str, int]
    loss_distribution: Dict[str, int]
    
    def __repr__(self):
        return f"""EventStudyResult:
  事件总数: {self.total_events}
  多头事件: {self.long_events}
  空头事件: {self.short_events}
  
  综合胜率: {self.overall_hit_rate:.2%}
  多头胜率: {self.long_hit_rate:.2%}
  空头胜率: {self.short_hit_rate:.2%}
  
  综合平均收益: {self.overall_avg_return:.4f}
  多头平均收益: {self.long_avg_return:.4f}
  空头平均收益: {self.short_avg_return:.4f}
  
  MFE/MAE 比率: {self.mfe_mae_ratio:.2f}
  统计显著性 (p-value): {self.p_value:.4f}
"""


@dataclass
class WindowResult:
    """单个时间窗口的结果"""
    window: str
    hit_rate: float
    avg_return: float
    median_return: float
    std_return: float
    positive_count: int
    negative_count: int
    t_stat: float
    p_value: float


class EventStudy:
    """
    事件研究工具
    
    核心职责：
    1. 识别信号触发事件
    2. 计算事件后的价格走势
    3. 统计胜率、收益、MFE/MAE
    4. 验证统计显著性
    """
    
    def __init__(self, windows: List[int] = None):
        """
        Args:
            windows: 要分析的未来时间窗口（以 bar 为单位）
                     默认: [1, 3, 5, 10]
        """
        self.windows = windows or [1, 3, 5, 10]
        self.events: List[EventResult] = []
    
    def add_event(
        self,
        timestamp: int,
        signal_type: str,
        confidence: float,
        reason: str,
        current_price: float,
        future_prices: np.ndarray
    ):
        """
        添加事件记录
        
        Args:
            timestamp: 事件发生时间
            signal_type: 信号类型 (long/short)
            confidence: 置信度
            reason: 信号原因
            current_price: 事件发生时的当前价格（基准）
            future_prices: 事件后的未来价格序列
        """
        if signal_type not in ("long", "short"):
            return
        
        # 计算各窗口的收益
        returns = np.zeros(len(self.windows))
        for i, window in enumerate(self.windows):
            if window <= len(future_prices):
                returns[i] = (future_prices[window - 1] - current_price) / current_price
            else:
                returns[i] = np.nan
        
        # 计算 MFE 和 MAE
        if len(future_prices) > 0:
            price_change = (future_prices - current_price) / current_price
            
            if signal_type == "long":
                mfe = np.max(price_change)
                mae = np.min(price_change)
                direction_correct = returns[0] > 0 if not np.isnan(returns[0]) else False
            else:
                mfe = np.min(price_change)
                mae = np.max(price_change)
                direction_correct = returns[0] < 0 if not np.isnan(returns[0]) else False
        else:
            mfe = 0.0
            mae = 0.0
            direction_correct = False
        
        self.events.append(EventResult(
            timestamp=timestamp,
            signal_type=signal_type,
            confidence=confidence,
            reason=reason,
            returns=returns,
            mfe=mfe,
            mae=mae,
            direction_correct=direction_correct
        ))
    
    def analyze(self) -> EventStudyResult:
        """执行事件研究分析"""
        if not self.events:
            raise ValueError("没有事件数据可分析")
        
        # 基础统计
        long_events = [e for e in self.events if e.signal_type == "long"]
        short_events = [e for e in self.events if e.signal_type == "short"]
        total_events = len(self.events)
        
        # 按窗口计算结果
        window_results = {}
        for i, window in enumerate(self.windows):
            window_key = f"+{window}bar"
            all_returns = [e.returns[i] for e in self.events if not np.isnan(e.returns[i])]
            long_returns = [e.returns[i] for e in long_events if not np.isnan(e.returns[i])]
            short_returns = [e.returns[i] for e in short_events if not np.isnan(e.returns[i])]
            
            if all_returns:
                t_stat, p_value = stats.ttest_1samp(all_returns, 0)
                
                positive_count = sum(1 for r in all_returns if r > 0)
                negative_count = sum(1 for r in all_returns if r < 0)
                hit_rate = positive_count / len(all_returns)
                
                window_results[window_key] = WindowResult(
                    window=window_key,
                    hit_rate=hit_rate,
                    avg_return=np.mean(all_returns),
                    median_return=np.median(all_returns),
                    std_return=np.std(all_returns),
                    positive_count=positive_count,
                    negative_count=negative_count,
                    t_stat=t_stat,
                    p_value=p_value
                )
        
        # 综合统计
        all_correct = sum(1 for e in self.events if e.direction_correct)
        overall_hit_rate = all_correct / total_events
        
        long_correct = sum(1 for e in long_events if e.direction_correct)
        long_hit_rate = long_correct / len(long_events) if long_events else 0
        
        short_correct = sum(1 for e in short_events if e.direction_correct)
        short_hit_rate = short_correct / len(short_events) if short_events else 0
        
        # 收益统计（使用第一个窗口）
        first_window_returns = [e.returns[0] for e in self.events if not np.isnan(e.returns[0])]
        long_first_returns = [e.returns[0] for e in long_events if not np.isnan(e.returns[0])]
        short_first_returns = [e.returns[0] for e in short_events if not np.isnan(e.returns[0])]
        
        overall_avg_return = np.mean(first_window_returns) if first_window_returns else 0
        long_avg_return = np.mean(long_first_returns) if long_first_returns else 0
        short_avg_return = np.mean(short_first_returns) if short_first_returns else 0
        
        overall_median_return = np.median(first_window_returns) if first_window_returns else 0
        long_median_return = np.median(long_first_returns) if long_first_returns else 0
        short_median_return = np.median(short_first_returns) if short_first_returns else 0
        
        # MFE/MAE
        mfes = [e.mfe for e in self.events]
        maes = [abs(e.mae) for e in self.events]
        avg_mfe = np.mean(mfes) if mfes else 0
        avg_mae = np.mean(maes) if maes else 0
        mfe_mae_ratio = avg_mfe / avg_mae if avg_mae > 0 else float('inf')
        
        # 统计显著性
        if first_window_returns:
            t_stat, p_value = stats.ttest_1samp(first_window_returns, 0)
        else:
            t_stat = p_value = 0.0
        
        # 盈利分布
        win_distribution = self._compute_win_distribution(first_window_returns)
        loss_distribution = self._compute_loss_distribution(first_window_returns)
        
        return EventStudyResult(
            total_events=total_events,
            long_events=len(long_events),
            short_events=len(short_events),
            window_results=window_results,
            overall_hit_rate=overall_hit_rate,
            long_hit_rate=long_hit_rate,
            short_hit_rate=short_hit_rate,
            overall_avg_return=overall_avg_return,
            long_avg_return=long_avg_return,
            short_avg_return=short_avg_return,
            overall_median_return=overall_median_return,
            long_median_return=long_median_return,
            short_median_return=short_median_return,
            avg_mfe=avg_mfe,
            avg_mae=avg_mae,
            mfe_mae_ratio=mfe_mae_ratio,
            t_stat=t_stat,
            p_value=p_value,
            win_distribution=win_distribution,
            loss_distribution=loss_distribution
        )
    
    def _compute_win_distribution(self, returns: List[float]) -> Dict[str, int]:
        """计算盈利分布"""
        wins = [r for r in returns if r > 0]
        if not wins:
            return {}
        
        bins = [0, 0.005, 0.01, 0.02, 0.05, float('inf')]
        labels = ["0-0.5%", "0.5-1%", "1-2%", "2-5%", ">5%"]
        
        hist, _ = np.histogram(wins, bins=bins)
        return {labels[i]: int(hist[i]) for i in range(len(labels))}
    
    def _compute_loss_distribution(self, returns: List[float]) -> Dict[str, int]:
        """计算亏损分布"""
        losses = [abs(r) for r in returns if r < 0]
        if not losses:
            return {}
        
        bins = [0, 0.005, 0.01, 0.02, 0.05, float('inf')]
        labels = ["0-0.5%", "0.5-1%", "1-2%", "2-5%", ">5%"]
        
        hist, _ = np.histogram(losses, bins=bins)
        return {labels[i]: int(hist[i]) for i in range(len(labels))}
    
    def get_events_df(self) -> pd.DataFrame:
        """获取事件数据的 DataFrame"""
        data = []
        for event in self.events:
            window_data = {f"return_{w}bar": event.returns[i] for i, w in enumerate(self.windows)}
            data.append({
                "timestamp": event.timestamp,
                "signal_type": event.signal_type,
                "confidence": event.confidence,
                "reason": event.reason,
                "mfe": event.mfe,
                "mae": event.mae,
                "direction_correct": event.direction_correct,
                **window_data
            })
        return pd.DataFrame(data)


def run_event_study(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    windows: List[int] = None
) -> EventStudyResult:
    """
    运行事件研究
    
    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列（与 market_contexts 对齐）
        windows: 要分析的未来窗口（以 bar 为单位）
    
    Returns:
        EventStudyResult: 事件研究结果
    """
    study = EventStudy(windows=windows)
    
    for i, ctx in enumerate(market_contexts):
        signal = strategy.generate_signal(ctx)
        
        if signal.type in (SignalType.LONG, SignalType.SHORT):
            # 获取未来价格（从下一个 bar 开始）
            if i + 1 < len(prices):
                current_price = prices[i]
                future_prices = prices[i + 1:]
                study.add_event(
                    timestamp=timestamps[i],
                    signal_type="long" if signal.type == SignalType.LONG else "short",
                    confidence=signal.confidence,
                    reason=signal.reason,
                    current_price=current_price,
                    future_prices=future_prices
                )
    
    return study.analyze()


def compare_strategy_events(
    strategies: List[StrategyV2],
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    windows: List[int] = None
) -> pd.DataFrame:
    """
    比较多个策略的事件研究结果（串行版本）
    
    Args:
        strategies: 策略列表
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        windows: 时间窗口
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = []
    
    for strategy in strategies:
        result = run_event_study(strategy, market_contexts, timestamps, prices, windows)
        results.append({
            "strategy": strategy.meta.name,
            "total_events": result.total_events,
            "long_events": result.long_events,
            "short_events": result.short_events,
            "overall_hit_rate": result.overall_hit_rate,
            "long_hit_rate": result.long_hit_rate,
            "short_hit_rate": result.short_hit_rate,
            "overall_avg_return": result.overall_avg_return,
            "overall_median_return": result.overall_median_return,
            "mfe_mae_ratio": result.mfe_mae_ratio,
            "p_value": result.p_value,
        })
    
    return pd.DataFrame(results)


# ==================== 并行版本 ====================

def _run_event_study_task(args):
    """
    单个事件研究任务（用于并行执行）
    
    Args:
        args: (strategy_class, symbol, market_contexts, timestamps, prices, windows)
    
    Returns:
        (strategy_name, EventStudyResult)
    """
    strategy_class, symbol, market_contexts, timestamps, prices, windows = args
    
    strategy = strategy_class(symbol)
    try:
        result = run_event_study(strategy, market_contexts, timestamps, prices, windows)
        return (strategy.meta.name, result)
    except ValueError:
        return (strategy.meta.name, None)


def run_parallel_event_study(
    strategies: List,
    symbols: List[str],
    market_contexts_dict: Dict[str, List[Any]],
    timestamps_dict: Dict[str, List[int]],
    prices_dict: Dict[str, np.ndarray],
    windows: List[int] = None,
    executor: str = "process",
    max_workers: Optional[int] = None
) -> Dict[str, Dict[str, EventStudyResult]]:
    """
    并行运行事件研究（多策略 × 多交易对）
    
    Args:
        strategies: 策略类列表（不是实例）
        symbols: 交易对列表
        market_contexts_dict: 交易对 -> MarketContext 列表
        timestamps_dict: 交易对 -> 时间戳列表
        prices_dict: 交易对 -> 价格序列
        windows: 时间窗口
        executor: 执行器类型 ("process" | "thread" | "sequential")
        max_workers: 最大工作进程数
    
    Returns:
        Dict[symbol, Dict[strategy_name, EventStudyResult]]: 结果字典
    """
    if not ACCELERATION_AVAILABLE:
        return _run_parallel_event_study_fallback(
            strategies, symbols, market_contexts_dict, timestamps_dict, prices_dict, windows
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
                windows
            ))
    
    # 并行执行
    results = service.parallel_map(_run_event_study_task, tasks, executor=executor)
    
    # 整理结果
    result_dict = {symbol: {} for symbol in symbols}
    task_idx = 0
    for strategy_class in strategies:
        for symbol in symbols:
            strategy_name, result = results[task_idx]
            if result is not None:
                result_dict[symbol][strategy_name] = result
            task_idx += 1
    
    return result_dict


def _run_parallel_event_study_fallback(
    strategies: List,
    symbols: List[str],
    market_contexts_dict: Dict[str, List[Any]],
    timestamps_dict: Dict[str, List[int]],
    prices_dict: Dict[str, np.ndarray],
    windows: List[int] = None
) -> Dict[str, Dict[str, EventStudyResult]]:
    """
    并行事件研究的降级版本（无 AccelerationService）
    
    Args:
        strategies: 策略类列表
        symbols: 交易对列表
        market_contexts_dict: 交易对 -> MarketContext 列表
        timestamps_dict: 交易对 -> 时间戳列表
        prices_dict: 交易对 -> 价格序列
        windows: 时间窗口
    
    Returns:
        Dict[symbol, Dict[strategy_name, EventStudyResult]]: 结果字典
    """
    result_dict = {symbol: {} for symbol in symbols}
    
    for strategy_class in strategies:
        for symbol in symbols:
            strategy = strategy_class(symbol)
            try:
                result = run_event_study(
                    strategy,
                    market_contexts_dict[symbol],
                    timestamps_dict[symbol],
                    prices_dict[symbol],
                    windows
                )
                result_dict[symbol][strategy.meta.name] = result
            except ValueError:
                pass
    
    return result_dict


def compare_strategy_events_parallel(
    strategies: List,
    symbols: List[str],
    market_contexts_dict: Dict[str, List[Any]],
    timestamps_dict: Dict[str, List[int]],
    prices_dict: Dict[str, np.ndarray],
    windows: List[int] = None,
    executor: str = "process"
) -> pd.DataFrame:
    """
    并行比较多个策略在多个交易对上的事件研究结果
    
    Args:
        strategies: 策略类列表
        symbols: 交易对列表
        market_contexts_dict: 交易对 -> MarketContext 列表
        timestamps_dict: 交易对 -> 时间戳列表
        prices_dict: 交易对 -> 价格序列
        windows: 时间窗口
        executor: 执行器类型
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = run_parallel_event_study(
        strategies, symbols, market_contexts_dict, timestamps_dict, prices_dict, windows, executor
    )
    
    all_rows = []
    for symbol in symbols:
        for strategy_name, result in results[symbol].items():
            all_rows.append({
                "symbol": symbol,
                "strategy": strategy_name,
                "total_events": result.total_events,
                "long_events": result.long_events,
                "short_events": result.short_events,
                "overall_hit_rate": result.overall_hit_rate,
                "long_hit_rate": result.long_hit_rate,
                "short_hit_rate": result.short_hit_rate,
                "overall_avg_return": result.overall_avg_return,
                "overall_median_return": result.overall_median_return,
                "mfe_mae_ratio": result.mfe_mae_ratio,
                "p_value": result.p_value,
            })
    
    return pd.DataFrame(all_rows)


__all__ = [
    "EventResult",
    "EventStudyResult",
    "WindowResult",
    "EventStudy",
    "run_event_study",
    "compare_strategy_events",
    # 并行版本
    "run_parallel_event_study",
    "compare_strategy_events_parallel",
]


# ==================== CLI 命令行接口 ====================

def generate_test_contexts(num_samples: int = 1000):
    """生成测试用的 MarketContext 序列（带趋势结构，用于事件研究验证）"""
    from engines.compute.context import (
        MarketContext,
        TimeframeContext,
        PriceState,
        TrendStateData,
        VolatilityStateData,
        VolumeStateData,
        FlowState,
        LiquidityStateData,
        DerivativesContext,
        OIData,
        FundingData,
        LiquidationData,
        RiskContext,
        TrendState,
        FlowPressure,
        FundingBias,
        LiquidityState,
        VolatilityState,
        VolumeState,
    )
    
    market_contexts = []
    timestamps = []
    prices = []
    
    base_timestamp = int(pd.Timestamp("2024-01-01").value / 10**6)
    base_price = 45000.0
    
    REQUIRED_TFS = ["1m", "5m", "15m", "1h", "4h"]
    extreme_prob = 0.15
    
    # 添加趋势结构：让价格在一段时间内有方向
    trend_direction = 1  # 1 表示上涨趋势，-1 表示下跌趋势
    trend_length = 0
    min_trend_length = 5
    max_trend_length = 30
    
    for i in range(num_samples):
        timestamp = base_timestamp + i * 15 * 60 * 1000
        timestamps.append(timestamp)
        
        # 更新趋势状态
        trend_length += 1
        if trend_length >= max_trend_length or (trend_length >= min_trend_length and np.random.random() < 0.05):
            trend_direction = -trend_direction
            trend_length = 0
        
        # 带有趋势偏向的价格变动
        trend_bias = trend_direction * 0.001  # 趋势偏向
        random_component = np.random.normal(0, 0.0025) * base_price
        trend_component = trend_bias * base_price
        price_change = random_component + trend_component
        price = base_price + price_change
        base_price = price
        prices.append(price)
        
        tf_contexts = {}
        
        m1_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        tf_contexts["1m"] = TimeframeContext(
            timeframe="1m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.0015)),
                low=price * (1 - np.random.uniform(0, 0.0015)),
                close=price,
                change_percent=np.random.uniform(-0.3, 0.3),
            ),
            flow=FlowState(
                pressure=m1_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-100, 100),
            ),
        )
        
        m5_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        tf_contexts["5m"] = TimeframeContext(
            timeframe="5m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.004)),
                low=price * (1 - np.random.uniform(0, 0.004)),
                close=price,
                change_percent=np.random.uniform(-0.6, 0.6),
            ),
            flow=FlowState(
                pressure=m5_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-500, 500),
            ),
        )
        
        m15_trend = np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                    p=[0.35, 0.35, 0.3])
        m15_flow_pressure = np.random.choice([FlowPressure.BUY, FlowPressure.SELL, FlowPressure.NEUTRAL], 
                                           p=[0.35, 0.35, 0.3])
        
        if np.random.random() < extreme_prob:
            m15_change_percent = np.random.uniform(0.5, 1.5)
        else:
            m15_change_percent = np.random.uniform(-1.2, 1.2)
        
        tf_contexts["15m"] = TimeframeContext(
            timeframe="15m",
            price=PriceState(
                open=price,
                high=price * (1 + np.random.uniform(0, 0.006)),
                low=price * (1 - np.random.uniform(0, 0.006)),
                close=price,
                change_percent=m15_change_percent,
            ),
            trend=TrendStateData(
                state=m15_trend,
                slope=np.random.uniform(-0.012, 0.012),
                strength=np.random.uniform(0.3, 0.95),
            ),
            volatility=VolatilityStateData(
                state=np.random.choice([VolatilityState.NORMAL, VolatilityState.ELEVATED, VolatilityState.LOW], 
                                      p=[0.5, 0.35, 0.15]),
                atr_pct=np.random.uniform(0.008, 0.025),
            ),
            volume=VolumeStateData(
                state=np.random.choice([VolumeState.NORMAL, VolumeState.CLIMAX, VolumeState.DRY], 
                                      p=[0.6, 0.25, 0.15]),
                volume_zscore=np.random.uniform(-2.5, 2.5),
            ),
            flow=FlowState(
                pressure=m15_flow_pressure,
                score=np.random.uniform(-1, 1),
                cvd=np.random.uniform(-1200, 1200),
                cvd_slope=np.random.uniform(-0.15, 0.15),
                aggressive_ratio=np.random.uniform(0.25, 0.75),
            ),
        )
        
        tf_contexts["1h"] = TimeframeContext(
            timeframe="1h",
            trend=TrendStateData(
                state=np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                      p=[0.35, 0.35, 0.3]),
                slope=np.random.uniform(-0.006, 0.006),
                strength=np.random.uniform(0.3, 0.95),
            ),
            price=PriceState(close=price, change_percent=np.random.uniform(-1.8, 1.8)),
        )
        
        tf_contexts["4h"] = TimeframeContext(
            timeframe="4h",
            trend=TrendStateData(
                state=np.random.choice([TrendState.WEAK_UP, TrendState.WEAK_DOWN, TrendState.SIDEWAYS], 
                                      p=[0.35, 0.35, 0.3]),
                slope=np.random.uniform(-0.004, 0.004),
                strength=np.random.uniform(0.3, 0.95),
            ),
        )
        
        if np.random.random() < extreme_prob:
            oi_zscore = np.random.uniform(1.6, 3.5)
        else:
            oi_zscore = np.random.uniform(-2.8, 2.8)
        
        if np.random.random() < extreme_prob:
            funding_zscore = np.random.uniform(-3.5, -1.6)
        else:
            funding_zscore = np.random.uniform(-2.8, 2.8)
        
        if funding_zscore > 2.0:
            funding_bias = FundingBias.EXTREME_POSITIVE
        elif funding_zscore > 0.5:
            funding_bias = FundingBias.POSITIVE
        elif funding_zscore < -2.0:
            funding_bias = FundingBias.EXTREME_NEGATIVE
        elif funding_zscore < -0.5:
            funding_bias = FundingBias.NEGATIVE
        else:
            funding_bias = FundingBias.NEUTRAL
        
        derivatives = DerivativesContext(
            oi=OIData(
                value=np.random.uniform(1500000, 6000000),
                delta=np.random.uniform(-150000, 150000),
                zscore=oi_zscore,
            ),
            funding=FundingData(
                rate=np.random.uniform(-0.012, 0.012),
                zscore=funding_zscore,
                bias=funding_bias,
            ),
            liquidation=LiquidationData(
                long=np.random.uniform(0, 150000),
                short=np.random.uniform(0, 150000),
                total=np.random.uniform(0, 300000),
                long_zscore=np.random.uniform(-3.5, 3.5),
                short_zscore=np.random.uniform(-3.5, 3.5),
                reversal_signal=np.random.random() < 0.1,
            ),
        )
        
        ctx = MarketContext(
            symbol="BTCUSDT",
            timestamp=timestamp,
            tf=tf_contexts,
            derivatives=derivatives,
            risk=RiskContext(multiplier=1.0),
        )
        
        market_contexts.append(ctx)
    
    return market_contexts, timestamps, np.array(prices)


def main():
    """CLI 入口函数"""
    parser = argparse.ArgumentParser(description="Event Study Tool - 事件研究工具")
    
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
        default=30,
        help="测试天数 (默认: 30)"
    )

    parser.add_argument(
        "--source",
        type=str,
        default="mock",
        choices=["mock", "datalake", "parquet"],
        help="数据源: mock(模拟), datalake(数据湖), parquet(本地parquet文件) (默认: mock)"
    )

    parser.add_argument(
        "--forward-bars",
        type=str,
        default="1,3,5,10",
        help="向前预测的 bar 数，逗号分隔 (默认: 1,3,5,10)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSON 文件路径"
    )
    
    args = parser.parse_args()
    
    print(f"事件研究: {args.strategy} | {args.symbol} | {args.days}天")
    print(f"向前窗口: {args.forward_bars}")
    print("="*50)
    
    # 解析窗口参数
    windows = [int(x.strip()) for x in args.forward_bars.split(",")]
    
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
            print(f"parquet 无数据，回退生成 {num_samples} 个模拟样本...")
            market_contexts, timestamps, prices = generate_test_contexts(num_samples)
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
    
    # 创建策略实例并运行事件研究
    strategy = strategy_class(args.symbol)
    try:
        result = run_event_study(strategy, market_contexts, timestamps, prices, windows)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)
    
    # 打印结果
    print(result)
    
    # 输出统计检验结果
    print(f"\n统计检验: t={result.t_stat:.2f}, p={result.p_value:.4f}")
    if result.p_value < 0.05:
        print("✓ 收益显著非零")
    else:
        print("✗ 收益不显著")
    
    # 保存结果
    if args.output:
        result_dict = {
            "strategy": args.strategy,
            "symbol": args.symbol,
            "days": args.days,
            "forward_windows": windows,
            "total_events": result.total_events,
            "long_events": result.long_events,
            "short_events": result.short_events,
            "overall_hit_rate": result.overall_hit_rate,
            "overall_avg_return": result.overall_avg_return,
            "mfe_mae_ratio": result.mfe_mae_ratio,
            "p_value": result.p_value,
            "window_results": {k: {
                "hit_rate": v.hit_rate,
                "avg_return": v.avg_return,
                "median_return": v.median_return,
            } for k, v in result.window_results.items()},
        }
        save_results_to_json(result_dict, args.output)


if __name__ == "__main__":
    main()
