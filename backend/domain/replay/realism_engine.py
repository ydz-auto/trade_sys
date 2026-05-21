"""
Replay Realism Engine - 回测真实性引擎

整合所有真实性模型:
1. Slippage
2. Latency
3. Partial Fill
4. Fees
5. Funding
6. Liquidation
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .slippage import SlippageModel, SlippageResult
from .latency import LatencyModel, LatencyResult
from .partial_fill import PartialFillModel, PartialFillResult
from .fee_model import FeeModel, FeeResult
from .funding import FundingModel, FundingResult
from .liquidation import LiquidationModel, LiquidationResult

from infrastructure.logging import get_logger

logger = get_logger("replay.realism_engine")


@dataclass
class RealisticExecution:
    timestamp: datetime
    
    requested_size: float
    requested_price: float
    
    actual_size: float
    actual_price: float
    
    slippage: SlippageResult
    latency: LatencyResult
    fill: PartialFillResult
    fees: FeeResult
    
    total_cost: float
    net_execution_price: float
    
    is_liquidated: bool
    liquidation: Optional[LiquidationResult]


class ReplayRealismEngine:
    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        latency_model: Optional[LatencyModel] = None,
        fill_model: Optional[PartialFillModel] = None,
        fee_model: Optional[FeeModel] = None,
        funding_model: Optional[FundingModel] = None,
        liquidation_model: Optional[LiquidationModel] = None,
    ):
        self.slippage = slippage_model or SlippageModel()
        self.latency = latency_model or LatencyModel()
        self.fill = fill_model or PartialFillModel()
        self.fees = fee_model or FeeModel()
        self.funding = funding_model or FundingModel()
        self.liquidation = liquidation_model or LiquidationModel()
        
        self._funding_history: Dict[str, List[float]] = {}
        
        logger.info("ReplayRealismEngine initialized")
    
    def execute(
        self,
        order_size: float,
        order_price: float,
        side: str,
        is_maker: bool,
        leverage: float,
        account_balance: float,
        position_size: float,
        position_value: float,
        position_side: str,
        market_data: Dict[str, Any],
        submission_time: datetime,
    ) -> RealisticExecution:
        slippage = self.slippage.calculate(
            order_type="market",
            side=side,
            size=order_size,
            price=order_price,
            avg_daily_volume=market_data.get("avg_volume", 1000000),
            current_spread_bps=market_data.get("spread_bps", 10),
            volatility=market_data.get("volatility", 0.02),
            orderbook_depth=market_data.get("depth", 100000),
        )
        
        latency = self.latency.simulate(
            submission_time,
            current_volatility=market_data.get("volatility", 0.02),
            market_stress=market_data.get("stress", 0.0),
        )
        
        fill = self.fill.simulate(
            order_size,
            slippage.execution_price,
            side,
            market_data.get("depth", 100000),
            market_data.get("avg_trade_size", 1000),
            latency.execution_timestamp,
            market_data.get("volatility", 0.02),
        )
        
        fees = self.fees.calculate(
            fill.total_filled,
            fill.avg_fill_price,
            side,
            is_maker,
            position_size,
            market_data.get("funding_rate", 0.0),
            market_data.get("holding_hours", 0.0),
        )
        
        liq_check = self.liquidation.check(
            position_size + (fill.total_filled if side == "buy" else -fill.total_filled),
            fill.avg_fill_price,
            market_data.get("current_price", order_price),
            leverage,
            account_balance - fees.total_fee,
            position_side,
        )
        
        total_cost = fees.total_fee + abs(slippage.slippage_pct) * fill.total_filled * fill.avg_fill_price
        
        if fill.total_filled > 0:
            net_price = fill.avg_fill_price + (total_cost / fill.total_filled if side == "buy" else -total_cost / fill.total_filled)
        else:
            net_price = order_price
        
        return RealisticExecution(
            timestamp=latency.execution_timestamp,
            requested_size=order_size,
            requested_price=order_price,
            actual_size=fill.total_filled,
            actual_price=fill.avg_fill_price,
            slippage=slippage,
            latency=latency,
            fill=fill,
            fees=fees,
            total_cost=total_cost,
            net_execution_price=net_price,
            is_liquidated=liq_check.status == "liquidated",
            liquidation=liq_check if liq_check.status != "safe" else None,
        )
    
    def calculate_total_drag(
        self,
        executions: List[RealisticExecution],
    ) -> Dict[str, float]:
        if not executions:
            return {"total_drag": 0.0, "avg_drag_pct": 0.0}
        
        total_slippage = sum(abs(e.slippage.slippage_pct) for e in executions)
        total_fees = sum(e.fees.total_fee for e in executions)
        total_notional = sum(e.actual_size * e.actual_price for e in executions)
        
        total_drag = total_slippage * total_notional + total_fees
        avg_drag_pct = total_drag / total_notional if total_notional > 0 else 0.0
        
        return {
            "total_slippage_cost": total_slippage * total_notional,
            "total_fees": total_fees,
            "total_drag": total_drag,
            "avg_drag_pct": avg_drag_pct,
            "execution_count": len(executions),
        }
    
    def get_realism_report(
        self,
        execution: RealisticExecution,
    ) -> Dict[str, Any]:
        return {
            "execution": {
                "requested": {
                    "size": execution.requested_size,
                    "price": execution.requested_price,
                },
                "actual": {
                    "size": execution.actual_size,
                    "price": execution.actual_price,
                    "fill_ratio": execution.actual_size / execution.requested_size if execution.requested_size > 0 else 0,
                },
                "net_price": execution.net_execution_price,
                "total_cost": execution.total_cost,
            },
            "slippage": {
                "bps": execution.slippage.slippage_bps,
                "pct": execution.slippage.slippage_pct,
                "market_impact": execution.slippage.market_impact,
            },
            "latency": {
                "total_ms": execution.latency.total_latency_ms,
                "price_drift": execution.latency.price_drift_estimate,
            },
            "fill": {
                "status": execution.fill.status.value,
                "count": execution.fill.fill_count,
                "price_improvement": execution.fill.price_improvement,
            },
            "fees": {
                "trading": execution.fees.trading_fee,
                "funding": execution.fees.funding_fee,
                "total": execution.fees.total_fee,
                "pct": execution.fees.total_fee_pct,
            },
            "liquidation": {
                "is_liquidated": execution.is_liquidated,
                "status": execution.liquidation.status.value if execution.liquidation else "safe",
                "distance_pct": execution.liquidation.distance_to_liquidation_pct if execution.liquidation else 1.0,
            },
        }
