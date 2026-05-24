from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

import logging

from domain.execution.slippage import SlippagePredictor, SlippagePrediction, ImpactModel, ImpactResult
from domain.execution.fee_model import LiquidityEstimator, LiquidityEstimate, LiquidityRating

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    TWAP = "twap"
    VWAP = "vwap"
    AGGRESSIVE = "aggressive"
    PASSIVE = "passive"
    ADAPTIVE = "adaptive"


@dataclass
class SmartExecutionPlan:
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
    ) -> SmartExecutionPlan:
        strategy = self._select_strategy(urgency, market_data)

        slices = self._generate_slices(
            order_size, order_side, current_price,
            strategy, urgency, market_data, time_limit_seconds
        )

        estimated_duration = self._estimate_duration(slices, strategy)
        estimated_price = self._estimate_avg_price(slices, current_price)
        estimated_slippage = self._estimate_slippage(slices, market_data)

        return SmartExecutionPlan(
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
) -> SmartExecutionPlan:
    executor = executor or SmartExecution()
    return executor.plan(
        order_size, order_side, current_price,
        urgency, market_data, time_limit_seconds
    )


@dataclass
class ExecutionRecord:
    timestamp: datetime
    symbol: str
    side: str
    requested_size: float
    requested_price: float
    filled_size: float
    filled_price: float
    slippage_bps: float
    latency_ms: float
    fee: float


@dataclass
class ExecutionStats:
    total_orders: int
    total_volume: float
    fill_rate: float
    avg_fill_ratio: float
    avg_slippage_bps: float
    worst_slippage_bps: float
    avg_latency_ms: float
    p99_latency_ms: float
    total_fees: float
    total_slippage_cost: float
    execution_score: float


