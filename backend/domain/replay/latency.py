"""
Latency Model - 延迟模型

模拟交易延迟:
1. 网络延迟
2. 交易所处理延迟
3. 策略计算延迟
4. 随机抖动
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("replay.latency")


class LatencyType(str, Enum):
    NETWORK = "network"
    EXCHANGE = "exchange"
    STRATEGY = "strategy"
    TOTAL = "total"


@dataclass
class LatencyResult:
    network_latency_ms: float
    exchange_latency_ms: float
    strategy_latency_ms: float
    
    total_latency_ms: float
    total_latency_seconds: float
    
    jitter_ms: float
    
    execution_timestamp: datetime
    submission_timestamp: datetime
    
    price_drift_estimate: float


@dataclass
class LatencyModel:
    base_network_latency_ms: float = 50.0
    base_exchange_latency_ms: float = 10.0
    base_strategy_latency_ms: float = 5.0
    
    network_jitter_ms: float = 20.0
    exchange_jitter_ms: float = 5.0
    
    high_load_multiplier: float = 2.0
    
    def simulate(
        self,
        submission_time: datetime,
        current_volatility: float = 0.02,
        market_stress: float = 0.0,
        is_high_frequency: bool = False,
    ) -> LatencyResult:
        network_latency = self._simulate_network_latency(
            current_volatility, market_stress
        )
        
        exchange_latency = self._simulate_exchange_latency(
            market_stress, is_high_frequency
        )
        
        strategy_latency = self.base_strategy_latency_ms
        
        jitter = np.random.normal(0, self.network_jitter_ms * 0.5)
        jitter = abs(jitter)
        
        total_latency = network_latency + exchange_latency + strategy_latency + jitter
        
        total_seconds = total_latency / 1000.0
        execution_time = submission_time + timedelta(milliseconds=total_latency)
        
        price_drift = current_volatility * np.sqrt(total_seconds / 86400)
        
        return LatencyResult(
            network_latency_ms=network_latency,
            exchange_latency_ms=exchange_latency,
            strategy_latency_ms=strategy_latency,
            total_latency_ms=total_latency,
            total_latency_seconds=total_seconds,
            jitter_ms=jitter,
            execution_timestamp=execution_time,
            submission_timestamp=submission_time,
            price_drift_estimate=price_drift,
        )
    
    def _simulate_network_latency(
        self,
        volatility: float,
        stress: float,
    ) -> float:
        base = self.base_network_latency_ms
        
        volatility_factor = 1 + volatility * 2
        stress_factor = 1 + stress
        
        jitter = np.random.normal(0, self.network_jitter_ms)
        
        latency = base * volatility_factor * stress_factor + jitter
        
        return max(10.0, latency)
    
    def _simulate_exchange_latency(
        self,
        stress: float,
        is_hft: bool,
    ) -> float:
        base = self.base_exchange_latency_ms
        
        if is_hft:
            base *= 0.5
        
        stress_factor = 1 + stress * 2
        
        jitter = np.random.exponential(self.exchange_jitter_ms)
        
        latency = base * stress_factor + jitter
        
        return max(5.0, latency)


def simulate_latency(
    submission_time: datetime,
    current_volatility: float = 0.02,
    market_stress: float = 0.0,
    is_high_frequency: bool = False,
    model: Optional[LatencyModel] = None,
) -> LatencyResult:
    model = model or LatencyModel()
    return model.simulate(
        submission_time, current_volatility,
        market_stress, is_high_frequency
    )
