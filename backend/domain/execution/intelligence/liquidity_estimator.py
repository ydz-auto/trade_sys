"""
Liquidity Estimator - 流动性估计器

估计市场当前的流动性状况，这是执行智能的核心。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import numpy as np


class LiquidityRating(str, Enum):
    """流动性评级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class LiquidityEstimate:
    """流动性估计"""
    rating: LiquidityRating
    available_depth: float  # 可用深度
    bid_ask_spread_bps: float
    slippage_estimate_1pct: float  # 1%成交量的滑点
    market_impact_estimate: float
    volatility_ratio: float  # 波动率/成交量比率
    timestamp: float


class LiquidityEstimator:
    """流动性估计器"""
    
    def __init__(self):
        self.spread_history: List[float] = []
        self.depth_history: List[float] = []
        self.volume_history: List[float] = []
        
        self.rating_thresholds = {
            LiquidityRating.EXCELLENT: {"spread": 5, "depth_ratio": 10.0},
            LiquidityRating.GOOD: {"spread": 15, "depth_ratio": 5.0},
            LiquidityRating.MODERATE: {"spread": 30, "depth_ratio": 2.0},
            LiquidityRating.POOR: {"spread": 50, "depth_ratio": 1.0},
        }
    
    def estimate(
        self,
        bid_price: float,
        ask_price: float,
        bid_depth: float,
        ask_depth: float,
        recent_volume: float,
        volatility: float,
    ) -> LiquidityEstimate:
        """估计流动性"""
        mid_price = (bid_price + ask_price) / 2
        
        # 计算点差
        spread_bps = ((ask_price - bid_price) / mid_price) * 10000 if mid_price > 0 else 0
        
        # 总深度
        total_depth = bid_depth + ask_depth
        
        # 波动率/成交量比率
        if recent_volume > 0:
            volatility_ratio = volatility / (np.sqrt(recent_volume) + 1e-10)
        else:
            volatility_ratio = 1.0
        
        # 记录历史
        self.spread_history.append(spread_bps)
        self.depth_history.append(total_depth)
        self.volume_history.append(recent_volume)
        
        if len(self.spread_history) > 100:
            self.spread_history = self.spread_history[-100:]
            self.depth_history = self.depth_history[-100:]
            self.volume_history = self.volume_history[-100:]
        
        # 评分
        avg_spread = np.mean(self.spread_history) if self.spread_history else spread_bps
        avg_depth = np.mean(self.depth_history) if self.depth_history else total_depth
        
        depth_ratio = avg_depth / (recent_volume / 24 + 1) if recent_volume > 0 else 0
        
        # 评级
        if avg_spread <= self.rating_thresholds[LiquidityRating.EXCELLENT]["spread"] and depth_ratio >= self.rating_thresholds[LiquidityRating.EXCELLENT]["depth_ratio"]:
            rating = LiquidityRating.EXCELLENT
        elif avg_spread <= self.rating_thresholds[LiquidityRating.GOOD]["spread"] and depth_ratio >= self.rating_thresholds[LiquidityRating.GOOD]["depth_ratio"]:
            rating = LiquidityRating.GOOD
        elif avg_spread <= self.rating_thresholds[LiquidityRating.MODERATE]["spread"] and depth_ratio >= self.rating_thresholds[LiquidityRating.MODERATE]["depth_ratio"]:
            rating = LiquidityRating.MODERATE
        elif avg_spread <= self.rating_thresholds[LiquidityRating.POOR]["spread"] and depth_ratio >= self.rating_thresholds[LiquidityRating.POOR]["depth_ratio"]:
            rating = LiquidityRating.POOR
        else:
            rating = LiquidityRating.CRITICAL
        
        # 估算1%成交量的滑点
        if recent_volume > 0:
            slippage_1pct = spread_bps * 2 + volatility * 50
        else:
            slippage_1pct = spread_bps * 5
        
        # 市场冲击估计
        market_impact = spread_bps * 3 + volatility * 30
        
        return LiquidityEstimate(
            rating=rating,
            available_depth=total_depth,
            bid_ask_spread_bps=spread_bps,
            slippage_estimate_1pct=slippage_1pct,
            market_impact_estimate=market_impact,
            volatility_ratio=volatility_ratio,
            timestamp=0.0,
        )
    
    def is_liquid_enough(
        self,
        order_size: float,
        estimate: LiquidityEstimate,
        max_slippage_bps: float = 20.0,
    ) -> bool:
        """检查流动性是否足够"""
        # 相对于可用深度的订单规模
        depth_ratio = order_size / (estimate.available_depth + 1)
        
        # 估算预期滑点
        expected_slippage = estimate.bid_ask_spread_bps * (1 + depth_ratio * 2)
        
        return expected_slippage <= max_slippage_bps
    
    def get_execution_recommendation(
        self,
        estimate: LiquidityEstimate,
    ) -> Dict[str, Any]:
        """获取执行建议"""
        if estimate.rating == LiquidityRating.EXCELLENT:
            return {
                "recommendation": "aggressive",
                "slippage_tolerance": 10,
                "order_type": "market",
                "reason": "Excellent liquidity, can execute aggressively",
            }
        elif estimate.rating == LiquidityRating.GOOD:
            return {
                "recommendation": "normal",
                "slippage_tolerance": 20,
                "order_type": "limit_mid",
                "reason": "Good liquidity, normal execution",
            }
        elif estimate.rating == LiquidityRating.MODERATE:
            return {
                "recommendation": "careful",
                "slippage_tolerance": 40,
                "order_type": "limit_passive",
                "reason": "Moderate liquidity, should be careful",
            }
        elif estimate.rating == LiquidityRating.POOR:
            return {
                "recommendation": "passive",
                "slippage_tolerance": 80,
                "order_type": "limit_deep",
                "reason": "Poor liquidity, should be passive",
            }
        else:
            return {
                "recommendation": "avoid",
                "slippage_tolerance": 150,
                "order_type": "no_trade",
                "reason": "Critical liquidity, avoid trading",
            }
