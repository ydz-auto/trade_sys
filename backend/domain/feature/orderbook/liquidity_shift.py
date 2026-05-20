"""
Liquidity Shift - 流动性移动检测

检测流动性变化:
1. 流动性注入/撤出
2. 价格跟随移动
3. 流动性空洞检测
4. 预测性信号
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("feature.orderbook.liquidity_shift")


class ShiftType(str, Enum):
    INJECTION = "injection"
    WITHDRAWAL = "withdrawal"
    RELOCATION = "relocation"
    HOLE = "hole"
    NONE = "none"


@dataclass
class LiquidityShift:
    timestamp: datetime
    symbol: str
    shift_type: ShiftType
    
    bid_liquidity_before: float
    bid_liquidity_after: float
    bid_liquidity_delta: float
    
    ask_liquidity_before: float
    ask_liquidity_after: float
    ask_liquidity_delta: float
    
    shift_magnitude: float
    shift_direction: float
    
    price_impact_prediction: float
    
    is_significant: bool
    
    metadata: Dict[str, Any] = field(default_factory=dict)


def detect_liquidity_shift(
    prev_orderbook: Tuple[List[Tuple[float, float]], List[Tuple[float, float]]],
    curr_orderbook: Tuple[List[Tuple[float, float]], List[Tuple[float, float]]],
    symbol: str,
    significance_threshold: float = 0.2,
    depth_levels: int = 20,
) -> LiquidityShift:
    """
    检测流动性移动
    
    Args:
        prev_orderbook: (prev_bids, prev_asks)
        curr_orderbook: (curr_bids, curr_asks)
        symbol: 交易对
        significance_threshold: 显著性阈值
        depth_levels: 计算深度
    """
    timestamp = datetime.now()
    
    prev_bids, prev_asks = prev_orderbook
    curr_bids, curr_asks = curr_orderbook
    
    prev_bid_liq = sum(size for _, size in prev_bids[:depth_levels])
    prev_ask_liq = sum(size for _, size in prev_asks[:depth_levels])
    curr_bid_liq = sum(size for _, size in curr_bids[:depth_levels])
    curr_ask_liq = sum(size for _, size in curr_asks[:depth_levels])
    
    bid_delta = curr_bid_liq - prev_bid_liq
    ask_delta = curr_ask_liq - prev_ask_liq
    
    bid_change_pct = bid_delta / prev_bid_liq if prev_bid_liq > 0 else 0.0
    ask_change_pct = ask_delta / prev_ask_liq if prev_ask_liq > 0 else 0.0
    
    magnitude = np.sqrt(bid_change_pct ** 2 + ask_change_pct ** 2)
    
    direction = (bid_change_pct - ask_change_pct) / 2
    
    shift_type = _determine_shift_type(bid_change_pct, ask_change_pct)
    
    price_impact = direction * magnitude * 0.001
    
    is_significant = magnitude > significance_threshold
    
    return LiquidityShift(
        timestamp=timestamp,
        symbol=symbol,
        shift_type=shift_type,
        bid_liquidity_before=prev_bid_liq,
        bid_liquidity_after=curr_bid_liq,
        bid_liquidity_delta=bid_delta,
        ask_liquidity_before=prev_ask_liq,
        ask_liquidity_after=curr_ask_liq,
        ask_liquidity_delta=ask_delta,
        shift_magnitude=magnitude,
        shift_direction=direction,
        price_impact_prediction=price_impact,
        is_significant=is_significant,
    )


def _determine_shift_type(bid_change: float, ask_change: float) -> ShiftType:
    if bid_change > 0.1 and ask_change > 0.1:
        return ShiftType.INJECTION
    elif bid_change < -0.1 and ask_change < -0.1:
        return ShiftType.WITHDRAWAL
    elif abs(bid_change - ask_change) > 0.2:
        return ShiftType.RELOCATION
    elif bid_change < -0.3 or ask_change < -0.3:
        return ShiftType.HOLE
    else:
        return ShiftType.NONE


class LiquidityTracker:
    def __init__(self, history_size: int = 100):
        self._history_size = history_size
        self._history: Dict[str, List[LiquidityShift]] = {}
    
    def update(self, shift: LiquidityShift) -> Dict[str, Any]:
        symbol = shift.symbol
        
        if symbol not in self._history:
            self._history[symbol] = []
        
        self._history[symbol].append(shift)
        
        if len(self._history[symbol]) > self._history_size:
            self._history[symbol] = self._history[symbol][-self._history_size:]
        
        return self._analyze_pattern(symbol)
    
    def _analyze_pattern(self, symbol: str) -> Dict[str, Any]:
        history = self._history.get(symbol, [])
        
        if len(history) < 5:
            return {"pattern": "unknown", "confidence": 0.0}
        
        recent = history[-20:]
        
        injections = sum(1 for s in recent if s.shift_type == ShiftType.INJECTION)
        withdrawals = sum(1 for s in recent if s.shift_type == ShiftType.WITHDRAWAL)
        
        if injections > withdrawals * 2:
            pattern = "accumulation"
            confidence = min(1.0, injections / len(recent))
        elif withdrawals > injections * 2:
            pattern = "distribution"
            confidence = min(1.0, withdrawals / len(recent))
        else:
            pattern = "neutral"
            confidence = 0.5
        
        return {
            "pattern": pattern,
            "confidence": confidence,
            "injection_count": injections,
            "withdrawal_count": withdrawals,
        }
