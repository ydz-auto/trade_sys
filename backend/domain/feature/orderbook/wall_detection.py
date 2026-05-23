"""
Wall Detection - 订单墙检测

检测大额挂单（冰山订单）:
1. 价格聚集检测
2. 大额订单识别
3. 墙强度评估
4. 突破概率计算
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from domain.logging import get_logger

logger = get_logger("feature.orderbook.wall_detection")


@dataclass
class WallInfo:
    price: float
    side: str
    size: float
    notional: float
    
    relative_size: float
    wall_strength: float
    
    distance_from_mid: float
    distance_percent: float
    
    is_iceberg: bool
    iceberg_probability: float
    
    breakthrough_probability: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WallDetection:
    timestamp: datetime
    symbol: str
    mid_price: float
    
    bid_walls: List[WallInfo]
    ask_walls: List[WallInfo]
    
    strongest_bid_wall: Optional[WallInfo]
    strongest_ask_wall: Optional[WallInfo]
    
    wall_pressure: float
    support_resistance_score: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def detect_walls(
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    symbol: str,
    wall_threshold: float = 3.0,
    iceberg_threshold: float = 5.0,
    price_tolerance: float = 0.001,
) -> WallDetection:
    """
    检测订单墙
    
    Args:
        bids: 买单列表
        asks: 卖单列表
        symbol: 交易对
        wall_threshold: 墙阈值（相对于平均大小的倍数）
        iceberg_threshold: 冰山订单阈值
        price_tolerance: 价格聚集容差
    """
    timestamp = datetime.now()
    
    if not bids or not asks:
        return WallDetection(
            timestamp=timestamp,
            symbol=symbol,
            mid_price=0.0,
            bid_walls=[],
            ask_walls=[],
            strongest_bid_wall=None,
            strongest_ask_wall=None,
            wall_pressure=0.0,
            support_resistance_score=0.0,
        )
    
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = (best_bid + best_ask) / 2
    
    bid_walls = _detect_side_walls(
        bids, "bid", mid_price, wall_threshold, iceberg_threshold
    )
    ask_walls = _detect_side_walls(
        asks, "ask", mid_price, wall_threshold, iceberg_threshold
    )
    
    strongest_bid = max(bid_walls, key=lambda w: w.wall_strength) if bid_walls else None
    strongest_ask = max(ask_walls, key=lambda w: w.wall_strength) if ask_walls else None
    
    bid_wall_strength = sum(w.wall_strength for w in bid_walls)
    ask_wall_strength = sum(w.wall_strength for w in ask_walls)
    
    total_strength = bid_wall_strength + ask_wall_strength
    if total_strength > 0:
        wall_pressure = (ask_wall_strength - bid_wall_strength) / total_strength
    else:
        wall_pressure = 0.0
    
    if strongest_bid and strongest_ask:
        support_dist = strongest_bid.distance_percent
        resistance_dist = strongest_ask.distance_percent
        
        if support_dist < resistance_dist:
            support_resistance_score = -strongest_bid.wall_strength
        else:
            support_resistance_score = strongest_ask.wall_strength
    elif strongest_bid:
        support_resistance_score = -strongest_bid.wall_strength
    elif strongest_ask:
        support_resistance_score = strongest_ask.wall_strength
    else:
        support_resistance_score = 0.0
    
    return WallDetection(
        timestamp=timestamp,
        symbol=symbol,
        mid_price=mid_price,
        bid_walls=bid_walls,
        ask_walls=ask_walls,
        strongest_bid_wall=strongest_bid,
        strongest_ask_wall=strongest_ask,
        wall_pressure=wall_pressure,
        support_resistance_score=support_resistance_score,
    )


def _detect_side_walls(
    orders: List[Tuple[float, float]],
    side: str,
    mid_price: float,
    wall_threshold: float,
    iceberg_threshold: float,
) -> List[WallInfo]:
    if not orders:
        return []
    
    sizes = np.array([size for _, size in orders])
    prices = np.array([price for price, _ in orders])
    
    avg_size = np.mean(sizes)
    std_size = np.std(sizes)
    
    walls = []
    
    for i, (price, size) in enumerate(orders):
        relative_size = size / avg_size if avg_size > 0 else 1.0
        
        if relative_size < wall_threshold:
            continue
        
        distance = abs(price - mid_price)
        distance_pct = distance / mid_price if mid_price > 0 else 0.0
        
        wall_strength = relative_size * (1 - distance_pct * 10)
        wall_strength = max(0, wall_strength)
        
        is_iceberg = relative_size > iceberg_threshold
        iceberg_prob = min(1.0, relative_size / iceberg_threshold) if is_iceberg else 0.0
        
        breakthrough_prob = 1.0 / (1.0 + relative_size)
        
        wall = WallInfo(
            price=price,
            side=side,
            size=size,
            notional=price * size,
            relative_size=relative_size,
            wall_strength=wall_strength,
            distance_from_mid=distance,
            distance_percent=distance_pct,
            is_iceberg=is_iceberg,
            iceberg_probability=iceberg_prob,
            breakthrough_probability=breakthrough_prob,
        )
        walls.append(wall)
    
    return walls
