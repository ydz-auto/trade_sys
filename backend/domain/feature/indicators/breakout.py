from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

import logging

logger = logging.getLogger(__name__)


class BreakoutType(str, Enum):
    NONE = "none"
    UPWARD = "upward"
    DOWNWARD = "downward"
    FAKE_UP = "fake_up"
    FAKE_DOWN = "fake_down"


@dataclass
class BreakoutEvent:
    timestamp: datetime
    symbol: str
    breakout_type: BreakoutType

    breakout_level: float
    current_price: float
    breakout_distance: float

    volume_confirmation: bool
    volume_ratio: float

    breakout_strength: float
    is_false_breakout: bool

    pullback_probability: float

    signal: float

    metadata: Dict[str, Any] = field(default_factory=dict)


class BreakoutDetector:
    def __init__(
        self,
        lookback_periods: int = 50,
        volume_threshold: float = 1.5,
        false_breakout_threshold: float = 0.3,
    ):
        self._lookback = lookback_periods
        self._volume_threshold = volume_threshold
        self._false_breakout_threshold = false_breakout_threshold

        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        self._range_history: Dict[str, List[Tuple[float, float]]] = {}

        logger.info("BreakoutDetector initialized")

    def detect(
        self,
        current_price: float,
        current_volume: float,
        prices: List[float],
        volumes: List[float],
        symbol: str,
    ) -> BreakoutEvent:
        timestamp = datetime.now()

        if len(prices) < 10:
            return self._empty_event(timestamp, symbol, current_price)

        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].extend(prices)
        if len(self._price_history[symbol]) > self._lookback * 2:
            self._price_history[symbol] = self._price_history[symbol][-self._lookback * 2:]

        if symbol not in self._volume_history:
            self._volume_history[symbol] = []
        self._volume_history[symbol].extend(volumes)
        if len(self._volume_history[symbol]) > self._lookback * 2:
            self._volume_history[symbol] = self._volume_history[symbol][-self._lookback * 2:]

        history = self._price_history[symbol][-self._lookback:]
        vol_history = self._volume_history[symbol][-self._lookback:]

        resistance = max(history[:-5])
        support = min(history[:-5])

        avg_volume = np.mean(vol_history[:-5]) if len(vol_history) > 5 else 1.0
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        volume_confirmed = volume_ratio > self._volume_threshold

        upward_breakout = current_price > resistance
        downward_breakout = current_price < support

        if upward_breakout:
            breakout_level = resistance
            breakout_distance = (current_price - resistance) / resistance
            base_type = BreakoutType.UPWARD
        elif downward_breakout:
            breakout_level = support
            breakout_distance = (support - current_price) / support
            base_type = BreakoutType.DOWNWARD
        else:
            return self._empty_event(timestamp, symbol, current_price)

        is_false = self._check_false_breakout(
            history, current_price, base_type, volume_confirmed
        )

        if is_false:
            breakout_type = BreakoutType.FAKE_UP if base_type == BreakoutType.UPWARD else BreakoutType.FAKE_DOWN
        else:
            breakout_type = base_type

        strength = self._calculate_strength(
            breakout_distance, volume_ratio, volume_confirmed, is_false
        )

        pullback_prob = self._estimate_pullback(
            breakout_distance, volume_ratio, is_false
        )

        if breakout_type == BreakoutType.UPWARD:
            signal = strength * (1 - pullback_prob)
        elif breakout_type == BreakoutType.DOWNWARD:
            signal = -strength * (1 - pullback_prob)
        elif breakout_type in [BreakoutType.FAKE_UP, BreakoutType.FAKE_DOWN]:
            signal = -0.3 if breakout_type == BreakoutType.FAKE_UP else 0.3
        else:
            signal = 0.0

        return BreakoutEvent(
            timestamp=timestamp,
            symbol=symbol,
            breakout_type=breakout_type,
            breakout_level=breakout_level,
            current_price=current_price,
            breakout_distance=breakout_distance,
            volume_confirmation=volume_confirmed,
            volume_ratio=volume_ratio,
            breakout_strength=strength,
            is_false_breakout=is_false,
            pullback_probability=pullback_prob,
            signal=signal,
        )

    def _check_false_breakout(
        self,
        history: List[float],
        current_price: float,
        breakout_type: BreakoutType,
        volume_confirmed: bool,
    ) -> bool:
        if not volume_confirmed:
            return True

        recent_range = max(history[-10:]) - min(history[-10:])
        avg_range = (max(history) - min(history)) / 2

        if recent_range < avg_range * self._false_breakout_threshold:
            return True

        return False

    def _calculate_strength(
        self,
        distance: float,
        volume_ratio: float,
        volume_confirmed: bool,
        is_false: bool,
    ) -> float:
        if is_false:
            return 0.2

        strength = 0.5

        strength += min(0.3, distance * 10)

        if volume_confirmed:
            strength += min(0.2, (volume_ratio - 1) * 0.2)

        return min(1.0, strength)

    def _estimate_pullback(
        self,
        distance: float,
        volume_ratio: float,
        is_false: bool,
    ) -> float:
        if is_false:
            return 0.8

        pullback = 0.3

        if distance > 0.02:
            pullback -= 0.1

        if volume_ratio > 2.0:
            pullback -= 0.1

        return max(0.1, min(0.7, pullback))

    def _empty_event(self, timestamp: datetime, symbol: str, price: float) -> BreakoutEvent:
        return BreakoutEvent(
            timestamp=timestamp,
            symbol=symbol,
            breakout_type=BreakoutType.NONE,
            breakout_level=price,
            current_price=price,
            breakout_distance=0.0,
            volume_confirmation=False,
            volume_ratio=1.0,
            breakout_strength=0.0,
            is_false_breakout=False,
            pullback_probability=0.5,
            signal=0.0,
        )


def detect_breakout(
    current_price: float,
    current_volume: float,
    prices: List[float],
    volumes: List[float],
    symbol: str,
    detector: Optional[BreakoutDetector] = None,
) -> BreakoutEvent:
    detector = detector or BreakoutDetector()
    return detector.detect(current_price, current_volume, prices, volumes, symbol)
