"""
Panic Detection - 恐慌检测

检测市场恐慌行为:
1. 快速价格下跌
2. 大量卖单涌入
3. 流动性枯竭
4. 连锁反应
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("behaviour.panic")


class PanicLevel(str, Enum):
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class PanicEvent:
    timestamp: datetime
    symbol: str
    level: PanicLevel
    
    price_drop_pct: float
    velocity: float
    acceleration: float
    
    sell_volume_ratio: float
    liquidity_drop_pct: float
    
    panic_score: float
    is_cascading: bool
    
    signal: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class PanicDetector:
    def __init__(
        self,
        velocity_threshold: float = 0.02,
        acceleration_threshold: float = 0.01,
        sell_ratio_threshold: float = 0.8,
        lookback_periods: int = 20,
    ):
        self._velocity_threshold = velocity_threshold
        self._acceleration_threshold = acceleration_threshold
        self._sell_ratio_threshold = sell_ratio_threshold
        self._lookback = lookback_periods
        
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[Dict[str, float]]] = {}
        
        logger.info("PanicDetector initialized")
    
    def detect(
        self,
        current_price: float,
        trades: List[Dict[str, Any]],
        orderbook: tuple,
        symbol: str,
    ) -> PanicEvent:
        timestamp = datetime.now()
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(current_price)
        if len(self._price_history[symbol]) > self._lookback:
            self._price_history[symbol] = self._price_history[symbol][-self._lookback:]
        
        prices = self._price_history[symbol]
        
        if len(prices) < 3:
            return self._empty_event(timestamp, symbol)
        
        price_drop = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0.0
        
        velocity = self._calculate_velocity(prices)
        acceleration = self._calculate_acceleration(prices)
        
        buy_vol = sum(t["size"] for t in trades if t.get("side") == "buy")
        sell_vol = sum(t["size"] for t in trades if t.get("side") == "sell")
        total_vol = buy_vol + sell_vol
        sell_ratio = sell_vol / total_vol if total_vol > 0 else 0.5
        
        bids, asks = orderbook
        bid_liquidity = sum(size for _, size in bids[:10])
        ask_liquidity = sum(size for _, size in asks[:10])
        total_liq = bid_liquidity + ask_liquidity
        
        liquidity_drop = 0.0
        if hasattr(self, '_prev_liquidity') and self._prev_liquidity.get(symbol, 0) > 0:
            prev_liq = self._prev_liquidity[symbol]
            liquidity_drop = (prev_liq - total_liq) / prev_liq
        
        self._prev_liquidity = getattr(self, '_prev_liquidity', {})
        self._prev_liquidity[symbol] = total_liq
        
        panic_score = self._calculate_panic_score(
            price_drop, velocity, acceleration, sell_ratio, liquidity_drop
        )
        
        level = self._determine_level(panic_score)
        
        is_cascading = (
            acceleration < -self._acceleration_threshold and
            sell_ratio > self._sell_ratio_threshold
        )
        
        signal = -np.tanh(panic_score * 2) if panic_score > 0.3 else 0.0
        
        return PanicEvent(
            timestamp=timestamp,
            symbol=symbol,
            level=level,
            price_drop_pct=price_drop,
            velocity=velocity,
            acceleration=acceleration,
            sell_volume_ratio=sell_ratio,
            liquidity_drop_pct=liquidity_drop,
            panic_score=panic_score,
            is_cascading=is_cascading,
            signal=signal,
        )
    
    def _calculate_velocity(self, prices: List[float]) -> float:
        if len(prices) < 2:
            return 0.0
        return (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0.0
    
    def _calculate_acceleration(self, prices: List[float]) -> float:
        if len(prices) < 3:
            return 0.0
        v1 = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0.0
        v2 = (prices[-2] - prices[-3]) / prices[-3] if prices[-3] > 0 else 0.0
        return v1 - v2
    
    def _calculate_panic_score(
        self,
        price_drop: float,
        velocity: float,
        acceleration: float,
        sell_ratio: float,
        liquidity_drop: float,
    ) -> float:
        score = 0.0
        
        if price_drop < 0:
            score += abs(price_drop) * 5
        
        if velocity < -self._velocity_threshold:
            score += abs(velocity) * 10
        
        if acceleration < -self._acceleration_threshold:
            score += abs(acceleration) * 20
        
        if sell_ratio > self._sell_ratio_threshold:
            score += (sell_ratio - 0.5) * 2
        
        if liquidity_drop > 0.3:
            score += liquidity_drop
        
        return min(1.0, score)
    
    def _determine_level(self, score: float) -> PanicLevel:
        if score < 0.2:
            return PanicLevel.NONE
        elif score < 0.4:
            return PanicLevel.MILD
        elif score < 0.6:
            return PanicLevel.MODERATE
        elif score < 0.8:
            return PanicLevel.SEVERE
        else:
            return PanicLevel.EXTREME
    
    def _empty_event(self, timestamp: datetime, symbol: str) -> PanicEvent:
        return PanicEvent(
            timestamp=timestamp,
            symbol=symbol,
            level=PanicLevel.NONE,
            price_drop_pct=0.0,
            velocity=0.0,
            acceleration=0.0,
            sell_volume_ratio=0.5,
            liquidity_drop_pct=0.0,
            panic_score=0.0,
            is_cascading=False,
            signal=0.0,
        )


def detect_panic(
    current_price: float,
    trades: List[Dict[str, Any]],
    orderbook: tuple,
    symbol: str,
    detector: Optional[PanicDetector] = None,
) -> PanicEvent:
    detector = detector or PanicDetector()
    return detector.detect(current_price, trades, orderbook, symbol)
