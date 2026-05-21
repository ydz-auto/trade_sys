"""
Execution Optimizer - 执行优化器

整合滑点预测、市场冲击、流动性估计，给出最优执行策略。
这是执行智能的核心。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import numpy as np

from domain.execution.intelligence.slippage_predictor import SlippagePredictor, SlippagePrediction
from domain.execution.intelligence.impact_model import ImpactModel, ImpactResult
from domain.execution.intelligence.liquidity_estimator import LiquidityEstimator, LiquidityEstimate, LiquidityRating


class ExecutionStrategyType(str, Enum):
    """执行策略类型"""
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    CAREFUL = "careful"
    PASSIVE = "passive"
    TWAP = "twap"
    VWAP = "vwap"


@dataclass
class ExecutionPlan:
    """执行计划"""
    strategy: ExecutionStrategyType
    order_type: str
    num_slices: int
    time_window_seconds: float
    price_offset_bps: float
    max_slippage_bps: float
    expected_slippage_bps: float
    expected_impact_bps: float
    total_cost_bps: float
    confidence: float
    rationale: str
    slices: Optional[List[Dict[str, Any]]] = None


class ExecutionOptimizer:
    """执行优化器"""
    
    def __init__(self):
        self.slippage_predictor = SlippagePredictor()
        self.impact_model = ImpactModel()
        self.liquidity_estimator = LiquidityEstimator()
    
    def optimize(
        self,
        order_size: float,
        current_price: float,
        side: str,
        bid_price: float,
        ask_price: float,
        bid_depth: float,
        ask_depth: float,
        spread_bps: float,
        volatility: float,
        recent_volume: float,
        avg_daily_volume: float,
        avg_trade_size: float,
        time_constraint_seconds: Optional[float] = None,
        max_slippage_limit: Optional[float] = None,
    ) -> ExecutionPlan:
        """优化执行策略"""
        liquidity = self.liquidity_estimator.estimate(
            bid_price, ask_price, bid_depth, ask_depth, recent_volume, volatility
        )
        
        slippage = self.slippage_predictor.predict(
            order_size, current_price, spread_bps, volatility,
            bid_depth + ask_depth, avg_trade_size, is_maker=False
        )
        
        impact = self.impact_model.calculate_impact(
            order_size, current_price, bid_depth + ask_depth, volatility, avg_daily_volume
        )
        
        strategy, rationale = self._select_strategy(
            liquidity, slippage, impact, time_constraint_seconds, max_slippage_limit
        )
        
        plan = self._generate_plan(
            strategy, order_size, current_price, side, liquidity, slippage, impact,
            time_constraint_seconds, max_slippage_limit
        )
        
        return plan
    
    def _select_strategy(
        self,
        liquidity: LiquidityEstimate,
        slippage: SlippagePrediction,
        impact: ImpactResult,
        time_constraint: Optional[float],
        max_slippage: Optional[float],
    ) -> tuple[ExecutionStrategyType, str]:
        """选择执行策略"""
        if liquidity.rating == LiquidityRating.CRITICAL:
            return ExecutionStrategyType.PASSIVE, "Critical liquidity, must be passive"
        
        if max_slippage and slippage.expected_slippage_bps > max_slippage:
            return ExecutionStrategyType.PASSIVE, f"Expected slippage {slippage.expected_slippage_bps:.1f}bps exceeds limit {max_slippage}bps"
        
        if time_constraint and time_constraint < 60:
            return ExecutionStrategyType.AGGRESSIVE, f"Time constraint {time_constraint}s requires aggressive execution"
        
        if liquidity.rating == LiquidityRating.EXCELLENT and impact.total_impact_bps < 10:
            return ExecutionStrategyType.AGGRESSIVE, "Excellent liquidity and low impact"
        
        if liquidity.rating == LiquidityRating.GOOD and impact.total_impact_bps < 20:
            return ExecutionStrategyType.NORMAL, "Good liquidity and moderate impact"
        
        if liquidity.rating == LiquidityRating.MODERATE:
            return ExecutionStrategyType.CAREFUL, "Moderate liquidity, need careful execution"
        
        if liquidity.rating == LiquidityRating.POOR:
            return ExecutionStrategyType.PASSIVE, "Poor liquidity, should be passive"
        
        if impact.total_impact_bps > 50:
            return ExecutionStrategyType.TWAP, f"High impact {impact.total_impact_bps:.1f}bps, use TWAP"
        
        return ExecutionStrategyType.NORMAL, "Default to normal execution"
    
    def _generate_plan(
        self,
        strategy: ExecutionStrategyType,
        order_size: float,
        current_price: float,
        side: str,
        liquidity: LiquidityEstimate,
        slippage: SlippagePrediction,
        impact: ImpactResult,
        time_constraint: Optional[float],
        max_slippage: Optional[float],
    ) -> ExecutionPlan:
        """生成执行计划"""
        if strategy == ExecutionStrategyType.AGGRESSIVE:
            return ExecutionPlan(
                strategy=ExecutionStrategyType.AGGRESSIVE,
                order_type="market",
                num_slices=1,
                time_window_seconds=0.0,
                price_offset_bps=0.0,
                max_slippage_bps=max_slippage or slippage.worst_case_bps,
                expected_slippage_bps=slippage.expected_slippage_bps,
                expected_impact_bps=impact.total_impact_bps,
                total_cost_bps=slippage.expected_slippage_bps + impact.total_impact_bps,
                confidence=slippage.confidence,
                rationale=f"Aggressive execution - liquidity: {liquidity.rating.value}, impact: {impact.total_impact_bps:.1f}bps",
            )
        
        if strategy == ExecutionStrategyType.NORMAL:
            num_slices = min(5, max(1, int(order_size / (liquidity.available_depth / 10 + 1))))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.NORMAL,
                order_type="limit",
                num_slices=num_slices,
                time_window_seconds=60 * num_slices,
                price_offset_bps=0.0,
                max_slippage_bps=max_slippage or slippage.worst_case_bps,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.6,
                expected_impact_bps=impact.total_impact_bps * 0.4,
                total_cost_bps=slippage.expected_slippage_bps * 0.6 + impact.total_impact_bps * 0.4,
                confidence=slippage.confidence * 0.9,
                rationale=f"Normal execution with {num_slices} slices",
            )
        
        if strategy == ExecutionStrategyType.CAREFUL:
            num_slices = min(10, max(2, int(order_size / (liquidity.available_depth / 20 + 1))))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.CAREFUL,
                order_type="limit_passive",
                num_slices=num_slices,
                time_window_seconds=120 * num_slices,
                price_offset_bps=liquidity.bid_ask_spread_bps * 0.5,
                max_slippage_bps=max_slippage or slippage.expected_slippage_bps * 0.8,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.4,
                expected_impact_bps=impact.total_impact_bps * 0.3,
                total_cost_bps=slippage.expected_slippage_bps * 0.4 + impact.total_impact_bps * 0.3,
                confidence=slippage.confidence * 0.8,
                rationale=f"Careful execution with {num_slices} slices over {120 * num_slices}s",
            )
        
        if strategy == ExecutionStrategyType.PASSIVE:
            num_slices = min(20, max(3, int(order_size / (liquidity.available_depth / 50 + 1))))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.PASSIVE,
                order_type="limit_deep",
                num_slices=num_slices,
                time_window_seconds=300 * num_slices,
                price_offset_bps=liquidity.bid_ask_spread_bps * 1.5,
                max_slippage_bps=max_slippage or slippage.expected_slippage_bps * 0.5,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.2,
                expected_impact_bps=impact.total_impact_bps * 0.1,
                total_cost_bps=slippage.expected_slippage_bps * 0.2 + impact.total_impact_bps * 0.1,
                confidence=slippage.confidence * 0.7,
                rationale=f"Passive execution with {num_slices} slices over {300 * num_slices}s",
            )
        
        if strategy == ExecutionStrategyType.TWAP:
            time_window = time_constraint or 3600
            num_slices = min(30, max(5, int(time_window / 60)))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.TWAP,
                order_type="twap_limit",
                num_slices=num_slices,
                time_window_seconds=time_window,
                price_offset_bps=0.0,
                max_slippage_bps=max_slippage or slippage.expected_slippage_bps,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.7,
                expected_impact_bps=impact.total_impact_bps * 0.5,
                total_cost_bps=slippage.expected_slippage_bps * 0.7 + impact.total_impact_bps * 0.5,
                confidence=slippage.confidence * 0.85,
                rationale=f"TWAP over {time_window}s with {num_slices} slices",
            )
        
        # 默认策略
        return ExecutionPlan(
            strategy=ExecutionStrategyType.NORMAL,
            order_type="limit",
            num_slices=3,
            time_window_seconds=180.0,
            price_offset_bps=0.0,
            max_slippage_bps=max_slippage or slippage.worst_case_bps,
            expected_slippage_bps=slippage.expected_slippage_bps * 0.6,
            expected_impact_bps=impact.total_impact_bps * 0.4,
            total_cost_bps=slippage.expected_slippage_bps * 0.6 + impact.total_impact_bps * 0.4,
            confidence=slippage.confidence * 0.9,
            rationale="Default normal execution",
        )
