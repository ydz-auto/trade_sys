"""
Regime Test - 状态测试工具

核心：按市场状态拆开测试策略

测试的市场状态：
- trend: 趋势市场
- range: 震荡市场
- panic: 恐慌状态
- high vol: 高波动
- low vol: 低波动

Perp 策略非常 regime-dependent，必须分别测试
"""

from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from collections import Counter
import pandas as pd
import numpy as np
from scipy import stats

from engines.compute.strategy_v2 import StrategyV2, Signal

from research.common.backtest_engine import run_single_bar_backtest


@dataclass
class RegimeResult:
    """单个状态的测试结果"""
    regime_type: str
    description: str
    sample_count: int
    
    # 信号统计
    signals: int
    long_signals: int
    short_signals: int
    signal_rate: float  # 信号率（每bar）
    
    # 收益统计
    hit_rate: float
    avg_return: float
    median_return: float
    std_return: float
    
    # 风险指标
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    
    # 统计显著性
    t_stat: float
    p_value: float


@dataclass
class RegimeTestResult:
    """状态测试综合结果"""
    
    # 总体统计
    total_samples: int
    total_signals: int
    
    # 各状态结果
    regime_results: Dict[str, RegimeResult]
    
    # 状态分布
    regime_distribution: Dict[str, int]
    
    # 策略在不同状态下的表现对比
    best_regime: str
    best_regime_return: float
    worst_regime: str
    worst_regime_return: float
    
    # 状态依赖性指标
    regime_dependence_score: float
    consistency_score: float
    
    def __repr__(self):
        return f"""RegimeTestResult:
  总样本数: {self.total_samples}
  总信号数: {self.total_signals}
  
  状态分布: {dict(self.regime_distribution)}
  
  最佳状态: {self.best_regime} (收益: {self.best_regime_return:.4f})
  最差状态: {self.worst_regime} (收益: {self.worst_regime_return:.4f})
  
  状态依赖度: {self.regime_dependence_score:.2%}
  一致性得分: {self.consistency_score:.2%}
"""


class RegimeClassifier:
    """
    市场状态分类器
    
    根据市场上下文自动分类市场状态：
    - TREND_UP: 上升趋势
    - TREND_DOWN: 下降趋势
    - RANGE: 震荡区间
    - PANIC: 恐慌状态
    - HIGH_VOL: 高波动
    - LOW_VOL: 低波动
    """
    
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    PANIC = "panic"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    
    def __init__(
        self,
        trend_threshold: float = 0.3,
        volatility_high_threshold: float = 1.5,
        volatility_low_threshold: float = 0.5,
        panic_threshold: float = 0.02  # 2% 单日跌幅
    ):
        self.trend_threshold = trend_threshold
        self.volatility_high_threshold = volatility_high_threshold
        self.volatility_low_threshold = volatility_low_threshold
        self.panic_threshold = panic_threshold
    
    def classify(self, ctx: Any) -> List[str]:
        """
        对市场上下文进行状态分类
        
        Args:
            ctx: MarketContext
        
        Returns:
            List[str]: 状态标签列表（一个样本可能属于多个状态）
        """
        regimes = []
        
        # 趋势判断（基于 1h 和 4h 的趋势状态）
        h4_trend = getattr(ctx.tf.get("4h"), 'trend', None)
        h1_trend = getattr(ctx.tf.get("1h"), 'trend', None)
        
        if h4_trend and hasattr(h4_trend, 'state'):
            trend_state = h4_trend.state
            if trend_state in ("STRONG_UP", "WEAK_UP"):
                regimes.append(self.TREND_UP)
            elif trend_state in ("STRONG_DOWN", "WEAK_DOWN"):
                regimes.append(self.TREND_DOWN)
            else:
                regimes.append(self.RANGE)
        
        # 波动判断
        volatility = getattr(ctx.tf.get("15m"), 'volatility', None)
        if volatility and hasattr(volatility, 'state'):
            vol_state = volatility.state
            if vol_state in ("ELEVATED", "EXTREME"):
                regimes.append(self.HIGH_VOL)
            elif vol_state == "LOW":
                regimes.append(self.LOW_VOL)
        
        # 恐慌判断（基于价格变化）
        price = getattr(ctx.tf.get("1m"), 'price', None)
        if price and hasattr(price, 'change_percent'):
            if price.change_percent < -self.panic_threshold * 100:
                regimes.append(self.PANIC)
        
        return regimes


