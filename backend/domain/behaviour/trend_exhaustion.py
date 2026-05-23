"""
Trend Exhaustion - 趋势耗竭检测

检测趋势即将结束:
1. 动量衰减
2. 成交量萎缩
3. 背离信号
4. 耗竭形态
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("behaviour.trend_exhaustion")


class ExhaustionLevel(str, Enum):
    NONE = "none"
    EARLY = "early"
    MODERATE = "moderate"
    MATURE = "mature"
    EXHAUSTED = "exhausted"


@dataclass
class TrendExhaustionEvent:
    timestamp: datetime
    symbol: str
    level: ExhaustionLevel
    
    trend_direction: float
    momentum: float
    momentum_change: float
    
    volume_trend: float
    volume_divergence: bool
    
    price_divergence: bool
    
    exhaustion_score: float
    reversal_probability: float
    
    signal: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class TrendExhaustionDetector:
    def __init__(
        self,
        lookback_periods: int = 50,
        momentum_threshold: float = 0.3,
    ):
        self._lookback = lookback_periods
        self._momentum_threshold = momentum_threshold
        
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        
        logger.info("TrendExhaustionDetector initialized")
    
    def detect(
        self,
        prices: List[float],
        volumes: List[float],
        symbol: str,
    ) -> TrendExhaustionEvent:
        timestamp = datetime.now()
        
        if len(prices) < 10 or len(volumes) < 10:
            return self._empty_event(timestamp, symbol)
        
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
        
        price_history = self._price_history[symbol][-self._lookback:]
        vol_history = self._volume_history[symbol][-self._lookback:]
        
        trend_direction = np.sign(price_history[-1] - price_history[0])
        
        momentum = self._calculate_momentum(price_history)
        momentum_change = self._calculate_momentum_change(price_history)
        
        volume_trend = self._calculate_volume_trend(vol_history)
        volume_divergence = self._check_volume_divergence(
            price_history, vol_history, trend_direction
        )
        
        price_divergence = self._check_price_divergence(price_history)
        
        exhaustion_score = self._calculate_exhaustion_score(
            momentum, momentum_change, volume_trend, 
            volume_divergence, price_divergence
        )
        
        level = self._determine_level(exhaustion_score)
        
        reversal_prob = self._estimate_reversal(level, exhaustion_score)
        
        signal = self._generate_signal(
            trend_direction, level, reversal_prob
        )
        
        return TrendExhaustionEvent(
            timestamp=timestamp,
            symbol=symbol,
            level=level,
            trend_direction=trend_direction,
            momentum=momentum,
            momentum_change=momentum_change,
            volume_trend=volume_trend,
            volume_divergence=volume_divergence,
            price_divergence=price_divergence,
            exhaustion_score=exhaustion_score,
            reversal_probability=reversal_prob,
            signal=signal,
        )
    
    def _calculate_momentum(self, prices: List[float]) -> float:
        if len(prices) < 5:
            return 0.0
        
        recent = prices[-5:]
        older = prices[-10:-5] if len(prices) >= 10 else prices[:-5]
        
        recent_change = (recent[-1] - recent[0]) / recent[0] if recent[0] > 0 else 0.0
        older_change = (older[-1] - older[0]) / older[0] if len(older) > 0 and older[0] > 0 else 0.0
        
        return recent_change - older_change
    
    def _calculate_momentum_change(self, prices: List[float]) -> float:
        if len(prices) < 10:
            return 0.0
        
        m1 = self._calculate_momentum(prices[-5:])
        m2 = self._calculate_momentum(prices[-10:-5])
        
        return m1 - m2
    
    def _calculate_volume_trend(self, volumes: List[float]) -> float:
        if len(volumes) < 10:
            return 0.0
        
        recent_avg = np.mean(volumes[-5:])
        older_avg = np.mean(volumes[-10:-5])
        
        return (recent_avg - older_avg) / older_avg if older_avg > 0 else 0.0
    
    def _check_volume_divergence(
        self,
        prices: List[float],
        volumes: List[float],
        trend: float,
    ) -> bool:
        if len(prices) < 10 or len(volumes) < 10:
            return False
        
        price_trend = np.polyfit(range(len(prices)), prices, 1)[0]
        vol_trend = np.polyfit(range(len(volumes)), volumes, 1)[0]
        
        if trend > 0 and price_trend > 0 and vol_trend < 0:
            return True
        if trend < 0 and price_trend < 0 and vol_trend < 0:
            return True
        
        return False
    
    def _check_price_divergence(self, prices: List[float]) -> bool:
        if len(prices) < 20:
            return False
        
        recent_high = max(prices[-10:])
        older_high = max(prices[-20:-10])
        recent_low = min(prices[-10:])
        older_low = min(prices[-20:-10])
        
        if recent_high > older_high and prices[-1] < recent_high * 0.98:
            return True
        if recent_low < older_low and prices[-1] > recent_low * 1.02:
            return True
        
        return False
    
    def _calculate_exhaustion_score(
        self,
        momentum: float,
        momentum_change: float,
        volume_trend: float,
        volume_divergence: bool,
        price_divergence: bool,
    ) -> float:
        score = 0.0
        
        if abs(momentum) < self._momentum_threshold:
            score += 0.3
        
        if momentum_change < 0:
            score += 0.2 * min(1.0, abs(momentum_change) * 10)
        
        if volume_trend < -0.2:
            score += 0.2
        
        if volume_divergence:
            score += 0.15
        
        if price_divergence:
            score += 0.15
        
        return min(1.0, score)
    
    def _determine_level(self, score: float) -> ExhaustionLevel:
        if score < 0.2:
            return ExhaustionLevel.NONE
        elif score < 0.4:
            return ExhaustionLevel.EARLY
        elif score < 0.6:
            return ExhaustionLevel.MODERATE
        elif score < 0.8:
            return ExhaustionLevel.MATURE
        else:
            return ExhaustionLevel.EXHAUSTED
    
    def _estimate_reversal(self, level: ExhaustionLevel, score: float) -> float:
        reversal_map = {
            ExhaustionLevel.NONE: 0.1,
            ExhaustionLevel.EARLY: 0.2,
            ExhaustionLevel.MODERATE: 0.4,
            ExhaustionLevel.MATURE: 0.6,
            ExhaustionLevel.EXHAUSTED: 0.8,
        }
        return reversal_map.get(level, 0.1)
    
    def _generate_signal(
        self,
        trend: float,
        level: ExhaustionLevel,
        reversal_prob: float,
    ) -> float:
        if level == ExhaustionLevel.NONE:
            return 0.0
        
        signal = -trend * reversal_prob * 0.5
        
        return np.clip(signal, -1.0, 1.0)
    
    def _empty_event(self, timestamp: datetime, symbol: str) -> TrendExhaustionEvent:
        return TrendExhaustionEvent(
            timestamp=timestamp,
            symbol=symbol,
            level=ExhaustionLevel.NONE,
            trend_direction=0.0,
            momentum=0.0,
            momentum_change=0.0,
            volume_trend=0.0,
            volume_divergence=False,
            price_divergence=False,
            exhaustion_score=0.0,
            reversal_probability=0.0,
            signal=0.0,
        )


def detect_trend_exhaustion(
    prices: List[float],
    volumes: List[float],
    symbol: str,
    detector: Optional[TrendExhaustionDetector] = None,
) -> TrendExhaustionEvent:
    detector = detector or TrendExhaustionDetector()
    return detector.detect(prices, volumes, symbol)
