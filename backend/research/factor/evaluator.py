"""
Factor Evaluator - 因子评估系统

功能：
1. IC / RankIC 计算
2. IR (Information Ratio) 计算
3. Sharpe / Max Drawdown 计算
4. Turnover / Decay 分析
5. Regime Sensitivity 分析
6. 综合评分

这是因子研究的核心评估工具。
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
from scipy import stats

from infrastructure.logging import get_logger

logger = get_logger("research.factor.evaluator")


@dataclass
class EvaluationMetrics:
    """评估指标"""
    ic: float
    rank_ic: float
    ir: float
    
    sharpe: float
    max_drawdown: float
    
    turnover: float
    decay: float
    
    stability: float
    regime_sensitivity: Dict[str, float] = field(default_factory=dict)
    
    sample_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ic": self.ic,
            "rank_ic": self.rank_ic,
            "ir": self.ir,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "turnover": self.turnover,
            "decay": self.decay,
            "stability": self.stability,
            "regime_sensitivity": self.regime_sensitivity,
            "sample_count": self.sample_count,
        }


@dataclass
class EvaluationResult:
    """评估结果"""
    evaluation_id: str
    factor_id: str
    
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    
    metrics: EvaluationMetrics
    
    ic_series: List[float] = field(default_factory=list)
    returns_series: List[float] = field(default_factory=list)
    
    regime_breakdown: Dict[str, EvaluationMetrics] = field(default_factory=dict)
    
    overall_score: float = 0.0
    recommendation: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "factor_id": self.factor_id,
            "timestamp": self.timestamp.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metrics": self.metrics.to_dict(),
            "overall_score": self.overall_score,
            "recommendation": self.recommendation,
            "metadata": self.metadata,
        }


class FactorEvaluator:
    """因子评估器
    
    提供完整的因子评估能力
    """
    
    def __init__(self):
        self._regime_classifiers: Dict[str, callable] = {}
        self._regime_classifiers["bull_market"] = lambda returns: returns > 0
        self._regime_classifiers["bear_market"] = lambda returns: returns < 0
        self._regime_classifiers["high_vol"] = lambda returns: abs(returns) > np.std(returns)
        self._regime_classifiers["low_vol"] = lambda returns: abs(returns) <= np.std(returns)
    
    def register_regime_classifier(
        self,
        name: str,
        classifier: callable,
    ) -> None:
        """注册市场状态分类器"""
        self._regime_classifiers[name] = classifier
    
    async def evaluate(
        self,
        factor_id: str,
        factor_values: List[float],
        forward_returns: List[float],
        timestamps: List[datetime],
        regimes: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """评估因子"""
        if len(factor_values) != len(forward_returns):
            raise ValueError("Factor values and forward returns must have same length")
        
        period_start = timestamps[0] if timestamps else datetime.utcnow()
        period_end = timestamps[-1] if timestamps else datetime.utcnow()
        
        factor_array = np.array(factor_values)
        returns_array = np.array(forward_returns)
        
        ic = self._compute_ic(factor_array, returns_array)
        rank_ic = self._compute_rank_ic(factor_array, returns_array)
        ir = self._compute_ir(factor_array, returns_array)
        
        sharpe = self._compute_sharpe(returns_array)
        max_drawdown = self._compute_max_drawdown(returns_array)
        
        turnover = self._compute_turnover(factor_array)
        decay = self._compute_decay(factor_array, returns_array)
        
        stability = self._compute_stability(factor_array)
        
        regime_sensitivity = {}
        regime_breakdown = {}
        
        if regimes:
            regime_sensitivity, regime_breakdown = self._compute_regime_analysis(
                factor_array, returns_array, regimes
            )
        
        metrics = EvaluationMetrics(
            ic=ic,
            rank_ic=rank_ic,
            ir=ir,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            turnover=turnover,
            decay=decay,
            stability=stability,
            regime_sensitivity=regime_sensitivity,
            sample_count=len(factor_values),
        )
        
        overall_score = self._compute_overall_score(metrics)
        recommendation = self._generate_recommendation(metrics, overall_score)
        
        ic_series = self._compute_ic_series(factor_array, returns_array)
        
        return EvaluationResult(
            evaluation_id=f"eval_{uuid.uuid4().hex[:12]}",
            factor_id=factor_id,
            timestamp=datetime.utcnow(),
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            ic_series=ic_series,
            returns_series=forward_returns,
            regime_breakdown=regime_breakdown,
            overall_score=overall_score,
            recommendation=recommendation,
        )
    
    def _compute_ic(
        self,
        factor: np.ndarray,
        returns: np.ndarray,
    ) -> float:
        """计算 IC (Information Correlation)"""
        valid_mask = ~(np.isnan(factor) | np.isnan(returns))
        if not valid_mask.any():
            return 0.0
        
        factor_valid = factor[valid_mask]
        returns_valid = returns[valid_mask]
        
        if len(factor_valid) < 2:
            return 0.0
        
        correlation = np.corrcoef(factor_valid, returns_valid)[0, 1]
        return float(correlation) if not np.isnan(correlation) else 0.0
    
    def _compute_rank_ic(
        self,
        factor: np.ndarray,
        returns: np.ndarray,
    ) -> float:
        """计算 Rank IC"""
        valid_mask = ~(np.isnan(factor) | np.isnan(returns))
        if not valid_mask.any():
            return 0.0
        
        factor_valid = factor[valid_mask]
        returns_valid = returns[valid_mask]
        
        if len(factor_valid) < 2:
            return 0.0
        
        try:
            rank_corr, _ = stats.spearmanr(factor_valid, returns_valid)
            return float(rank_corr) if not np.isnan(rank_corr) else 0.0
        except Exception:
            return 0.0
    
    def _compute_ir(
        self,
        factor: np.ndarray,
        returns: np.ndarray,
        rolling_window: int = 20,
    ) -> float:
        """计算 IR (Information Ratio)"""
        ic_series = self._compute_ic_series(factor, returns, rolling_window)
        
        if not ic_series or len(ic_series) < 2:
            return 0.0
        
        ic_mean = np.mean(ic_series)
        ic_std = np.std(ic_series)
        
        if ic_std == 0:
            return 0.0
        
        return float(ic_mean / ic_std)
    
    def _compute_ic_series(
        self,
        factor: np.ndarray,
        returns: np.ndarray,
        rolling_window: int = 20,
    ) -> List[float]:
        """计算 IC 序列"""
        ic_series = []
        
        for i in range(rolling_window, len(factor)):
            window_factor = factor[i-rolling_window:i]
            window_returns = returns[i-rolling_window:i]
            
            ic = self._compute_ic(window_factor, window_returns)
            ic_series.append(ic)
        
        return ic_series
    
    def _compute_sharpe(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.0,
    ) -> float:
        """计算 Sharpe Ratio"""
        valid_mask = ~np.isnan(returns)
        if not valid_mask.any():
            return 0.0
        
        returns_valid = returns[valid_mask]
        
        if len(returns_valid) < 2:
            return 0.0
        
        excess_returns = returns_valid - risk_free_rate
        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns)
        
        if std_return == 0:
            return 0.0
        
        sharpe = mean_return / std_return
        return float(sharpe * np.sqrt(252))
    
    def _compute_max_drawdown(
        self,
        returns: np.ndarray,
    ) -> float:
        """计算最大回撤"""
        valid_mask = ~np.isnan(returns)
        if not valid_mask.any():
            return 0.0
        
        returns_valid = returns[valid_mask]
        
        cumulative = np.cumprod(1 + returns_valid)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        
        max_dd = np.min(drawdowns)
        return float(max_dd)
    
    def _compute_turnover(
        self,
        factor: np.ndarray,
        quantile: int = 10,
    ) -> float:
        """计算换手率"""
        if len(factor) < 2:
            return 0.0
        
        quantiled = np.zeros_like(factor)
        valid_mask = ~np.isnan(factor)
        
        if not valid_mask.any():
            return 0.0
        
        ranks = np.argsort(np.argsort(factor[valid_mask]))
        quantiled[valid_mask] = ranks // (len(ranks) // quantile + 1)
        
        turnovers = []
        for i in range(1, len(quantiled)):
            if not (np.isnan(quantiled[i]) or np.isnan(quantiled[i-1])):
                turnover = np.sum(quantiled[i] != quantiled[i-1]) / quantile
                turnovers.append(turnover)
        
        return float(np.mean(turnovers)) if turnovers else 0.0
    
    def _compute_decay(
        self,
        factor: np.ndarray,
        returns: np.ndarray,
        max_horizon: int = 5,
    ) -> float:
        """计算因子衰减"""
        if len(factor) <= max_horizon:
            return 0.0
        
        ic_by_horizon = []
        
        for h in range(1, max_horizon + 1):
            factor_aligned = factor[:-h]
            returns_aligned = returns[h:]
            
            ic = self._compute_ic(factor_aligned, returns_aligned)
            ic_by_horizon.append(abs(ic))
        
        if not ic_by_horizon:
            return 0.0
        
        decay_rate = (ic_by_horizon[0] - ic_by_horizon[-1]) / ic_by_horizon[0] if ic_by_horizon[0] > 0 else 0
        
        return float(decay_rate)
    
    def _compute_stability(
        self,
        factor: np.ndarray,
    ) -> float:
        """计算因子稳定性 (IC 自相关)"""
        if len(factor) < 10:
            return 0.0
        
        valid_mask = ~np.isnan(factor)
        if not valid_mask.any():
            return 0.0
        
        factor_valid = factor[valid_mask]
        
        if len(factor_valid) < 2:
            return 0.0
        
        try:
            autocorr = np.corrcoef(factor_valid[:-1], factor_valid[1:])[0, 1]
            return float(autocorr) if not np.isnan(autocorr) else 0.0
        except Exception:
            return 0.0
    
    def _compute_regime_analysis(
        self,
        factor: np.ndarray,
        returns: np.ndarray,
        regimes: List[str],
    ) -> Tuple[Dict[str, float], Dict[str, EvaluationMetrics]]:
        """计算市场状态分析"""
        regime_ic = {}
        regime_metrics = {}
        
        for regime_name, classifier in self._regime_classifiers.items():
            regime_mask = np.array([classifier(r) for r in regimes])
            
            if not regime_mask.any():
                continue
            
            regime_factor = factor[regime_mask]
            regime_returns = returns[regime_mask]
            
            if len(regime_factor) < 5:
                continue
            
            ic = self._compute_ic(regime_factor, regime_returns)
            regime_ic[regime_name] = ic
            
            regime_metrics[regime_name] = EvaluationMetrics(
                ic=ic,
                rank_ic=self._compute_rank_ic(regime_factor, regime_returns),
                ir=self._compute_ir(regime_factor, regime_returns),
                sharpe=self._compute_sharpe(regime_returns),
                max_drawdown=self._compute_max_drawdown(regime_returns),
                turnover=0.0,
                decay=0.0,
                stability=0.0,
                sample_count=int(np.sum(regime_mask)),
            )
        
        return regime_ic, regime_metrics
    
    def _compute_overall_score(
        self,
        metrics: EvaluationMetrics,
    ) -> float:
        """计算综合评分"""
        weights = {
            "ic": 0.25,
            "rank_ic": 0.25,
            "ir": 0.20,
            "sharpe": 0.10,
            "turnover": 0.10,
            "decay": 0.05,
            "stability": 0.05,
        }
        
        ic_score = min(abs(metrics.ic) * 10, 1.0)
        rank_ic_score = min(abs(metrics.rank_ic) * 10, 1.0)
        
        ir_score = min(max(metrics.ir, 0), 2.0) / 2.0
        
        sharpe_score = min(max(metrics.sharpe, 0), 3.0) / 3.0
        
        turnover_score = 1.0 - min(metrics.turnover, 1.0)
        
        decay_score = max(1.0 - metrics.decay, 0.0)
        
        stability_score = (metrics.stability + 1.0) / 2.0
        
        score = (
            weights["ic"] * ic_score +
            weights["rank_ic"] * rank_ic_score +
            weights["ir"] * ir_score +
            weights["sharpe"] * sharpe_score +
            weights["turnover"] * turnover_score +
            weights["decay"] * decay_score +
            weights["stability"] * stability_score
        )
        
        return float(score)
    
    def _generate_recommendation(
        self,
        metrics: EvaluationMetrics,
        overall_score: float,
    ) -> str:
        """生成推荐"""
        if overall_score >= 0.8:
            return "Strong Alpha - Consider Production"
        elif overall_score >= 0.6:
            return "Good Potential - Further Validation Needed"
        elif overall_score >= 0.4:
            return "Moderate - Requires Optimization"
        elif overall_score >= 0.2:
            return "Weak Signal - May Need Revisions"
        else:
            return "Poor Performance - Not Recommended"
    
    def compare_factors(
        self,
        results: List[EvaluationResult],
    ) -> List[Tuple[str, float]]:
        """比较因子"""
        sorted_results = sorted(
            [(r.factor_id, r.overall_score) for r in results],
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_results


_evaluator: Optional[FactorEvaluator] = None


def get_factor_evaluator() -> FactorEvaluator:
    """获取因子评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = FactorEvaluator()
    return _evaluator