class ExecutionAnalytics:
    def __init__(self, history_size: int = 1000):
        self._history_size = history_size
        self._records: Dict[str, List[ExecutionRecord]] = {}

        logger.info("ExecutionAnalytics initialized")

    def record(
        self,
        symbol: str,
        side: str,
        requested_size: float,
        requested_price: float,
        filled_size: float,
        filled_price: float,
        latency_ms: float,
        fee: float,
    ) -> ExecutionRecord:
        timestamp = datetime.now()

        if requested_price > 0:
            slippage_pct = (filled_price - requested_price) / requested_price
            if side == "sell":
                slippage_pct = -slippage_pct
            slippage_bps = abs(slippage_pct) * 10000
        else:
            slippage_bps = 0.0

        record = ExecutionRecord(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            requested_size=requested_size,
            requested_price=requested_price,
            filled_size=filled_size,
            filled_price=filled_price,
            slippage_bps=slippage_bps,
            latency_ms=latency_ms,
            fee=fee,
        )

        if symbol not in self._records:
            self._records[symbol] = []

        self._records[symbol].append(record)

        if len(self._records[symbol]) > self._history_size:
            self._records[symbol] = self._records[symbol][-self._history_size:]

        return record

    def get_stats(
        self,
        symbol: str,
        period_hours: Optional[float] = None,
    ) -> ExecutionStats:
        records = self._records.get(symbol, [])

        if period_hours:
            cutoff = datetime.now() - timedelta(hours=period_hours)
            records = [r for r in records if r.timestamp >= cutoff]

        if not records:
            return self._empty_stats()

        total_orders = len(records)
        total_volume = sum(r.filled_size * r.filled_price for r in records)

        fill_ratios = [
            r.filled_size / r.requested_size
            for r in records if r.requested_size > 0
        ]
        avg_fill_ratio = np.mean(fill_ratios) if fill_ratios else 0.0
        fill_rate = sum(1 for r in fill_ratios if r >= 0.99) / total_orders

        slippages = [r.slippage_bps for r in records]
        avg_slippage = np.mean(slippages)
        worst_slippage = max(slippages)

        latencies = [r.latency_ms for r in records]
        avg_latency = np.mean(latencies)
        p99_latency = np.percentile(latencies, 99) if len(latencies) >= 100 else max(latencies)

        total_fees = sum(r.fee for r in records)
        total_slippage_cost = sum(
            r.slippage_bps / 10000 * r.filled_size * r.filled_price
            for r in records
        )

        execution_score = self._calculate_score(
            fill_rate, avg_slippage, avg_latency
        )

        return ExecutionStats(
            total_orders=total_orders,
            total_volume=total_volume,
            fill_rate=fill_rate,
            avg_fill_ratio=avg_fill_ratio,
            avg_slippage_bps=avg_slippage,
            worst_slippage_bps=worst_slippage,
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
            total_fees=total_fees,
            total_slippage_cost=total_slippage_cost,
            execution_score=execution_score,
        )

    def _calculate_score(
        self,
        fill_rate: float,
        avg_slippage: float,
        avg_latency: float,
    ) -> float:
        score = 0.0

        score += fill_rate * 0.4

        if avg_slippage < 5:
            score += 0.3
        elif avg_slippage < 10:
            score += 0.2
        elif avg_slippage < 20:
            score += 0.1

        if avg_latency < 100:
            score += 0.3
        elif avg_latency < 200:
            score += 0.2
        elif avg_latency < 500:
            score += 0.1

        return score

    def _empty_stats(self) -> ExecutionStats:
        return ExecutionStats(
            total_orders=0,
            total_volume=0.0,
            fill_rate=0.0,
            avg_fill_ratio=0.0,
            avg_slippage_bps=0.0,
            worst_slippage_bps=0.0,
            avg_latency_ms=0.0,
            p99_latency_ms=0.0,
            total_fees=0.0,
            total_slippage_cost=0.0,
            execution_score=0.0,
        )

    def get_report(
        self,
        symbol: str,
        period_hours: float = 24.0,
    ) -> Dict[str, Any]:
        stats = self.get_stats(symbol, period_hours)

        return {
            "symbol": symbol,
            "period_hours": period_hours,
            "summary": {
                "total_orders": stats.total_orders,
                "total_volume": stats.total_volume,
                "fill_rate": f"{stats.fill_rate * 100:.1f}%",
                "avg_fill_ratio": f"{stats.avg_fill_ratio * 100:.1f}%",
            },
            "slippage": {
                "avg_bps": f"{stats.avg_slippage_bps:.2f}",
                "worst_bps": f"{stats.worst_slippage_bps:.2f}",
                "total_cost": stats.total_slippage_cost,
            },
            "latency": {
                "avg_ms": f"{stats.avg_latency_ms:.1f}",
                "p99_ms": f"{stats.p99_latency_ms:.1f}",
            },
            "costs": {
                "total_fees": stats.total_fees,
                "total_slippage": stats.total_slippage_cost,
                "total_cost": stats.total_fees + stats.total_slippage_cost,
            },
            "score": {
                "value": f"{stats.execution_score:.2f}",
                "rating": self._get_rating(stats.execution_score),
            },
        }

    def _get_rating(self, score: float) -> str:
        if score >= 0.9:
            return "Excellent"
        elif score >= 0.7:
            return "Good"
        elif score >= 0.5:
            return "Fair"
        else:
            return "Poor"


class ExecutionStrategyType(str, Enum):
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    CAREFUL = "careful"
    PASSIVE = "passive"
    TWAP = "twap"
    VWAP = "vwap"


@dataclass
class ExecutionPlan:
    strategy: ExecutionStrategyType
    order_type: str
    num_slices: int
    time_window_seconds: float
    price_offset_bps: float
    max_slippage_bps: float
    expected_slippage_bps: float
    expected_impact_bps: float
    total_cost_bps: float
    confidence: float
    rationale: str
    slices: Optional[List[Dict[str, Any]]] = None


