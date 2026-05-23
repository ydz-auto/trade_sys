
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from infrastructure.logging import get_logger
from research.reality_engine.models import (
    SlippageModel,
    LatencyModel,
    FeeModel,
    FundingModel,
    LiquidationImpactModel,
)

logger = get_logger("research.reality_engine")


@dataclass
class ExecutionCostResult:
    entry_price: float
    slippage_amount: float
    slippage_bps: float
    fee_amount: float
    fee_bps: float
    latency_ms: float
    total_entry_cost_bps: float
    total_entry_cost_amount: float
    funding_payment: float = 0.0
    liquidation_impact: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_price": self.entry_price,
            "slippage_amount": self.slippage_amount,
            "slippage_bps": self.slippage_bps,
            "fee_amount": self.fee_amount,
            "fee_bps": self.fee_bps,
            "latency_ms": self.latency_ms,
            "total_entry_cost_bps": self.total_entry_cost_bps,
            "total_entry_cost_amount": self.total_entry_cost_amount,
            "funding_payment": self.funding_payment,
            "liquidation_impact": self.liquidation_impact,
            "details": self.details,
        }


class RealityExecutionLayer:
    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        latency_model: Optional[LatencyModel] = None,
        fee_model: Optional[FeeModel] = None,
        funding_model: Optional[FundingModel] = None,
        liquidation_model: Optional[LiquidationImpactModel] = None,
    ):
        self.slippage_model = slippage_model or SlippageModel()
        self.latency_model = latency_model or LatencyModel()
        self.fee_model = fee_model or FeeModel()
        self.funding_model = funding_model or FundingModel()
        self.liquidation_model = liquidation_model or LiquidationImpactModel()

    def simulate_entry(
        self,
        notional: float,
        mid_price: float,
        is_buy: bool,
        volatility: float = 0.02,
        relative_volume: float = 0.01,
        is_taker: bool = True,
        hours_held: Optional[float] = None,
        leverage: Optional[float] = None,
    ) -> ExecutionCostResult:
        slippage_bps = self.slippage_model.calculate_slippage(
            notional=notional,
            volatility=volatility,
            relative_volume=relative_volume,
        )
        slippage_amount = notional * slippage_bps

        fee_amount = self.fee_model.calculate_fee(
            notional=notional,
            is_taker=is_taker,
        )
        fee_bps = (fee_amount / notional) * 10000.0 if notional > 0 else 0.0

        latency_ms = self.latency_model.sample_latency()

        total_entry_cost_bps = slippage_bps * 10000.0 + fee_bps
        total_entry_cost_amount = slippage_amount + fee_amount

        if is_buy:
            entry_price = mid_price * (1 + slippage_bps)
        else:
            entry_price = mid_price * (1 - slippage_bps)

        funding_payment = 0.0
        liquidation_impact = 0.0

        if hours_held is not None:
            position_size = notional / mid_price
            funding_payment = self.funding_model.calculate_funding_payment(
                position_size=position_size,
                entry_price=entry_price,
                hours_held=hours_held,
            )

        if leverage is not None:
            position_size = notional / mid_price
            liquidation_impact = self.liquidation_model.calculate_liquidation_impact(
                position_size=position_size,
                entry_price=entry_price,
                leverage=leverage,
                volatility=volatility,
            ) * notional

        result = ExecutionCostResult(
            entry_price=entry_price,
            slippage_amount=slippage_amount,
            slippage_bps=slippage_bps * 10000.0,
            fee_amount=fee_amount,
            fee_bps=fee_bps,
            latency_ms=latency_ms,
            total_entry_cost_bps=total_entry_cost_bps,
            total_entry_cost_amount=total_entry_cost_amount,
            funding_payment=funding_payment,
            liquidation_impact=liquidation_impact,
            details={
                "notional": notional,
                "mid_price": mid_price,
                "is_buy": is_buy,
                "volatility": volatility,
                "relative_volume": relative_volume,
                "is_taker": is_taker,
                "hours_held": hours_held,
                "leverage": leverage,
            },
        )

        return result

    def calculate_trade_vs_replay_penalty(
        self,
        replay_pnl: float,
        entry_notional: float,
        volatility: float = 0.02,
        relative_volume: float = 0.01,
        is_taker: bool = True,
        hours_held: float = 24.0,
        leverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        mid_price = 100000.0
        cost_result = self.simulate_entry(
            notional=entry_notional,
            mid_price=mid_price,
            is_buy=True,
            volatility=volatility,
            relative_volume=relative_volume,
            is_taker=is_taker,
            hours_held=hours_held,
            leverage=leverage,
        )

        total_costs = (
            cost_result.total_entry_cost_amount
            + cost_result.funding_payment
            + cost_result.liquidation_impact
        )

        adjusted_pnl = replay_pnl - total_costs

        return {
            "replay_pnl": replay_pnl,
            "total_reality_costs": total_costs,
            "adjusted_pnl": adjusted_pnl,
            "cost_result": cost_result.to_dict(),
        }
