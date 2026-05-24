from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

import logging

logger = logging.getLogger(__name__)


class AbsorptionType(str, Enum):
    NONE = "none"
    PASSIVE = "passive"
    AGGRESSIVE = "aggressive"
    STEALTH = "stealth"


@dataclass
class AbsorptionEvent:
    timestamp: datetime
    symbol: str
    absorption_type: AbsorptionType

    price_stability: float
    volume_intensity: float

    buy_pressure: float
    ask_absorption_rate: float

    absorption_score: float
    duration_estimate: float

    signal: float

    metadata: Dict[str, Any] = field(default_factory=dict)


class AbsorptionDetector:
    def __init__(
        self,
        stability_threshold: float = 0.005,
        volume_threshold: float = 2.0,
        lookback_periods: int = 30,
    ):
        self._stability_threshold = stability_threshold
        self._volume_threshold = volume_threshold
        self._lookback = lookback_periods

        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        self._avg_volume: Dict[str, float] = {}

        logger.info("AbsorptionDetector initialized")

    def detect(
        self,
        prices: List[float],
        volumes: List[float],
        trades: List[Dict[str, Any]],
        orderbook: tuple,
        symbol: str,
    ) -> AbsorptionEvent:
        timestamp = datetime.now()

        if len(prices) < 5 or len(volumes) < 5:
            return self._empty_event(timestamp, symbol)

        prices = prices[-self._lookback:]
        volumes = volumes[-self._lookback:]

        price_range = max(prices) - min(prices)
        price_mean = np.mean(prices)
        price_stability = 1.0 - (price_range / price_mean) if price_mean > 0 else 0.0

        if symbol not in self._avg_volume:
            self._avg_volume[symbol] = np.mean(volumes)
        else:
            self._avg_volume[symbol] = 0.9 * self._avg_volume[symbol] + 0.1 * np.mean(volumes)

        avg_vol = self._avg_volume[symbol]
        current_vol = np.mean(volumes[-5:])
        volume_intensity = current_vol / avg_vol if avg_vol > 0 else 1.0

        buy_vol = sum(t["size"] for t in trades if t.get("side") == "buy")
        sell_vol = sum(t["size"] for t in trades if t.get("side") == "sell")
        total_vol = buy_vol + sell_vol
        buy_pressure = buy_vol / total_vol if total_vol > 0 else 0.5

        bids, asks = orderbook
        ask_sizes = [size for _, size in asks[:10]]
        ask_absorption_rate = 0.0
        if len(ask_sizes) >= 2:
            ask_absorption_rate = (ask_sizes[0] - ask_sizes[-1]) / ask_sizes[-1] if ask_sizes[-1] > 0 else 0.0

        absorption_score = self._calculate_score(
            price_stability, volume_intensity, buy_pressure, ask_absorption_rate
        )

        absorption_type = self._determine_type(
            price_stability, volume_intensity, buy_pressure
        )

        duration = self._estimate_duration(volume_intensity, absorption_score)

        signal = np.tanh(absorption_score * 2) if absorption_score > 0.3 else 0.0

        return AbsorptionEvent(
            timestamp=timestamp,
            symbol=symbol,
            absorption_type=absorption_type,
            price_stability=price_stability,
            volume_intensity=volume_intensity,
            buy_pressure=buy_pressure,
            ask_absorption_rate=ask_absorption_rate,
            absorption_score=absorption_score,
            duration_estimate=duration,
            signal=signal,
        )

    def _calculate_score(
        self,
        stability: float,
        intensity: float,
        buy_pressure: float,
        absorption_rate: float,
    ) -> float:
        score = 0.0

        if stability > 0.9:
            score += 0.3

        if intensity > self._volume_threshold:
            score += 0.3 * min(1.0, intensity / self._volume_threshold)

        if buy_pressure > 0.6:
            score += 0.2 * (buy_pressure - 0.5) * 2

        if absorption_rate > 0.3:
            score += 0.2 * min(1.0, absorption_rate)

        return min(1.0, score)

    def _determine_type(
        self,
        stability: float,
        intensity: float,
        buy_pressure: float,
    ) -> AbsorptionType:
        if stability > 0.95 and intensity < 1.5:
            return AbsorptionType.STEALTH
        elif intensity > self._volume_threshold * 1.5:
            return AbsorptionType.AGGRESSIVE
        elif buy_pressure > 0.6:
            return AbsorptionType.PASSIVE
        else:
            return AbsorptionType.NONE

    def _estimate_duration(self, intensity: float, score: float) -> float:
        if score < 0.3:
            return 0.0
        return intensity * score * 10

    def _empty_event(self, timestamp: datetime, symbol: str) -> AbsorptionEvent:
        return AbsorptionEvent(
            timestamp=timestamp,
            symbol=symbol,
            absorption_type=AbsorptionType.NONE,
            price_stability=0.0,
            volume_intensity=1.0,
            buy_pressure=0.5,
            ask_absorption_rate=0.0,
            absorption_score=0.0,
            duration_estimate=0.0,
            signal=0.0,
        )


def detect_absorption(
    prices: List[float],
    volumes: List[float],
    trades: List[Dict[str, Any]],
    orderbook: tuple,
    symbol: str,
    detector: Optional[AbsorptionDetector] = None,
) -> AbsorptionEvent:
    detector = detector or AbsorptionDetector()
    return detector.detect(prices, volumes, trades, orderbook, symbol)
