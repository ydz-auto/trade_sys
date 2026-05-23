"""
Order Splitting - 订单拆分

智能拆分大额订单:
1. 基于流动性拆分
2. 基于时间拆分
3. 基于价格档位拆分
4. 隐藏真实意图
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("execution.order_splitting")


class SplitStrategy(str, Enum):
    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    RANDOM = "random"
    STEALTH = "stealth"


@dataclass
class OrderSlice:
    slice_id: int
    size: float
    price: float
    
    delay_seconds: float
    
    is_visible: bool
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitResult:
    original_size: float
    original_price: float
    
    slices: List[OrderSlice]
    
    total_slices: int
    visible_slices: int
    
    estimated_total_time_seconds: float
    
    size_variance: float
    stealth_score: float


@dataclass
class OrderSplitter:
    max_slice_size_pct: float = 0.1
    
    min_slices: int = 1
    max_slices: int = 20
    
    stealth_enabled: bool = True
    random_variance: float = 0.2
    
    def split(
        self,
        order_size: float,
        order_price: float,
        orderbook_depth: float,
        avg_trade_size: float,
        strategy: SplitStrategy = SplitStrategy.STEALTH,
    ) -> SplitResult:
        num_slices = self._calculate_num_slices(
            order_size, orderbook_depth, avg_trade_size
        )
        
        sizes = self._calculate_slice_sizes(
            order_size, num_slices, strategy
        )
        
        delays = self._calculate_delays(num_slices, strategy)
        
        prices = self._calculate_slice_prices(
            order_price, num_slices, strategy
        )
        
        slices = []
        for i in range(num_slices):
            is_visible = self._is_slice_visible(i, num_slices, strategy)
            
            slices.append(OrderSlice(
                slice_id=i,
                size=sizes[i],
                price=prices[i],
                delay_seconds=delays[i],
                is_visible=is_visible,
            ))
        
        total_time = max(delays) if delays else 0.0
        
        size_variance = np.var(sizes) / (np.mean(sizes) ** 2) if sizes and np.mean(sizes) > 0 else 0.0
        
        stealth_score = self._calculate_stealth_score(
            num_slices, size_variance, strategy
        )
        
        return SplitResult(
            original_size=order_size,
            original_price=order_price,
            slices=slices,
            total_slices=num_slices,
            visible_slices=sum(1 for s in slices if s.is_visible),
            estimated_total_time_seconds=total_time,
            size_variance=size_variance,
            stealth_score=stealth_score,
        )
    
    def _calculate_num_slices(
        self,
        order_size: float,
        depth: float,
        avg_size: float,
    ) -> int:
        max_single_size = depth * self.max_slice_size_pct
        
        if max_single_size <= 0:
            return self.min_slices
        
        min_needed = int(np.ceil(order_size / max_single_size))
        
        by_avg = int(np.ceil(order_size / (avg_size * 3)))
        
        num_slices = max(min_needed, by_avg, self.min_slices)
        num_slices = min(num_slices, self.max_slices)
        
        return num_slices
    
    def _calculate_slice_sizes(
        self,
        total_size: float,
        num_slices: int,
        strategy: SplitStrategy,
    ) -> List[float]:
        if strategy == SplitStrategy.EQUAL:
            sizes = [total_size / num_slices] * num_slices
        
        elif strategy == SplitStrategy.PROPORTIONAL:
            weights = np.linspace(1, 0.5, num_slices)
            weights = weights / weights.sum()
            sizes = list(total_size * weights)
        
        elif strategy == SplitStrategy.RANDOM:
            base_size = total_size / num_slices
            sizes = []
            remaining = total_size
            
            for i in range(num_slices - 1):
                variance = base_size * self.random_variance
                size = base_size + np.random.uniform(-variance, variance)
                size = max(size, base_size * 0.5)
                size = min(size, remaining * 0.8)
                sizes.append(size)
                remaining -= size
            
            sizes.append(remaining)
        
        else:
            sizes = self._stealth_sizes(total_size, num_slices)
        
        return sizes
    
    def _stealth_sizes(
        self,
        total_size: float,
        num_slices: int,
    ) -> List[float]:
        sizes = []
        remaining = total_size
        
        base_size = total_size / num_slices
        
        for i in range(num_slices - 1):
            noise = np.random.normal(0, base_size * 0.15)
            size = base_size + noise
            
            size = max(size, base_size * 0.3)
            size = min(size, remaining * 0.5)
            
            sizes.append(size)
            remaining -= size
        
        sizes.append(remaining)
        
        return sizes
    
    def _calculate_delays(
        self,
        num_slices: int,
        strategy: SplitStrategy,
    ) -> List[float]:
        if strategy == SplitStrategy.AGGRESSIVE:
            return [0.0] * num_slices
        
        base_interval = 5.0
        
        if strategy == SplitStrategy.STEALTH:
            intervals = []
            for i in range(num_slices):
                noise = np.random.exponential(2.0)
                intervals.append(i * base_interval + noise)
            return intervals
        
        return [i * base_interval for i in range(num_slices)]
    
    def _calculate_slice_prices(
        self,
        base_price: float,
        num_slices: int,
        strategy: SplitStrategy,
    ) -> List[float]:
        if strategy in [SplitStrategy.EQUAL, SplitStrategy.PROPORTIONAL]:
            return [base_price] * num_slices
        
        prices = []
        for i in range(num_slices):
            tick = base_price * 0.0001 * (i % 2 * 2 - 1)
            prices.append(base_price + tick)
        
        return prices
    
    def _is_slice_visible(
        self,
        index: int,
        total: int,
        strategy: SplitStrategy,
    ) -> bool:
        if strategy != SplitStrategy.STEALTH:
            return True
        
        if not self.stealth_enabled:
            return True
        
        return index < total * 0.3
    
    def _calculate_stealth_score(
        self,
        num_slices: int,
        size_variance: float,
        strategy: SplitStrategy,
    ) -> float:
        if strategy != SplitStrategy.STEALTH:
            return 0.0
        
        score = 0.5
        
        if num_slices >= 5:
            score += 0.2
        
        if size_variance > 0.01:
            score += 0.2
        
        if self.stealth_enabled:
            score += 0.1
        
        return min(1.0, score)


def split_order(
    order_size: float,
    order_price: float,
    orderbook_depth: float,
    avg_trade_size: float,
    strategy: SplitStrategy = SplitStrategy.STEALTH,
    splitter: Optional[OrderSplitter] = None,
) -> SplitResult:
    splitter = splitter or OrderSplitter()
    return splitter.split(
        order_size, order_price,
        orderbook_depth, avg_trade_size,
        strategy
    )
