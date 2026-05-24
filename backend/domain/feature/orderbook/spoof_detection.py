"""
Spoof Detection - 假挂单检测

检测市场操纵行为:
1. 快速挂撤单
2. 层级诱导检测
3. 假墙识别
4. 操纵概率评估
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

import logging

logger = logging.getLogger(__name__)


class SpoofType(str, Enum):
    LAYERING = "layering"
    SPOOFING = "spoofing"
    PUMP_DUMP = "pump_dump"
    NONE = "none"


@dataclass
class SpoofIndicators:
    cancel_rate: float
    order_lifetime_avg: float
    fill_rate: float
    
    layering_score: float
    spoofing_score: float
    
    suspicious_orders: int
    suspicious_volume: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpoofDetection:
    timestamp: datetime
    symbol: str
    
    spoof_type: SpoofType
    spoof_probability: float
    
    indicators: SpoofIndicators
    
    bid_manipulation_score: float
    ask_manipulation_score: float
    
    net_manipulation_signal: float
    
    warning_level: str
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def detect_spoofing(
    order_events: List[Dict[str, Any]],
    current_orderbook: Tuple[List[Tuple[float, float]], List[Tuple[float, float]]],
    symbol: str,
    lookback_seconds: int = 60,
    cancel_threshold: float = 0.7,
    layering_threshold: float = 0.5,
) -> SpoofDetection:
    """
    检测假挂单行为
    
    Args:
        order_events: 订单事件列表 [{type, side, price, size, timestamp, lifetime}, ...]
        current_orderbook: (bids, asks)
        symbol: 交易对
        lookback_seconds: 回看时间
        cancel_threshold: 撤单率阈值
        layering_threshold: 层级诱导阈值
    """
    timestamp = datetime.now()
    cutoff = timestamp - timedelta(seconds=lookback_seconds)
    
    recent_events = [
        e for e in order_events
        if e.get("timestamp", timestamp) >= cutoff
    ]
    
    if len(recent_events) < 10:
        return _empty_detection(timestamp, symbol)
    
    indicators = _calculate_indicators(recent_events)
    
    spoofing_score = _calculate_spoofing_score(indicators, cancel_threshold)
    layering_score = _calculate_layering_score(indicators, layering_threshold)
    
    bids, asks = current_orderbook
    bid_manip = _detect_side_manipulation(recent_events, "bid", bids)
    ask_manip = _detect_side_manipulation(recent_events, "ask", asks)
    
    net_signal = ask_manip - bid_manip
    
    spoof_type, spoof_prob = _determine_spoof_type(
        spoofing_score, layering_score, bid_manip, ask_manip
    )
    
    if spoof_prob > 0.7:
        warning_level = "high"
    elif spoof_prob > 0.4:
        warning_level = "medium"
    else:
        warning_level = "low"
    
    return SpoofDetection(
        timestamp=timestamp,
        symbol=symbol,
        spoof_type=spoof_type,
        spoof_probability=spoof_prob,
        indicators=indicators,
        bid_manipulation_score=bid_manip,
        ask_manipulation_score=ask_manip,
        net_manipulation_signal=net_signal,
        warning_level=warning_level,
    )


def _empty_detection(timestamp: datetime, symbol: str) -> SpoofDetection:
    return SpoofDetection(
        timestamp=timestamp,
        symbol=symbol,
        spoof_type=SpoofType.NONE,
        spoof_probability=0.0,
        indicators=SpoofIndicators(
            cancel_rate=0.0,
            order_lifetime_avg=0.0,
            fill_rate=0.0,
            layering_score=0.0,
            spoofing_score=0.0,
            suspicious_orders=0,
            suspicious_volume=0.0,
        ),
        bid_manipulation_score=0.0,
        ask_manipulation_score=0.0,
        net_manipulation_signal=0.0,
        warning_level="low",
    )


def _calculate_indicators(events: List[Dict[str, Any]]) -> SpoofIndicators:
    cancels = [e for e in events if e.get("type") == "cancel"]
    new_orders = [e for e in events if e.get("type") == "new"]
    fills = [e for e in events if e.get("type") == "fill"]
    
    total = len(cancels) + len(new_orders) + len(fills)
    cancel_rate = len(cancels) / total if total > 0 else 0.0
    fill_rate = len(fills) / total if total > 0 else 0.0
    
    lifetimes = [e.get("lifetime", 0) for e in cancels]
    avg_lifetime = np.mean(lifetimes) if lifetimes else 0.0
    
    suspicious = [
        e for e in cancels
        if e.get("lifetime", 0) < 1.0 and e.get("size", 0) > 1000
    ]
    
    suspicious_volume = sum(e.get("size", 0) for e in suspicious)
    
    layering_score = len(suspicious) / len(cancels) if cancels else 0.0
    
    spoofing_score = cancel_rate * (1 - fill_rate)
    
    return SpoofIndicators(
        cancel_rate=cancel_rate,
        order_lifetime_avg=avg_lifetime,
        fill_rate=fill_rate,
        layering_score=layering_score,
        spoofing_score=spoofing_score,
        suspicious_orders=len(suspicious),
        suspicious_volume=suspicious_volume,
    )


def _calculate_spoofing_score(indicators: SpoofIndicators, threshold: float) -> float:
    score = 0.0
    
    if indicators.cancel_rate > threshold:
        score += 0.4
    
    if indicators.order_lifetime_avg < 2.0:
        score += 0.3
    
    if indicators.fill_rate < 0.1:
        score += 0.3
    
    return min(1.0, score)


def _calculate_layering_score(indicators: SpoofIndicators, threshold: float) -> float:
    return min(1.0, indicators.layering_score)


def _detect_side_manipulation(
    events: List[Dict[str, Any]],
    side: str,
    orders: List[Tuple[float, float]],
) -> float:
    side_events = [e for e in events if e.get("side") == side]
    
    if not side_events:
        return 0.0
    
    cancels = [e for e in side_events if e.get("type") == "cancel"]
    short_cancels = [e for e in cancels if e.get("lifetime", 0) < 1.0]
    
    return len(short_cancels) / len(side_events)


def _determine_spoof_type(
    spoofing_score: float,
    layering_score: float,
    bid_manip: float,
    ask_manip: float,
) -> Tuple[SpoofType, float]:
    scores = {
        SpoofType.SPOOFING: spoofing_score,
        SpoofType.LAYERING: layering_score,
        SpoofType.PUMP_DUMP: max(bid_manip, ask_manip) * 0.8,
    }
    
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    
    if best_score < 0.3:
        return SpoofType.NONE, best_score
    
    return best_type, best_score