class RegimeTester:
    """
    状态测试器
    
    核心职责：
    1. 根据市场状态分类数据
    2. 在每个状态上测试策略表现
    3. 分析策略的状态依赖性
    4. 识别策略的最佳/最差状态环境
    """
    
    def __init__(self, classifier: RegimeClassifier = None):
        self.classifier = classifier or RegimeClassifier()
        self.regime_data: Dict[str, List[Tuple[Any, int, float]]] = {}  # regime -> [(ctx, timestamp, price)]
    
    def add_sample(self, ctx: Any, timestamp: int, price: float):
        """添加样本数据"""
        regimes = self.classifier.classify(ctx)
        
        for regime in regimes:
            if regime not in self.regime_data:
                self.regime_data[regime] = []
            self.regime_data[regime].append((ctx, timestamp, price))
    
    def test(self, strategy: StrategyV2) -> RegimeTestResult:
        """执行状态测试"""
        if not self.regime_data:
            raise ValueError("没有样本数据可测试")
        
        regime_results = {}
        total_samples = sum(len(samples) for samples in self.regime_data.values())
        total_signals = 0
        
        for regime, samples in self.regime_data.items():
            result = self._test_regime(strategy, regime, samples)
            regime_results[regime] = result
            total_signals += result.signals
        
        # 计算状态分布
        regime_distribution = {
            regime: len(samples) for regime, samples in self.regime_data.items()
        }
        
        # 找出最佳/最差状态
        returns = {r: regime_results[r].avg_return for r in regime_results}
        best_regime = max(returns, key=returns.get) if returns else ""
        worst_regime = min(returns, key=returns.get) if returns else ""
        
        # 计算状态依赖度（收益的标准差 / 平均收益）
        avg_returns = [r.avg_return for r in regime_results.values()]
        if avg_returns and np.mean(avg_returns) != 0:
            regime_dependence_score = np.std(avg_returns) / abs(np.mean(avg_returns))
        else:
            regime_dependence_score = 0.0
        
        # 计算一致性得分（所有状态胜率的一致性）
        hit_rates = [r.hit_rate for r in regime_results.values()]
        if hit_rates:
            consistency_score = 1 - np.std(hit_rates)
        else:
            consistency_score = 0.0
        
        return RegimeTestResult(
            total_samples=total_samples,
            total_signals=total_signals,
            regime_results=regime_results,
            regime_distribution=regime_distribution,
            best_regime=best_regime,
            best_regime_return=returns.get(best_regime, 0),
            worst_regime=worst_regime,
            worst_regime_return=returns.get(worst_regime, 0),
            regime_dependence_score=regime_dependence_score,
            consistency_score=consistency_score
        )
    
    def _test_regime(
        self,
        strategy: StrategyV2,
        regime: str,
        samples: List[Tuple[Any, int, float]]
    ) -> RegimeResult:
        market_contexts = [ctx for ctx, _, _ in samples]
        timestamps = [ts for _, ts, _ in samples]
        prices = np.array([price for _, _, price in samples])

        signal_results, metrics = run_single_bar_backtest(
            strategy, market_contexts, timestamps, prices,
            maker_fee=0.0002, taker_fee=0.0005
        )

        sample_count = len(samples)
        signal_rate = metrics.total_trades / sample_count if sample_count > 0 else 0

        if signal_results:
            returns = [r.pnl_pct for r in signal_results]
            std_return = np.std(returns)
            t_stat, p_value = stats.ttest_1samp(returns, 0)
        else:
            std_return = 0.0
            t_stat = p_value = 0.0

        return RegimeResult(
            regime_type=regime,
            description=self._get_regime_description(regime),
            sample_count=sample_count,
            signals=metrics.total_trades,
            long_signals=metrics.long_trades,
            short_signals=metrics.short_trades,
            signal_rate=signal_rate,
            hit_rate=metrics.win_rate,
            avg_return=metrics.avg_trade_return,
            median_return=metrics.median_trade_return,
            std_return=std_return,
            max_drawdown=metrics.max_drawdown,
            sharpe_ratio=metrics.sharpe_ratio,
            profit_factor=metrics.profit_factor,
            t_stat=t_stat,
            p_value=p_value
        )
    
    def _get_regime_description(self, regime: str) -> str:
        """获取状态描述"""
        descriptions = {
            "trend_up": "上升趋势",
            "trend_down": "下降趋势",
            "range": "震荡区间",
            "panic": "恐慌状态",
            "high_vol": "高波动",
            "low_vol": "低波动"
        }
        return descriptions.get(regime, regime)
    
    def get_regimes_df(self) -> pd.DataFrame:
        """获取各状态结果的 DataFrame"""
        data = []
        for regime, result in self.regime_data.items():
            data.append({
                "regime": regime,
                "description": self._get_regime_description(regime),
                "samples": len(result),
            })
        return pd.DataFrame(data)


def run_regime_test(
    strategy: StrategyV2,
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray,
    classifier: RegimeClassifier = None
) -> RegimeTestResult:
    """
    运行状态测试
    
    Args:
        strategy: 策略实例
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
        classifier: 状态分类器（可选）
    
    Returns:
        RegimeTestResult: 状态测试结果
    """
    tester = RegimeTester(classifier=classifier)
    
    for ctx, ts, price in zip(market_contexts, timestamps, prices):
        tester.add_sample(ctx, ts, price)
    
    return tester.test(strategy)


def compare_strategy_regimes(
    strategies: List[StrategyV2],
    market_contexts: List[Any],
    timestamps: List[int],
    prices: np.ndarray
) -> pd.DataFrame:
    """
    比较多个策略的状态测试结果
    
    Args:
        strategies: 策略列表
        market_contexts: MarketContext 列表
        timestamps: 时间戳列表
        prices: 价格序列
    
    Returns:
        pd.DataFrame: 比较结果
    """
    results = []
    
    for strategy in strategies:
        result = run_regime_test(strategy, market_contexts, timestamps, prices)
        
        results.append({
            "strategy": strategy.meta.name,
            "total_samples": result.total_samples,
            "total_signals": result.total_signals,
            "best_regime": result.best_regime,
            "best_regime_return": result.best_regime_return,
            "worst_regime": result.worst_regime,
            "worst_regime_return": result.worst_regime_return,
            "regime_dependence": result.regime_dependence_score,
            "consistency_score": result.consistency_score,
        })
    
    return pd.DataFrame(results)


__all__ = [
    "RegimeResult",
    "RegimeTestResult",
    "RegimeClassifier",
    "RegimeTester",
    "run_regime_test",
    "compare_strategy_regimes",
]
