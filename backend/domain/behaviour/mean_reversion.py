"""
Mean Reversion - 均值回归检测

检测价格回归均值:
1. 统计偏离度
2. 回归区间识别
3. 回归概率计算
4. 回归时机判断
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("behaviour.mean_reversion")


class ReversionSignal(str, Enum):
    NONE = "none"
    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    EXTREME_HIGH = "extreme_high"
    EXTREME_LOW = "extreme_low"


@dataclass
class MeanReversionEvent:
    timestamp: datetime
    symbol: str
    signal: ReversionSignal
    
    current_price: float
    mean_price: float
    std_dev: float
    
    z_score: float
    deviation_pct: float
    
    reversion_probability: float
    expected_reversion: float
    
    confidence: float
    
    trade_signal: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class MeanReversionDetector:
    def __init__(
        self,
        lookback_periods: int = 100,
        z_threshold: float = 2.0,
        extreme_threshold: float = 3.0,
    ):
        self._lookback = lookback_periods
        self._z_threshold = z_threshold
        self._extreme_threshold = extreme_threshold
        
        self._price_history: Dict[str, List[float]] = {}
        
        logger.info("MeanReversionDetector initialized")
    
    def detect(
        self,
        current_price: float,
        prices: List[float],
        symbol: str,
    ) -> MeanReversionEvent:
        timestamp = datetime.now()
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].extend(prices)
        if len(self._price_history[symbol]) > self._lookback * 2:
            self._price_history[symbol] = self._price_history[symbol][-self._lookback * 2:]
        
        history = self._price_history[symbol][-self._lookback:]
        
        if len(history) < 20:
            return self._empty_event(timestamp, symbol, current_price)
        
        mean_price = np.mean(history)
        std_dev = np.std(history)
        
        if std_dev == 0:
            return self._empty_event(timestamp, symbol, current_price)
        
        z_score = (current_price - mean_price) / std_dev
        
        deviation_pct = (current_price - mean_price) / mean_price if mean_price > 0 else 0.0
        
        signal = self._determine_signal(z_score)
        
        reversion_prob = self._calculate_reversion_prob(z_score)
        
        expected_reversion = self._estimate_reversion(
            current_price, mean_price, z_score
        )
        
        confidence = self._calculate_confidence(len(history), abs(z_score))
        
        trade_signal = self._generate_trade_signal(
            signal, reversion_prob, confidence
        )
        
        return MeanReversionEvent(
            timestamp=timestamp,
            symbol=symbol,
            signal=signal,
            current_price=current_price,
            mean_price=mean_price,
            std_dev=std_dev,
            z_score=z_score,
            deviation_pct=deviation_pct,
            reversion_probability=reversion_prob,
            expected_reversion=expected_reversion,
            confidence=confidence,
            trade_signal=trade_signal,
        )
    
    def _determine_signal(self, z_score: float) -> ReversionSignal:
        abs_z = abs(z_score)
        
        if abs_z < self._z_threshold:
            return ReversionSignal.NONE
        
        if z_score > self._extreme_threshold:
            return ReversionSignal.EXTREME_HIGH
        elif z_score < -self._extreme_threshold:
            return ReversionSignal.EXTREME_LOW
        elif z_score > self._z_threshold:
            return ReversionSignal.OVERBOUGHT
        else:
            return ReversionSignal.OVERSOLD
    
    def _calculate_reversion_prob(self, z_score: float) -> float:
        abs_z = abs(z_score)
        
        if abs_z < self._z_threshold:
            return 0.2
        
        prob = 0.3 + (abs_z - self._z_threshold) * 0.2
        
        return min(0.95, prob)
    
    def _estimate_reversion(
        self,
        current: float,
        mean: float,
        z_score: float,
    ) -> float:
        if abs(z_score) < self._z_threshold:
            return 0.0
        
        reversion_pct = 0.3 + min(0.4, abs(z_score) * 0.1)
        
        distance = abs(current - mean)
        expected_move = distance * reversion_pct
        
        if current > mean:
            return -expected_move
        else:
            return expected_move
    
    def _calculate_confidence(self, history_len: int, abs_z: float) -> float:
        len_factor = min(1.0, history_len / 50)
        
        z_factor = min(1.0, abs_z / self._extreme_threshold)
        
        return 0.6 * len_factor + 0.4 * z_factor
    
    def _generate_trade_signal(
        self,
        signal: ReversionSignal,
        reversion_prob: float,
        confidence: float,
    ) -> float:
        if signal == ReversionSignal.NONE:
            return 0.0
        
        base_signal = 0.0
        if signal == ReversionSignal.OVERBOUGHT:
            base_signal = -0.5
        elif signal == ReversionSignal.OVERSOLD:
            base_signal = 0.5
        elif signal == ReversionSignal.EXTREME_HIGH:
            base_signal = -0.8
        elif signal == ReversionSignal.EXTREME_LOW:
            base_signal = 0.8
        
        return base_signal * reversion_prob * confidence
    
    def _empty_event(self, timestamp: datetime, symbol: str, price: float) -> MeanReversionEvent:
        return MeanReversionEvent(
            timestamp=timestamp,
            symbol=symbol,
            signal=ReversionSignal.NONE,
            current_price=price,
            mean_price=price,
            std_dev=0.0,
            z_score=0.0,
            deviation_pct=0.0,
            reversion_probability=0.0,
            expected_reversion=0.0,
            confidence=0.0,
            trade_signal=0.0,
        )


def detect_mean_reversion(
    current_price: float,
    prices: List[float],
    symbol: str,
    detector: Optional[MeanReversionDetector] = None,
) -> MeanReversionEvent:
    detector = detector or MeanReversionDetector()
    return detector.detect(current_price, prices, symbol)
