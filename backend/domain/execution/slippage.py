from typing import Dict, Any, List
from dataclasses import dataclass
import numpy as np


@dataclass
class SlippagePrediction:
    expected_slippage_bps: float
    slippage_std: float
    worst_case_bps: float
    best_case_bps: float
    confidence: float
    factors: Dict[str, float]


class SlippagePredictor:

    def __init__(self):
        self.spread_coef = 0.5
        self.volatility_coef = 2.0
        self.size_coef = 0.0001
        self.liquidity_coef = 0.8
        self.history: List[Dict[str, Any]] = []

    def predict(
        self,
        order_size: float,
        current_price: float,
        spread_bps: float,
        volatility: float,
        orderbook_depth: float,
        avg_trade_size: float,
        is_maker: bool = False,
    ) -> SlippagePrediction:
        factors = {}

        base_slippage = spread_bps * self.spread_coef
        factors["spread"] = base_slippage

        volatility_slippage = volatility * 100 * self.volatility_coef
        factors["volatility"] = volatility_slippage

        relative_size = order_size / (avg_trade_size or 1)
        size_slippage = relative_size * self.size_coef * 100
        factors["size"] = size_slippage

        if orderbook_depth > 0:
            liquidity_ratio = order_size / orderbook_depth
            liquidity_slippage = liquidity_ratio * self.liquidity_coef * 100
            factors["liquidity"] = liquidity_slippage
        else:
            liquidity_slippage = 0.0
            factors["liquidity"] = 0.0

        total_expected = base_slippage + volatility_slippage + size_slippage + liquidity_slippage

        if is_maker:
            total_expected *= 0.3

        slippage_std = volatility * 50

        worst_case = total_expected + slippage_std * 2
        best_case = max(0, total_expected - slippage_std * 2)

        confidence = 0.7
        if orderbook_depth > 0 and avg_trade_size > 0:
            confidence = 0.9

        return SlippagePrediction(
            expected_slippage_bps=total_expected,
            slippage_std=slippage_std,
            worst_case_bps=worst_case,
            best_case_bps=best_case,
            confidence=confidence,
            factors=factors,
        )

    def record_actual_slippage(
        self,
        order_size: float,
        requested_price: float,
        actual_price: float,
        side: str,
        market_data: Dict[str, Any],
    ) -> None:
        if requested_price > 0:
            slippage_pct = abs((actual_price - requested_price) / requested_price)
            slippage_bps = slippage_pct * 10000

            self.history.append({
                "size": order_size,
                "slippage_bps": slippage_bps,
                "side": side,
                "timestamp": market_data.get("timestamp"),
                "spread": market_data.get("spread_bps"),
                "volatility": market_data.get("volatility"),
            })

            if len(self.history) > 1000:
                self.history = self.history[-1000:]

    def calibrate(self) -> None:
        if len(self.history) < 100:
            return

        recent = self.history[-100:]

        spread_slippage = [h["slippage_bps"] / h["spread"] for h in recent if h["spread"] > 0]
        if spread_slippage:
            self.spread_coef = np.mean(spread_slippage)

        volatility_slippage = [h["slippage_bps"] / (h["volatility"] * 100) for h in recent if h["volatility"] > 0]
        if volatility_slippage:
            self.volatility_coef = np.mean(volatility_slippage)


@dataclass
class ImpactResult:
    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    price_impact: float
    recovery_time_seconds: float


class ImpactModel:

    def __init__(self):
        self.temporary_coef = 0.3
        self.permanent_coef = 0.1
        self.recovery_rate = 0.1

    def calculate_impact(
        self,
        order_size: float,
        current_price: float,
        orderbook_depth: float,
        volatility: float,
        avg_daily_volume: float,
    ) -> ImpactResult:
        if orderbook_depth <= 0 or avg_daily_volume <= 0:
            return ImpactResult(
                temporary_impact_bps=0.0,
                permanent_impact_bps=0.0,
                total_impact_bps=0.0,
                price_impact=0.0,
                recovery_time_seconds=0.0,
            )

        depth_ratio = order_size / orderbook_depth

        volume_ratio = order_size / (avg_daily_volume / 24)

        temporary_impact = depth_ratio * self.temporary_coef * 100

        permanent_impact = volume_ratio * self.permanent_coef * 100

        volatility_factor = 1 + volatility * 2

        temporary_impact *= volatility_factor
        permanent_impact *= volatility_factor

        total_impact = temporary_impact + permanent_impact

        price_impact = current_price * (total_impact / 10000)

        recovery_time = 60 * (1 + depth_ratio * 10)

        return ImpactResult(
            temporary_impact_bps=temporary_impact,
            permanent_impact_bps=permanent_impact,
            total_impact_bps=total_impact,
            price_impact=price_impact,
            recovery_time_seconds=recovery_time,
        )

    def estimate_optimal_size(
        self,
        desired_size: float,
        max_impact_bps: float,
        current_price: float,
        orderbook_depth: float,
        volatility: float,
        avg_daily_volume: float,
    ) -> float:
        if max_impact_bps <= 0:
            return 0.0

        low = 0.0
        high = desired_size * 2
        optimal = 0.0

        for _ in range(20):
            mid = (low + high) / 2
            impact = self.calculate_impact(mid, current_price, orderbook_depth, volatility, avg_daily_volume)

            if impact.total_impact_bps <= max_impact_bps:
                optimal = mid
                low = mid
            else:
                high = mid

        return min(optimal, desired_size)
