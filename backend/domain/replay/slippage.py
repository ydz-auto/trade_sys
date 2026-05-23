"""
Slippage Model - 滑点模型

模拟真实滑点:
1. 市价单滑点
2. 流动性影响
3. 订单大小影响
4. 波动率影响
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("replay.slippage")


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"


@dataclass
class SlippageResult:
    requested_price: float
    execution_price: float
    slippage_bps: float
    slippage_pct: float
    
    market_impact: float
    liquidity_impact: float
    volatility_impact: float
    
    total_impact: float


@dataclass
class SlippageModel:
    base_slippage_bps: float = 1.0
    market_impact_coefficient: float = 0.1
    liquidity_impact_coefficient: float = 0.05
    volatility_impact_coefficient: float = 0.02
    
    max_slippage_bps: float = 50.0
    
    def calculate(
        self,
        order_type: OrderType,
        side: str,
        size: float,
        price: float,
        avg_daily_volume: float,
        current_spread_bps: float,
        volatility: float,
        orderbook_depth: float,
    ) -> SlippageResult:
        if order_type == OrderType.LIMIT:
            return SlippageResult(
                requested_price=price,
                execution_price=price,
                slippage_bps=0.0,
                slippage_pct=0.0,
                market_impact=0.0,
                liquidity_impact=0.0,
                volatility_impact=0.0,
                total_impact=0.0,
            )
        
        market_impact = self._calculate_market_impact(
            size, avg_daily_volume, price
        )
        
        liquidity_impact = self._calculate_liquidity_impact(
            size, orderbook_depth, current_spread_bps
        )
        
        volatility_impact = self._calculate_volatility_impact(volatility)
        
        total_impact = (
            self.base_slippage_bps +
            market_impact * self.market_impact_coefficient +
            liquidity_impact * self.liquidity_impact_coefficient +
            volatility_impact * self.volatility_impact_coefficient
        )
        
        total_impact = min(total_impact, self.max_slippage_bps)
        
        if side == "buy":
            execution_price = price * (1 + total_impact / 10000)
        else:
            execution_price = price * (1 - total_impact / 10000)
        
        slippage_pct = total_impact / 10000
        
        return SlippageResult(
            requested_price=price,
            execution_price=execution_price,
            slippage_bps=total_impact,
            slippage_pct=slippage_pct,
            market_impact=market_impact,
            liquidity_impact=liquidity_impact,
            volatility_impact=volatility_impact,
            total_impact=total_impact,
        )
    
    def _calculate_market_impact(
        self,
        size: float,
        avg_volume: float,
        price: float,
    ) -> float:
        if avg_volume <= 0:
            return 0.0
        
        participation_rate = size / avg_volume
        
        impact = participation_rate ** 0.5 * 100
        
        return impact
    
    def _calculate_liquidity_impact(
        self,
        size: float,
        depth: float,
        spread_bps: float,
    ) -> float:
        if depth <= 0:
            return spread_bps * 2
        
        size_ratio = size / depth
        
        impact = spread_bps * (1 + size_ratio)
        
        return impact
    
    def _calculate_volatility_impact(self, volatility: float) -> float:
        impact = volatility * 10000 * 0.5
        
        return impact


def calculate_slippage(
    order_type: OrderType,
    side: str,
    size: float,
    price: float,
    avg_daily_volume: float,
    current_spread_bps: float,
    volatility: float,
    orderbook_depth: float,
    model: Optional[SlippageModel] = None,
) -> SlippageResult:
    model = model or SlippageModel()
    return model.calculate(
        order_type, side, size, price,
        avg_daily_volume, current_spread_bps,
        volatility, orderbook_depth
    )
