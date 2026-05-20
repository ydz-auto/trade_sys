"""
Liquidation Cascade - 爆仓连锁检测

检测爆仓连锁反应:
1. 快速价格移动
2. 连续爆仓触发
3. 级联效应
4. 反弹机会
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("behaviour.liquidation_cascade")


class CascadePhase(str, Enum):
    NONE = "none"
    BUILDUP = "buildup"
    TRIGGER = "trigger"
    CASCADE = "cascade"
    EXHAUSTION = "exhaustion"
    REVERSAL = "reversal"


@dataclass
class LiquidationCascadeEvent:
    timestamp: datetime
    symbol: str
    phase: CascadePhase
    
    price_move_pct: float
    velocity: float
    
    estimated_liquidations: int
    cascade_depth: int
    
    long_liquidated: float
    short_liquidated: float
    
    cascade_score: float
    reversal_probability: float
    
    signal: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class LiquidationCascadeDetector:
    def __init__(
        self,
        price_threshold: float = 0.05,
        velocity_threshold: float = 0.02,
        lookback_periods: int = 50,
    ):
        self._price_threshold = price_threshold
        self._velocity_threshold = velocity_threshold
        self._lookback = lookback_periods
        
        self._price_history: Dict[str, List[float]] = {}
        self._cascade_count: Dict[str, int] = {}
        
        logger.info("LiquidationCascadeDetector initialized")
    
    def detect(
        self,
        current_price: float,
        prices: List[float],
        funding_rate: float,
        open_interest: float,
        symbol: str,
    ) -> LiquidationCascadeEvent:
        timestamp = datetime.now()
        
        if len(prices) < 10:
            return self._empty_event(timestamp, symbol)
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(current_price)
        if len(self._price_history[symbol]) > self._lookback:
            self._price_history[symbol] = self._price_history[symbol][-self._lookback:]
        
        history = self._price_history[symbol]
        
        price_move = (current_price - history[0]) / history[0] if history[0] > 0 else 0.0
        
        velocity = 0.0
        if len(history) >= 2:
            velocity = (history[-1] - history[-2]) / history[-2] if history[-2] > 0 else 0.0
        
        long_liq, short_liq = self._estimate_liquidations(
            price_move, funding_rate, open_interest
        )
        
        phase = self._determine_phase(
            price_move, velocity, long_liq + short_liq
        )
        
        cascade_depth = self._calculate_cascade_depth(phase, history)
        
        estimated_liqs = int((long_liq + short_liq) * cascade_depth)
        
        cascade_score = self._calculate_score(
            abs(price_move), abs(velocity), estimated_liqs
        )
        
        reversal_prob = self._estimate_reversal(
            phase, cascade_score, funding_rate
        )
        
        signal = self._generate_signal(
            phase, price_move, reversal_prob
        )
        
        return LiquidationCascadeEvent(
            timestamp=timestamp,
            symbol=symbol,
            phase=phase,
            price_move_pct=price_move,
            velocity=velocity,
            estimated_liquidations=estimated_liqs,
            cascade_depth=cascade_depth,
            long_liquidated=long_liq,
            short_liquidated=short_liq,
            cascade_score=cascade_score,
            reversal_probability=reversal_prob,
            signal=signal,
        )
    
    def _estimate_liquidations(
        self,
        price_move: float,
        funding_rate: float,
        open_interest: float,
    ) -> tuple:
        long_liq = 0.0
        short_liq = 0.0
        
        if price_move < -self._price_threshold:
            long_liq = abs(price_move) * open_interest * 0.1
        elif price_move > self._price_threshold:
            short_liq = abs(price_move) * open_interest * 0.1
        
        if funding_rate > 0.001:
            long_liq *= 1.5
        elif funding_rate < -0.001:
            short_liq *= 1.5
        
        return long_liq, short_liq
    
    def _determine_phase(
        self,
        price_move: float,
        velocity: float,
        total_liq: float,
    ) -> CascadePhase:
        if total_liq < 0.01:
            return CascadePhase.NONE
        
        if abs(velocity) < self._velocity_threshold * 0.5:
            return CascadePhase.BUILDUP
        
        if abs(velocity) > self._velocity_threshold * 2:
            if total_liq > 0.1:
                return CascadePhase.CASCADE
            else:
                return CascadePhase.TRIGGER
        
        if abs(velocity) < self._velocity_threshold:
            return CascadePhase.EXHAUSTION
        
        return CascadePhase.TRIGGER
    
    def _calculate_cascade_depth(
        self,
        phase: CascadePhase,
        history: List[float],
    ) -> int:
        if phase == CascadePhase.NONE:
            return 0
        
        if len(history) < 5:
            return 1
        
        changes = np.diff(history)
        direction = 1 if changes[-1] < 0 else -1
        
        depth = 0
        for change in reversed(changes[-10:]):
            if np.sign(change) == direction:
                depth += 1
            else:
                break
        
        return min(5, depth)
    
    def _calculate_score(
        self,
        price_move: float,
        velocity: float,
        liquidations: int,
    ) -> float:
        score = 0.0
        
        score += min(0.4, price_move * 5)
        score += min(0.3, velocity * 10)
        score += min(0.3, liquidations * 0.01)
        
        return min(1.0, score)
    
    def _estimate_reversal(
        self,
        phase: CascadePhase,
        cascade_score: float,
        funding_rate: float,
    ) -> float:
        if phase == CascadePhase.EXHAUSTION:
            return 0.7
        elif phase == CascadePhase.CASCADE:
            return 0.3
        elif phase == CascadePhase.TRIGGER:
            return 0.5
        
        if abs(funding_rate) > 0.005:
            return 0.6
        
        return 0.4
    
    def _generate_signal(
        self,
        phase: CascadePhase,
        price_move: float,
        reversal_prob: float,
    ) -> float:
        if phase == CascadePhase.NONE:
            return 0.0
        
        if phase == CascadePhase.EXHAUSTION:
            if price_move < 0:
                return reversal_prob * 0.8
            else:
                return -reversal_prob * 0.8
        
        if phase == CascadePhase.CASCADE:
            if price_move < 0:
                return -0.5
            else:
                return 0.5
        
        return 0.0
    
    def _empty_event(self, timestamp: datetime, symbol: str) -> LiquidationCascadeEvent:
        return LiquidationCascadeEvent(
            timestamp=timestamp,
            symbol=symbol,
            phase=CascadePhase.NONE,
            price_move_pct=0.0,
            velocity=0.0,
            estimated_liquidations=0,
            cascade_depth=0,
            long_liquidated=0.0,
            short_liquidated=0.0,
            cascade_score=0.0,
            reversal_probability=0.5,
            signal=0.0,
        )


def detect_liquidation_cascade(
    current_price: float,
    prices: List[float],
    funding_rate: float,
    open_interest: float,
    symbol: str,
    detector: Optional[LiquidationCascadeDetector] = None,
) -> LiquidationCascadeEvent:
    detector = detector or LiquidationCascadeDetector()
    return detector.detect(current_price, prices, funding_rate, open_interest, symbol)
