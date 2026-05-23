"""
Smart Execution - 智能执行

根据市场条件选择最优执行策略:
1. TWAP - 时间加权平均价格
2. VWAP - 成交量加权平均价格
3. Aggressive - 激进执行
4. Passive - 被动执行
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("execution.smart_execution")


class ExecutionStrategy(str, Enum):
    TWAP = "twap"
    VWAP = "vwap"
    AGGRESSIVE = "aggressive"
    PASSIVE = "passive"
    ADAPTIVE = "adaptive"


@dataclass
class ExecutionPlan:
    strategy: ExecutionStrategy
    total_size: float
    
    slices: List[Dict[str, Any]]
    
    estimated_duration_seconds: float
    estimated_avg_price: float
    estimated_slippage_bps: float
    
    urgency_score: float


@dataclass
class SmartExecution:
    default_strategy: ExecutionStrategy = ExecutionStrategy.ADAPTIVE
    
    twap_interval_seconds: float = 30.0
    max_slices: int = 10
    
    urgency_threshold_high: float = 0.7
    urgency_threshold_low: float = 0.3
    
    def plan(
        self,
        order_size: float,
        order_side: str,
        current_price: float,
        urgency: float,
        market_data: Dict[str, Any],
        time_limit_seconds: Optional[float] = None,
    ) -> ExecutionPlan:
        strategy = self._select_strategy(urgency, market_data)
        
        slices = self._generate_slices(
            order_size, order_side, current_price,
            strategy, urgency, market_data, time_limit_seconds
        )
        
        estimated_duration = self._estimate_duration(slices, strategy)
        estimated_price = self._estimate_avg_price(slices, current_price)
        estimated_slippage = self._estimate_slippage(slices, market_data)
        
        return ExecutionPlan(
            strategy=strategy,
            total_size=order_size,
            slices=slices,
            estimated_duration_seconds=estimated_duration,
            estimated_avg_price=estimated_price,
            estimated_slippage_bps=estimated_slippage,
            urgency_score=urgency,
        )
    
    def _select_strategy(
        self,
        urgency: float,
        market_data: Dict[str, Any],
    ) -> ExecutionStrategy:
        volatility = market_data.get("volatility", 0.02)
        spread = market_data.get("spread_bps", 10)
        
        if urgency > self.urgency_threshold_high:
            return ExecutionStrategy.AGGRESSIVE
        
        if urgency < self.urgency_threshold_low:
            return ExecutionStrategy.PASSIVE
        
        if spread > 20:
            return ExecutionStrategy.VWAP
        
        if volatility > 0.05:
            return ExecutionStrategy.TWAP
        
        return ExecutionStrategy.ADAPTIVE
    
    def _generate_slices(
        self,
        total_size: float,
        side: str,
        price: float,
        strategy: ExecutionStrategy,
        urgency: float,
        market_data: Dict[str, Any],
        time_limit: Optional[float],
    ) -> List[Dict[str, Any]]:
        if strategy == ExecutionStrategy.AGGRESSIVE:
            return self._aggressive_slices(total_size, side, price)
        
        elif strategy == ExecutionStrategy.PASSIVE:
            return self._passive_slices(total_size, side, price, market_data)
        
        elif strategy == ExecutionStrategy.TWAP:
            return self._twap_slices(total_size, side, price, time_limit)
        
        elif strategy == ExecutionStrategy.VWAP:
            return self._vwap_slices(total_size, side, price, market_data)
        
        else:
            return self._adaptive_slices(total_size, side, price, urgency, market_data)
    
    def _aggressive_slices(
        self,
        size: float,
        side: str,
        price: float,
    ) -> List[Dict[str, Any]]:
        return [{
            "size": size,
            "price": price,
            "type": "market",
            "delay_seconds": 0,
        }]
    
    def _passive_slices(
        self,
        size: float,
        side: str,
        price: float,
        market_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        spread = market_data.get("spread_bps", 10) / 10000
        
        if side == "buy":
            limit_price = price * (1 - spread * 0.5)
        else:
            limit_price = price * (1 + spread * 0.5)
        
        slices = []
        slice_size = size / self.max_slices
        
        for i in range(self.max_slices):
            slices.append({
                "size": slice_size,
                "price": limit_price,
                "type": "limit",
                "delay_seconds": i * 60,
            })
        
        return slices
    
    def _twap_slices(
        self,
        size: float,
        side: str,
        price: float,
        time_limit: Optional[float],
    ) -> List[Dict[str, Any]]:
        duration = time_limit or self.twap_interval_seconds * self.max_slices
        
        num_slices = min(self.max_slices, int(duration / self.twap_interval_seconds))
        num_slices = max(1, num_slices)
        
        slice_size = size / num_slices
        
        slices = []
        for i in range(num_slices):
            slices.append({
                "size": slice_size,
                "price": price,
                "type": "limit",
                "delay_seconds": i * (duration / num_slices),
            })
        
        return slices
    
    def _vwap_slices(
        self,
        size: float,
        side: str,
        price: float,
        market_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        volume_profile = market_data.get("volume_profile", [1.0] * 10)
        total_vol = sum(volume_profile)
        
        slices = []
        remaining = size
        
        for i, vol_weight in enumerate(volume_profile):
            slice_size = size * (vol_weight / total_vol)
            slice_size = min(slice_size, remaining)
            remaining -= slice_size
            
            if slice_size > 0:
                slices.append({
                    "size": slice_size,
                    "price": price,
                    "type": "limit",
                    "delay_seconds": i * self.twap_interval_seconds,
                })
        
        return slices
    
    def _adaptive_slices(
        self,
        size: float,
        side: str,
        price: float,
        urgency: float,
        market_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        num_slices = int(1 + (1 - urgency) * (self.max_slices - 1))
        num_slices = max(1, min(self.max_slices, num_slices))
        
        slice_size = size / num_slices
        
        slices = []
        for i in range(num_slices):
            slices.append({
                "size": slice_size,
                "price": price,
                "type": "limit" if urgency < 0.5 else "market",
                "delay_seconds": i * self.twap_interval_seconds * (1 - urgency),
            })
        
        return slices
    
    def _estimate_duration(
        self,
        slices: List[Dict[str, Any]],
        strategy: ExecutionStrategy,
    ) -> float:
        if not slices:
            return 0.0
        
        return max(s["delay_seconds"] for s in slices)
    
    def _estimate_avg_price(
        self,
        slices: List[Dict[str, Any]],
        base_price: float,
    ) -> float:
        if not slices:
            return base_price
        
        total_size = sum(s["size"] for s in slices)
        weighted_price = sum(s["size"] * s["price"] for s in slices)
        
        return weighted_price / total_size if total_size > 0 else base_price
    
    def _estimate_slippage(
        self,
        slices: List[Dict[str, Any]],
        market_data: Dict[str, Any],
    ) -> float:
        base_slippage = market_data.get("spread_bps", 10) / 2
        
        market_slices = sum(1 for s in slices if s["type"] == "market")
        total_slices = len(slices)
        
        if total_slices > 0:
            market_ratio = market_slices / total_slices
        else:
            market_ratio = 0.0
        
        return base_slippage * (1 + market_ratio)


def execute_smart(
    order_size: float,
    order_side: str,
    current_price: float,
    urgency: float,
    market_data: Dict[str, Any],
    time_limit_seconds: Optional[float] = None,
    executor: Optional[SmartExecution] = None,
) -> ExecutionPlan:
    executor = executor or SmartExecution()
    return executor.plan(
        order_size, order_side, current_price,
        urgency, market_data, time_limit_seconds
    )
