
import random
from dataclasses import dataclass
from typing import Optional

from infrastructure.logging import get_logger

logger = get_logger("research.reality_engine")


@dataclass
class SlippageModel:
    base_bps: float = 1.0
    volatility_multiplier: float = 1.5
    volume_multiplier: float = 0.8
    min_slippage_bps: float = 0.1
    max_slippage_bps: float = 50.0

    def calculate_slippage(
        self,
        notional: float,
        volatility: float = 0.02,
        relative_volume: float = 0.01,
    ) -> float:
        base = self.base_bps
        vol_adj = base * (1 + volatility * self.volatility_multiplier)
        vol_adj = base * (1 + relative_volume * self.volume_multiplier)
        slippage = vol_adj
        slippage = max(slippage, self.min_slippage_bps)
        slippage = min(slippage, self.max_slippage_bps)
        return slippage / 10000.0


@dataclass
class LatencyModel:
    mean_latency_ms: float = 50.0
    std_latency_ms: float = 20.0
    min_latency_ms: float = 10.0
    max_latency_ms: float = 200.0

    def sample_latency(self) -> float:
        latency = random.normalvariate(self.mean_latency_ms, self.std_latency_ms)
        latency = max(latency, self.min_latency_ms)
        latency = min(latency, self.max_latency_ms)
        return latency


@dataclass
class FeeModel:
    maker_fee_bps: float = 0.1
    taker_fee_bps: float = 0.1
    stablecoin_conversion_fee_bps: float = 0.05

    def calculate_fee(
        self,
        notional: float,
        is_taker: bool = True,
    ) -> float:
        fee_bps = self.taker_fee_bps if is_taker else self.maker_fee_bps
        return notional * (fee_bps / 10000.0)


@dataclass
class FundingModel:
    funding_rate: float = 0.0001
    funding_interval_hours: int = 8
    is_contango: bool = True

    def calculate_funding_payment(
        self,
        position_size: float,
        entry_price: float,
        hours_held: float,
    ) -> float:
        if hours_held < 0.01:
            return 0.0
        num_intervals = hours_held / self.funding_interval_hours
        notional = position_size * entry_price
        payment = notional * self.funding_rate * num_intervals
        return payment if self.is_contango else -payment


@dataclass
class LiquidationImpactModel:
    slippage_multiplier: float = 5.0
    impact_scalar: float = 2.0
    max_impact_bps: float = 200.0

    def calculate_liquidation_impact(
        self,
        position_size: float,
        entry_price: float,
        leverage: float,
        volatility: float,
    ) -> float:
        notional = position_size * entry_price
        base_slippage = 0.001 * volatility * self.slippage_multiplier
        impact = base_slippage * self.impact_scalar * min(leverage, 20) / 10
        impact = min(impact, self.max_impact_bps / 10000.0)
        return impact
