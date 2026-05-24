"""
Microprice - 微价格计算

计算真实均衡价格:
1. 加权中间价
2. 流动性加权价格
3. 不平衡调整价格
4. 预测性价格
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

import logging

logger = logging.getLogger(__name__)


@dataclass
class Microprice:
    timestamp: datetime
    symbol: str
    
    best_bid: float
    best_ask: float
    mid_price: float
    spread: float
    
    weighted_mid: float
    imbalance_adjusted_mid: float
    
    microprice: float
    microprice_displacement: float
    
    bid_weight: float
    ask_weight: float
    
    fair_value: float
    value_confidence: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def calculate_microprice(
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    symbol: str,
    imbalance: Optional[float] = None,
    depth_levels: int = 5,
) -> Microprice:
    """
    计算微价格
    
    Args:
        bids: 买单列表
        asks: 危单列表
        symbol: 交易对
        imbalance: 外部计算的失衡值
        depth_levels: 计算深度
    """
    timestamp = datetime.now()
    
    if not bids or not asks:
        return Microprice(
            timestamp=timestamp,
            symbol=symbol,
            best_bid=0.0,
            best_ask=0.0,
            mid_price=0.0,
            spread=0.0,
            weighted_mid=0.0,
            imbalance_adjusted_mid=0.0,
            microprice=0.0,
            microprice_displacement=0.0,
            bid_weight=0.5,
            ask_weight=0.5,
            fair_value=0.0,
            value_confidence=0.0,
        )
    
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = (best_bid + best_ask) / 2
    spread = best_ask - best_bid
    
    bid_sizes = np.array([size for _, size in bids[:depth_levels]])
    ask_sizes = np.array([size for _, size in asks[:depth_levels]])
    
    bid_prices = np.array([price for price, _ in bids[:depth_levels]])
    ask_prices = np.array([price for price, _ in asks[:depth_levels]])
    
    total_bid_size = np.sum(bid_sizes)
    total_ask_size = np.sum(ask_sizes)
    total_size = total_bid_size + total_ask_size
    
    if total_size > 0:
        bid_weight = total_bid_size / total_size
        ask_weight = total_ask_size / total_size
    else:
        bid_weight = 0.5
        ask_weight = 0.5
    
    if total_bid_size > 0 and total_ask_size > 0:
        weighted_bid = np.sum(bid_prices * bid_sizes) / total_bid_size
        weighted_ask = np.sum(ask_prices * ask_sizes) / total_ask_size
        weighted_mid = (weighted_bid + weighted_ask) / 2
    else:
        weighted_mid = mid_price
    
    if imbalance is None:
        imbalance = (total_bid_size - total_ask_size) / total_size if total_size > 0 else 0.0
    
    imbalance_adjusted_mid = mid_price + imbalance * spread / 2
    
    microprice = mid_price + (bid_weight - ask_weight) * spread / 2
    
    displacement = (microprice - mid_price) / spread if spread > 0 else 0.0
    
    fair_value = 0.4 * microprice + 0.3 * imbalance_adjusted_mid + 0.3 * weighted_mid
    
    value_confidence = 1.0 - abs(displacement)
    
    return Microprice(
        timestamp=timestamp,
        symbol=symbol,
        best_bid=best_bid,
        best_ask=best_ask,
        mid_price=mid_price,
        spread=spread,
        weighted_mid=weighted_mid,
        imbalance_adjusted_mid=imbalance_adjusted_mid,
        microprice=microprice,
        microprice_displacement=displacement,
        bid_weight=bid_weight,
        ask_weight=ask_weight,
        fair_value=fair_value,
        value_confidence=value_confidence,
    )


class MicropriceTracker:
    def __init__(self, history_size: int = 100):
        self._history_size = history_size
        self._history: Dict[str, List[Microprice]] = {}
    
    def update(self, microprice: Microprice) -> Dict[str, Any]:
        symbol = microprice.symbol
        
        if symbol not in self._history:
            self._history[symbol] = []
        
        self._history[symbol].append(microprice)
        
        if len(self._history[symbol]) > self._history_size:
            self._history[symbol] = self._history[symbol][-self._history_size:]
        
        return self._analyze_displacement(symbol)
    
    def _analyze_displacement(self, symbol: str) -> Dict[str, Any]:
        history = self._history.get(symbol, [])
        
        if len(history) < 5:
            return {"trend": "unknown", "signal": 0.0}
        
        displacements = [m.microprice_displacement for m in history[-20:]]
        
        avg_displacement = np.mean(displacements)
        trend_displacement = displacements[-1] - displacements[0] if len(displacements) > 1 else 0.0
        
        if avg_displacement > 0.1:
            trend = "bullish"
        elif avg_displacement < -0.1:
            trend = "bearish"
        else:
            trend = "neutral"
        
        signal = np.tanh(avg_displacement * 5)
        
        return {
            "trend": trend,
            "signal": signal,
            "avg_displacement": avg_displacement,
            "trend_displacement": trend_displacement,
        }
