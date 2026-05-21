"""
Partial Fill Model - 部分成交模型

模拟部分成交:
1. 流动性限制
2. 订单大小影响
3. 市场条件影响
4. 多次成交模拟
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("replay.partial_fill")


class FillStatus(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


@dataclass
class FillChunk:
    size: float
    price: float
    timestamp: datetime
    latency_ms: float


@dataclass
class PartialFillResult:
    requested_size: float
    total_filled: float
    unfilled: float
    
    fill_ratio: float
    fill_count: int
    
    avg_fill_price: float
    price_improvement: float
    
    status: FillStatus
    
    fills: List[FillChunk]
    
    total_latency_ms: float


@dataclass
class PartialFillModel:
    min_fill_ratio: float = 0.1
    max_fill_iterations: int = 5
    
    large_order_threshold: float = 0.01
    large_order_penalty: float = 0.3
    
    def simulate(
        self,
        order_size: float,
        order_price: float,
        side: str,
        orderbook_depth: float,
        avg_trade_size: float,
        submission_time: datetime,
        volatility: float = 0.02,
    ) -> PartialFillResult:
        size_ratio = order_size / orderbook_depth if orderbook_depth > 0 else 1.0
        
        if size_ratio < self.large_order_threshold:
            return self._full_fill(
                order_size, order_price, submission_time
            )
        
        fills = []
        remaining = order_size
        total_latency = 0.0
        
        for i in range(self.max_fill_iterations):
            if remaining <= 0:
                break
            
            fill_ratio = self._calculate_fill_ratio(
                remaining, orderbook_depth, avg_trade_size, i
            )
            
            fill_size = remaining * fill_ratio
            fill_size = max(fill_size, remaining * self.min_fill_ratio)
            fill_size = min(fill_size, remaining)
            
            price_slippage = volatility * (i + 1) * 0.001
            if side == "buy":
                fill_price = order_price * (1 + price_slippage)
            else:
                fill_price = order_price * (1 - price_slippage)
            
            latency = 50 + np.random.exponential(20)
            total_latency += latency
            
            fill_time = submission_time + timedelta(milliseconds=total_latency)
            
            fills.append(FillChunk(
                size=fill_size,
                price=fill_price,
                timestamp=fill_time,
                latency_ms=latency,
            ))
            
            remaining -= fill_size
            orderbook_depth *= 0.8
        
        total_filled = sum(f.size for f in fills)
        unfilled = order_size - total_filled
        fill_ratio = total_filled / order_size if order_size > 0 else 0.0
        
        if fill_ratio >= 0.99:
            status = FillStatus.FULL
        elif fill_ratio >= self.min_fill_ratio:
            status = FillStatus.PARTIAL
        else:
            status = FillStatus.NONE
        
        if total_filled > 0:
            avg_price = sum(f.size * f.price for f in fills) / total_filled
            price_improvement = (avg_price - order_price) / order_price
            if side == "sell":
                price_improvement = -price_improvement
        else:
            avg_price = order_price
            price_improvement = 0.0
        
        return PartialFillResult(
            requested_size=order_size,
            total_filled=total_filled,
            unfilled=unfilled,
            fill_ratio=fill_ratio,
            fill_count=len(fills),
            avg_fill_price=avg_price,
            price_improvement=price_improvement,
            status=status,
            fills=fills,
            total_latency_ms=total_latency,
        )
    
    def _calculate_fill_ratio(
        self,
        remaining: float,
        depth: float,
        avg_size: float,
        iteration: int,
    ) -> float:
        base_ratio = 0.5
        
        depth_ratio = min(1.0, depth / (remaining * 10))
        
        size_factor = min(1.0, avg_size / remaining)
        
        iteration_penalty = 0.1 * iteration
        
        fill_ratio = base_ratio * depth_ratio * size_factor - iteration_penalty
        
        return max(0.1, min(0.9, fill_ratio))
    
    def _full_fill(
        self,
        size: float,
        price: float,
        time: datetime,
    ) -> PartialFillResult:
        fill = FillChunk(
            size=size,
            price=price,
            timestamp=time,
            latency_ms=50.0,
        )
        
        return PartialFillResult(
            requested_size=size,
            total_filled=size,
            unfilled=0.0,
            fill_ratio=1.0,
            fill_count=1,
            avg_fill_price=price,
            price_improvement=0.0,
            status=FillStatus.FULL,
            fills=[fill],
            total_latency_ms=50.0,
        )


def simulate_partial_fill(
    order_size: float,
    order_price: float,
    side: str,
    orderbook_depth: float,
    avg_trade_size: float,
    submission_time: datetime,
    volatility: float = 0.02,
    model: Optional[PartialFillModel] = None,
) -> PartialFillResult:
    model = model or PartialFillModel()
    return model.simulate(
        order_size, order_price, side,
        orderbook_depth, avg_trade_size,
        submission_time, volatility
    )
