"""
Depth Pressure - 深度压力计算

计算订单簿深度压力:
1. 买卖压力对比
2. 深度加权压力
3. 压力梯度
4. 支撑/阻力强度
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from domain.logging import get_logger

logger = get_logger("feature.orderbook.depth_pressure")


@dataclass
class DepthPressure:
    timestamp: datetime
    symbol: str
    
    bid_pressure: float
    ask_pressure: float
    net_pressure: float
    
    bid_depth: float
    ask_depth: float
    depth_ratio: float
    
    bid_pressure_gradient: float
    ask_pressure_gradient: float
    
    support_strength: float
    resistance_strength: float
    
    pressure_signal: float
    
    skew: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def calculate_depth_pressure(
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    symbol: str,
    depth_levels: int = 20,
    price_reference: Optional[float] = None,
    decay_factor: float = 0.95,
) -> DepthPressure:
    """
    计算深度压力
    
    Args:
        bids: 买单列表
        asks: 危单列表
        symbol: 交易对
        depth_levels: 计算深度
        price_reference: 参考价格（默认使用中间价）
        decay_factor: 距离衰减因子
    """
    timestamp = datetime.now()
    
    if not bids or not asks:
        return DepthPressure(
            timestamp=timestamp,
            symbol=symbol,
            bid_pressure=0.0,
            ask_pressure=0.0,
            net_pressure=0.0,
            bid_depth=0.0,
            ask_depth=0.0,
            depth_ratio=1.0,
            bid_pressure_gradient=0.0,
            ask_pressure_gradient=0.0,
            support_strength=0.0,
            resistance_strength=0.0,
            pressure_signal=0.0,
            skew=0.0,
        )
    
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = price_reference or (best_bid + best_ask) / 2
    
    bid_pressure, bid_depth, bid_gradient = _calculate_side_pressure(
        bids, mid_price, "bid", depth_levels, decay_factor
    )
    ask_pressure, ask_depth, ask_gradient = _calculate_side_pressure(
        asks, mid_price, "ask", depth_levels, decay_factor
    )
    
    total_pressure = bid_pressure + ask_pressure
    if total_pressure > 0:
        net_pressure = (bid_pressure - ask_pressure) / total_pressure
    else:
        net_pressure = 0.0
    
    depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0
    
    support_strength = bid_pressure * (1 - bid_gradient)
    resistance_strength = ask_pressure * (1 - ask_gradient)
    
    pressure_signal = np.tanh(net_pressure * 2)
    
    total_depth = bid_depth + ask_depth
    if total_depth > 0:
        skew = (bid_depth - ask_depth) / total_depth
    else:
        skew = 0.0
    
    return DepthPressure(
        timestamp=timestamp,
        symbol=symbol,
        bid_pressure=bid_pressure,
        ask_pressure=ask_pressure,
        net_pressure=net_pressure,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        depth_ratio=depth_ratio,
        bid_pressure_gradient=bid_gradient,
        ask_pressure_gradient=ask_gradient,
        support_strength=support_strength,
        resistance_strength=resistance_strength,
        pressure_signal=pressure_signal,
        skew=skew,
    )


def _calculate_side_pressure(
    orders: List[Tuple[float, float]],
    reference_price: float,
    side: str,
    depth_levels: int,
    decay_factor: float,
) -> Tuple[float, float, float]:
    orders = orders[:depth_levels]
    
    if not orders:
        return 0.0, 0.0, 0.0
    
    pressures = []
    depths = []
    
    for i, (price, size) in enumerate(orders):
        distance = abs(price - reference_price) / reference_price if reference_price > 0 else 0
        
        decay = decay_factor ** i
        
        pressure = size * decay * (1 - distance)
        pressures.append(pressure)
        depths.append(size * decay)
    
    total_pressure = sum(pressures)
    total_depth = sum(depths)
    
    if len(pressures) >= 2:
        gradient = (pressures[0] - pressures[-1]) / len(pressures)
    else:
        gradient = 0.0
    
    return total_pressure, total_depth, gradient


class DepthPressureTracker:
    def __init__(self, history_size: int = 100):
        self._history_size = history_size
        self._history: Dict[str, List[DepthPressure]] = {}
    
    def update(self, pressure: DepthPressure) -> Dict[str, Any]:
        symbol = pressure.symbol
        
        if symbol not in self._history:
            self._history[symbol] = []
        
        self._history[symbol].append(pressure)
        
        if len(self._history[symbol]) > self._history_size:
            self._history[symbol] = self._history[symbol][-self._history_size:]
        
        return self._analyze_pressure_trend(symbol)
    
    def _analyze_pressure_trend(self, symbol: str) -> Dict[str, Any]:
        history = self._history.get(symbol, [])
        
        if len(history) < 5:
            return {"trend": "unknown", "signal": 0.0}
        
        signals = [p.pressure_signal for p in history[-20:]]
        
        avg_signal = np.mean(signals)
        signal_trend = signals[-1] - signals[0] if len(signals) > 1 else 0.0
        
        if avg_signal > 0.2:
            trend = "bullish"
        elif avg_signal < -0.2:
            trend = "bearish"
        else:
            trend = "neutral"
        
        return {
            "trend": trend,
            "signal": avg_signal,
            "signal_trend": signal_trend,
            "support_strength": history[-1].support_strength,
            "resistance_strength": history[-1].resistance_strength,
        }
