"""
Funding Model - 资金费率模型

计算资金费率:
1. 历史资金费率
2. 预测资金费率
3. 持仓成本
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np

from domain.logging import get_logger

logger = get_logger("replay.funding")


@dataclass
class FundingResult:
    funding_rate: float
    funding_fee: float
    
    next_funding_time: datetime
    hours_to_funding: float
    
    estimated_next_rate: float
    estimated_next_fee: float
    
    cumulative_cost: float


@dataclass
class FundingModel:
    funding_interval_hours: float = 8.0
    
    max_funding_rate: float = 0.01
    
    rate_decay_factor: float = 0.9
    
    def calculate(
        self,
        position_size: float,
        position_value: float,
        current_funding_rate: float,
        current_time: datetime,
        last_funding_time: datetime,
        position_side: str,
        historical_rates: Optional[List[float]] = None,
    ) -> FundingResult:
        funding_fee = position_value * current_funding_rate
        if position_side == "short":
            funding_fee = -funding_fee
        
        hours_since_funding = (current_time - last_funding_time).total_seconds() / 3600
        hours_to_funding = self.funding_interval_hours - hours_since_funding
        next_funding_time = current_time + timedelta(hours=hours_to_funding)
        
        estimated_next_rate = self._estimate_next_rate(
            current_funding_rate, historical_rates
        )
        estimated_next_fee = position_value * estimated_next_rate
        if position_side == "short":
            estimated_next_fee = -estimated_next_fee
        
        cumulative_cost = funding_fee * (hours_since_funding / self.funding_interval_hours)
        
        return FundingResult(
            funding_rate=current_funding_rate,
            funding_fee=funding_fee,
            next_funding_time=next_funding_time,
            hours_to_funding=hours_to_funding,
            estimated_next_rate=estimated_next_rate,
            estimated_next_fee=estimated_next_fee,
            cumulative_cost=cumulative_cost,
        )
    
    def _estimate_next_rate(
        self,
        current_rate: float,
        historical: Optional[List[float]],
    ) -> float:
        if historical and len(historical) >= 3:
            recent = historical[-5:]
            avg = np.mean(recent)
            trend = recent[-1] - recent[0]
            
            estimated = avg + trend * 0.5
        else:
            estimated = current_rate * self.rate_decay_factor
        
        return np.clip(estimated, -self.max_funding_rate, self.max_funding_rate)
    
    def calculate_holding_cost(
        self,
        position_value: float,
        avg_funding_rate: float,
        holding_hours: float,
        position_side: str,
    ) -> Dict[str, float]:
        funding_periods = holding_hours / self.funding_interval_hours
        
        total_funding_cost = position_value * avg_funding_rate * funding_periods
        
        if position_side == "short":
            total_funding_cost = -total_funding_cost
        
        hourly_cost = total_funding_cost / holding_hours if holding_hours > 0 else 0.0
        daily_cost = hourly_cost * 24
        
        return {
            "total_funding_cost": total_funding_cost,
            "funding_periods": funding_periods,
            "hourly_cost": hourly_cost,
            "daily_cost": daily_cost,
            "cost_pct": abs(total_funding_cost) / position_value if position_value > 0 else 0.0,
        }


def calculate_funding(
    position_size: float,
    position_value: float,
    current_funding_rate: float,
    current_time: datetime,
    last_funding_time: datetime,
    position_side: str,
    historical_rates: Optional[List[float]] = None,
    model: Optional[FundingModel] = None,
) -> FundingResult:
    model = model or FundingModel()
    return model.calculate(
        position_size, position_value,
        current_funding_rate, current_time,
        last_funding_time, position_side,
        historical_rates
    )