class ExecutionOptimizer:

    def __init__(self):
        self.slippage_predictor = SlippagePredictor()
        self.impact_model = ImpactModel()
        self.liquidity_estimator = LiquidityEstimator()

    def optimize(
        self,
        order_size: float,
        current_price: float,
        side: str,
        bid_price: float,
        ask_price: float,
        bid_depth: float,
        ask_depth: float,
        spread_bps: float,
        volatility: float,
        recent_volume: float,
        avg_daily_volume: float,
        avg_trade_size: float,
        time_constraint_seconds: Optional[float] = None,
        max_slippage_limit: Optional[float] = None,
    ) -> ExecutionPlan:
        liquidity = self.liquidity_estimator.estimate(
            bid_price, ask_price, bid_depth, ask_depth, recent_volume, volatility
        )

        slippage = self.slippage_predictor.predict(
            order_size, current_price, spread_bps, volatility,
            bid_depth + ask_depth, avg_trade_size, is_maker=False
        )

        impact = self.impact_model.calculate_impact(
            order_size, current_price, bid_depth + ask_depth, volatility, avg_daily_volume
        )

        strategy, rationale = self._select_strategy(
            liquidity, slippage, impact, time_constraint_seconds, max_slippage_limit
        )

        plan = self._generate_plan(
            strategy, order_size, current_price, side, liquidity, slippage, impact,
            time_constraint_seconds, max_slippage_limit
        )

        return plan

    def _select_strategy(
        self,
        liquidity: LiquidityEstimate,
        slippage: SlippagePrediction,
        impact: ImpactResult,
        time_constraint: Optional[float],
        max_slippage: Optional[float],
    ) -> tuple[ExecutionStrategyType, str]:
        if liquidity.rating == LiquidityRating.CRITICAL:
            return ExecutionStrategyType.PASSIVE, "Critical liquidity, must be passive"

        if max_slippage and slippage.expected_slippage_bps > max_slippage:
            return ExecutionStrategyType.PASSIVE, f"Expected slippage {slippage.expected_slippage_bps:.1f}bps exceeds limit {max_slippage}bps"

        if time_constraint and time_constraint < 60:
            return ExecutionStrategyType.AGGRESSIVE, f"Time constraint {time_constraint}s requires aggressive execution"

        if liquidity.rating == LiquidityRating.EXCELLENT and impact.total_impact_bps < 10:
            return ExecutionStrategyType.AGGRESSIVE, "Excellent liquidity and low impact"

        if liquidity.rating == LiquidityRating.GOOD and impact.total_impact_bps < 20:
            return ExecutionStrategyType.NORMAL, "Good liquidity and moderate impact"

        if liquidity.rating == LiquidityRating.MODERATE:
            return ExecutionStrategyType.CAREFUL, "Moderate liquidity, need careful execution"

        if liquidity.rating == LiquidityRating.POOR:
            return ExecutionStrategyType.PASSIVE, "Poor liquidity, should be passive"

        if impact.total_impact_bps > 50:
            return ExecutionStrategyType.TWAP, f"High impact {impact.total_impact_bps:.1f}bps, use TWAP"

        return ExecutionStrategyType.NORMAL, "Default to normal execution"

    def _generate_plan(
        self,
        strategy: ExecutionStrategyType,
        order_size: float,
        current_price: float,
        side: str,
        liquidity: LiquidityEstimate,
        slippage: SlippagePrediction,
        impact: ImpactResult,
        time_constraint: Optional[float],
        max_slippage: Optional[float],
    ) -> ExecutionPlan:
        if strategy == ExecutionStrategyType.AGGRESSIVE:
            return ExecutionPlan(
                strategy=ExecutionStrategyType.AGGRESSIVE,
                order_type="market",
                num_slices=1,
                time_window_seconds=0.0,
                price_offset_bps=0.0,
                max_slippage_bps=max_slippage or slippage.worst_case_bps,
                expected_slippage_bps=slippage.expected_slippage_bps,
                expected_impact_bps=impact.total_impact_bps,
                total_cost_bps=slippage.expected_slippage_bps + impact.total_impact_bps,
                confidence=slippage.confidence,
                rationale=f"Aggressive execution - liquidity: {liquidity.rating.value}, impact: {impact.total_impact_bps:.1f}bps",
            )

        if strategy == ExecutionStrategyType.NORMAL:
            num_slices = min(5, max(1, int(order_size / (liquidity.available_depth / 10 + 1))))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.NORMAL,
                order_type="limit",
                num_slices=num_slices,
                time_window_seconds=60 * num_slices,
                price_offset_bps=0.0,
                max_slippage_bps=max_slippage or slippage.worst_case_bps,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.6,
                expected_impact_bps=impact.total_impact_bps * 0.4,
                total_cost_bps=slippage.expected_slippage_bps * 0.6 + impact.total_impact_bps * 0.4,
                confidence=slippage.confidence * 0.9,
                rationale=f"Normal execution with {num_slices} slices",
            )

        if strategy == ExecutionStrategyType.CAREFUL:
            num_slices = min(10, max(2, int(order_size / (liquidity.available_depth / 20 + 1))))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.CAREFUL,
                order_type="limit_passive",
                num_slices=num_slices,
                time_window_seconds=120 * num_slices,
                price_offset_bps=liquidity.bid_ask_spread_bps * 0.5,
                max_slippage_bps=max_slippage or slippage.expected_slippage_bps * 0.8,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.4,
                expected_impact_bps=impact.total_impact_bps * 0.3,
                total_cost_bps=slippage.expected_slippage_bps * 0.4 + impact.total_impact_bps * 0.3,
                confidence=slippage.confidence * 0.8,
                rationale=f"Careful execution with {num_slices} slices over {120 * num_slices}s",
            )

        if strategy == ExecutionStrategyType.PASSIVE:
            num_slices = min(20, max(3, int(order_size / (liquidity.available_depth / 50 + 1))))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.PASSIVE,
                order_type="limit_deep",
                num_slices=num_slices,
                time_window_seconds=300 * num_slices,
                price_offset_bps=liquidity.bid_ask_spread_bps * 1.5,
                max_slippage_bps=max_slippage or slippage.expected_slippage_bps * 0.5,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.2,
                expected_impact_bps=impact.total_impact_bps * 0.1,
                total_cost_bps=slippage.expected_slippage_bps * 0.2 + impact.total_impact_bps * 0.1,
                confidence=slippage.confidence * 0.7,
                rationale=f"Passive execution with {num_slices} slices over {300 * num_slices}s",
            )

        if strategy == ExecutionStrategyType.TWAP:
            time_window = time_constraint or 3600
            num_slices = min(30, max(5, int(time_window / 60)))
            return ExecutionPlan(
                strategy=ExecutionStrategyType.TWAP,
                order_type="twap_limit",
                num_slices=num_slices,
                time_window_seconds=time_window,
                price_offset_bps=0.0,
                max_slippage_bps=max_slippage or slippage.expected_slippage_bps,
                expected_slippage_bps=slippage.expected_slippage_bps * 0.7,
                expected_impact_bps=impact.total_impact_bps * 0.5,
                total_cost_bps=slippage.expected_slippage_bps * 0.7 + impact.total_impact_bps * 0.5,
                confidence=slippage.confidence * 0.85,
                rationale=f"TWAP over {time_window}s with {num_slices} slices",
            )

        return ExecutionPlan(
            strategy=ExecutionStrategyType.NORMAL,
            order_type="limit",
            num_slices=3,
            time_window_seconds=180.0,
            price_offset_bps=0.0,
            max_slippage_bps=max_slippage or slippage.worst_case_bps,
            expected_slippage_bps=slippage.expected_slippage_bps * 0.6,
            expected_impact_bps=impact.total_impact_bps * 0.4,
            total_cost_bps=slippage.expected_slippage_bps * 0.6 + impact.total_impact_bps * 0.4,
            confidence=slippage.confidence * 0.9,
            rationale="Default normal execution",
        )
