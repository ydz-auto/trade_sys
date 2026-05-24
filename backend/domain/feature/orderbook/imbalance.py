"""
Orderbook Imbalance - 买卖盘失衡检测

核心 Alpha 来源:
1. 买卖盘数量失衡
2. 买卖盘金额失衡
3. 失衡变化率
4. 失衡信号强度
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

import logging

logger = logging.getLogger(__name__)


@dataclass
class OrderbookImbalance:
    timestamp: datetime
    symbol: str
    
    bid_volume: float
    ask_volume: float
    bid_notional: float
    ask_notional: float
    
    volume_imbalance: float
    notional_imbalance: float
    
    imbalance_score: float
    imbalance_signal: float
    
    bid_levels: int
    ask_levels: int
    
    depth_ratio: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def calculate_imbalance(
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    symbol: str,
    depth_levels: int = 20,
    weight_decay: float = 0.95,
) -> OrderbookImbalance:
    """
    计算订单簿失衡
    
    Args:
        bids: [(price, size), ...] 买单列表
        asks: [(price, size), ...] 卖单列表
        symbol: 交易对
        depth_levels: 计算深度
        weight_decay: 权重衰减因子
    """
    timestamp = datetime.now()
    
    bids = bids[:depth_levels]
    asks = asks[:depth_levels]
    
    weights = np.array([weight_decay ** i for i in range(depth_levels)])
    
    bid_sizes = np.array([size for _, size in bids])
    ask_sizes = np.array([size for _, size in asks])
    bid_prices = np.array([price for price, _ in bids])
    ask_prices = np.array([price for price, _ in asks])
    
    if len(bid_sizes) < depth_levels:
        bid_sizes = np.pad(bid_sizes, (0, depth_levels - len(bid_sizes)))
    if len(ask_sizes) < depth_levels:
        ask_sizes = np.pad(ask_sizes, (0, depth_levels - len(ask_sizes)))
    
    bid_volume = float(np.sum(bid_sizes * weights[:len(bid_sizes)]))
    ask_volume = float(np.sum(ask_sizes * weights[:len(ask_sizes)]))
    
    bid_notional = float(np.sum(bid_sizes * bid_prices * weights[:len(bid_sizes)])) if len(bid_prices) > 0 else 0.0
    ask_notional = float(np.sum(ask_sizes * ask_prices * weights[:len(ask_sizes)])) if len(ask_prices) > 0 else 0.0
    
    total_volume = bid_volume + ask_volume
    total_notional = bid_notional + ask_notional
    
    if total_volume > 0:
        volume_imbalance = (bid_volume - ask_volume) / total_volume
    else:
        volume_imbalance = 0.0
    
    if total_notional > 0:
        notional_imbalance = (bid_notional - ask_notional) / total_notional
    else:
        notional_imbalance = 0.0
    
    imbalance_score = 0.5 * volume_imbalance + 0.5 * notional_imbalance
    
    imbalance_signal = np.tanh(imbalance_score * 3)
    
    depth_ratio = bid_volume / ask_volume if ask_volume > 0 else 1.0
    
    return OrderbookImbalance(
        timestamp=timestamp,
        symbol=symbol,
        bid_volume=bid_volume,
        ask_volume=ask_volume,
        bid_notional=bid_notional,
        ask_notional=ask_notional,
        volume_imbalance=volume_imbalance,
        notional_imbalance=notional_imbalance,
        imbalance_score=imbalance_score,
        imbalance_signal=imbalance_signal,
        bid_levels=len(bids),
        ask_levels=len(asks),
        depth_ratio=depth_ratio,
    )


class ImbalanceTracker:
    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._history: Dict[str, List[OrderbookImbalance]] = {}
    
    def update(self, imbalance: OrderbookImbalance) -> Dict[str, Any]:
        symbol = imbalance.symbol
        
        if symbol not in self._history:
            self._history[symbol] = []
        
        self._history[symbol].append(imbalance)
        
        if len(self._history[symbol]) > self._window_size:
            self._history[symbol] = self._history[symbol][-self._window_size:]
        
        return self._analyze_trend(symbol)
    
    def _analyze_trend(self, symbol: str) -> Dict[str, Any]:
        history = self._history.get(symbol, [])
        
        if len(history) < 2:
            return {"trend": "unknown", "momentum": 0.0}
        
        scores = [h.imbalance_score for h in history[-20:]]
        
        if len(scores) < 2:
            return {"trend": "unknown", "momentum": 0.0}
        
        momentum = scores[-1] - scores[0]
        
        if momentum > 0.1:
            trend = "bullish"
        elif momentum < -0.1:
            trend = "bearish"
        else:
            trend = "neutral"
        
        return {
            "trend": trend,
            "momentum": momentum,
            "current_score": scores[-1],
            "avg_score": np.mean(scores),
            "std_score": np.std(scores),
        }
