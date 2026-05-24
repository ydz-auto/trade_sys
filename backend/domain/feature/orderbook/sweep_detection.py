"""
Sweep Detection - 吃单检测

检测市场吃单行为:
1. 快速消耗流动性
2. 吃单方向判断
3. 吃单强度评估
4. 潜在信号生成
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

import logging

logger = logging.getLogger(__name__)


class SweepType(str, Enum):
    BUY_SWEEP = "buy_sweep"
    SELL_SWEEP = "sell_sweep"
    DOUBLE_SWEEP = "double_sweep"
    NONE = "none"


@dataclass
class SweepEvent:
    timestamp: datetime
    symbol: str
    sweep_type: SweepType
    
    start_price: float
    end_price: float
    price_delta: float
    
    volume_swept: float
    levels_swept: int
    
    sweep_velocity: float
    sweep_intensity: float
    
    is_aggressive: bool
    is_exhaustion: bool
    
    signal: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SweepDetection:
    timestamp: datetime
    symbol: str
    
    recent_sweeps: List[SweepEvent]
    
    buy_sweep_count: int
    sell_sweep_count: int
    
    net_sweep_signal: float
    sweep_momentum: float
    
    aggressive_sweep_detected: bool
    exhaustion_detected: bool
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def detect_sweeps(
    trades: List[Dict[str, Any]],
    orderbook_bids: List[Tuple[float, float]],
    orderbook_asks: List[Tuple[float, float]],
    symbol: str,
    lookback: int = 50,
    sweep_threshold: float = 0.002,
    velocity_threshold: float = 10.0,
) -> SweepDetection:
    """
    检测吃单行为
    
    Args:
        trades: 最近成交列表 [{price, size, side, timestamp}, ...]
        orderbook_bids: 当前买单
        orderbook_asks: 当前危单
        symbol: 交易对
        lookback: 回看成交数
        sweep_threshold: 吃单价格阈值
        velocity_threshold: 吃单速度阈值
    """
    timestamp = datetime.now()
    
    trades = trades[-lookback:] if len(trades) > lookback else trades
    
    if len(trades) < 5:
        return SweepDetection(
            timestamp=timestamp,
            symbol=symbol,
            recent_sweeps=[],
            buy_sweep_count=0,
            sell_sweep_count=0,
            net_sweep_signal=0.0,
            sweep_momentum=0.0,
            aggressive_sweep_detected=False,
            exhaustion_detected=False,
        )
    
    sweeps = _identify_sweep_events(
        trades, orderbook_bids, orderbook_asks, 
        sweep_threshold, velocity_threshold
    )
    
    buy_sweeps = [s for s in sweeps if s.sweep_type == SweepType.BUY_SWEEP]
    sell_sweeps = [s for s in sweeps if s.sweep_type == SweepType.SELL_SWEEP]
    
    buy_count = len(buy_sweeps)
    sell_count = len(sell_sweeps)
    
    total_sweeps = buy_count + sell_count
    if total_sweeps > 0:
        net_signal = (buy_count - sell_count) / total_sweeps
    else:
        net_signal = 0.0
    
    if sweeps:
        recent_signals = [s.signal for s in sweeps[-10:]]
        momentum = np.mean(recent_signals) if recent_signals else 0.0
    else:
        momentum = 0.0
    
    aggressive = any(s.is_aggressive for s in sweeps[-5:]) if sweeps else False
    exhaustion = any(s.is_exhaustion for s in sweeps[-5:]) if sweeps else False
    
    return SweepDetection(
        timestamp=timestamp,
        symbol=symbol,
        recent_sweeps=sweeps,
        buy_sweep_count=buy_count,
        sell_sweep_count=sell_count,
        net_sweep_signal=net_signal,
        sweep_momentum=momentum,
        aggressive_sweep_detected=aggressive,
        exhaustion_detected=exhaustion,
    )


def _identify_sweep_events(
    trades: List[Dict[str, Any]],
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    price_threshold: float,
    velocity_threshold: float,
) -> List[SweepEvent]:
    sweeps = []
    
    if not trades:
        return sweeps
    
    i = 0
    while i < len(trades) - 1:
        trade = trades[i]
        side = trade.get("side", "unknown")
        
        if side not in ["buy", "sell"]:
            i += 1
            continue
        
        start_price = trade["price"]
        end_price = start_price
        volume = trade["size"]
        levels = 1
        
        j = i + 1
        while j < len(trades):
            next_trade = trades[j]
            
            if next_trade.get("side") != side:
                break
            
            price_change = abs(next_trade["price"] - end_price) / end_price if end_price > 0 else 0
            
            if price_change > price_threshold:
                end_price = next_trade["price"]
                volume += next_trade["size"]
                levels += 1
                j += 1
            else:
                break
        
        if levels >= 2:
            price_delta = abs(end_price - start_price)
            
            time_delta = 1.0
            velocity = price_delta / time_delta if time_delta > 0 else 0.0
            
            intensity = volume * levels
            
            is_aggressive = velocity > velocity_threshold
            
            is_exhaustion = levels >= 5 and intensity > velocity_threshold * 10
            
            if side == "buy":
                sweep_type = SweepType.BUY_SWEEP
                signal = min(1.0, intensity / 1000.0)
            else:
                sweep_type = SweepType.SELL_SWEEP
                signal = -min(1.0, intensity / 1000.0)
            
            sweep = SweepEvent(
                timestamp=trade.get("timestamp", datetime.now()),
                symbol=trade.get("symbol", ""),
                sweep_type=sweep_type,
                start_price=start_price,
                end_price=end_price,
                price_delta=price_delta,
                volume_swept=volume,
                levels_swept=levels,
                sweep_velocity=velocity,
                sweep_intensity=intensity,
                is_aggressive=is_aggressive,
                is_exhaustion=is_exhaustion,
                signal=signal,
            )
            sweeps.append(sweep)
            
            i = j
        else:
            i += 1
    
    return sweeps
