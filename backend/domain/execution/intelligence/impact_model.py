"""
Impact Model - 市场冲击模型

评估订单对市场的冲击，这是执行智能的核心。
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class ImpactResult:
    """冲击结果"""
    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    price_impact: float
    recovery_time_seconds: float


class ImpactModel:
    """市场冲击模型"""
    
    def __init__(self):
        self.temporary_coef = 0.3  # 临时冲击系数
        self.permanent_coef = 0.1  # 永久冲击系数
        self.recovery_rate = 0.1  # 恢复速率
    
    def calculate_impact(
        self,
        order_size: float,
        current_price: float,
        orderbook_depth: float,
        volatility: float,
        avg_daily_volume: float,
    ) -> ImpactResult:
        """计算市场冲击"""
        if orderbook_depth <= 0 or avg_daily_volume <= 0:
            return ImpactResult(
                temporary_impact_bps=0.0,
                permanent_impact_bps=0.0,
                total_impact_bps=0.0,
                price_impact=0.0,
                recovery_time_seconds=0.0,
            )
        
        # 订单规模相对于深度
        depth_ratio = order_size / orderbook_depth
        
        # 订单规模相对于成交量
        volume_ratio = order_size / (avg_daily_volume / 24)  # 按小时算
        
        # 临时冲击（订单簿消耗）
        temporary_impact = depth_ratio * self.temporary_coef * 100  # bps
        
        # 永久冲击（信息泄露）
        permanent_impact = volume_ratio * self.permanent_coef * 100  # bps
        
        # 波动率调整
        volatility_factor = 1 + volatility * 2
        
        temporary_impact *= volatility_factor
        permanent_impact *= volatility_factor
        
        total_impact = temporary_impact + permanent_impact
        
        # 价格冲击
        price_impact = current_price * (total_impact / 10000)
        
        # 恢复时间
        recovery_time = 60 * (1 + depth_ratio * 10)  # 基础60秒，按深度比例增加
        
        return ImpactResult(
            temporary_impact_bps=temporary_impact,
            permanent_impact_bps=permanent_impact,
            total_impact_bps=total_impact,
            price_impact=price_impact,
            recovery_time_seconds=recovery_time,
        )
    
    def estimate_optimal_size(
        self,
        desired_size: float,
        max_impact_bps: float,
        current_price: float,
        orderbook_depth: float,
        volatility: float,
        avg_daily_volume: float,
    ) -> float:
        """估算在给定冲击限制下的最优订单规模"""
        if max_impact_bps <= 0:
            return 0.0
        
        low = 0.0
        high = desired_size * 2
        optimal = 0.0
        
        for _ in range(20):
            mid = (low + high) / 2
            impact = self.calculate_impact(mid, current_price, orderbook_depth, volatility, avg_daily_volume)
            
            if impact.total_impact_bps <= max_impact_bps:
                optimal = mid
                low = mid
            else:
                high = mid
        
        return min(optimal, desired_size)
