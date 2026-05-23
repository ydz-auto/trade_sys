"""
Orderbook Analyzer - 订单簿综合分析器

整合所有订单簿特征:
1. 失衡分析
2. 墙检测
3. 吃单检测
4. 假挂单检测
5. 微价格计算
6. 深度压力计算
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import numpy as np

from .imbalance import calculate_imbalance, ImbalanceTracker
from .wall_detection import detect_walls
from .sweep_detection import detect_sweeps
from .spoof_detection import detect_spoofing
from .liquidity_shift import detect_liquidity_shift, LiquidityTracker
from .microprice import calculate_microprice, MicropriceTracker
from .depth_pressure import calculate_depth_pressure, DepthPressureTracker

from domain.logging import get_logger

logger = get_logger("feature.orderbook.analyzer")


@dataclass
class OrderbookAnalysis:
    timestamp: datetime
    symbol: str
    
    imbalance: Any
    walls: Any
    sweeps: Any
    spoof: Any
    liquidity_shift: Any
    microprice: Any
    depth_pressure: Any
    
    composite_signal: float
    signal_confidence: float
    
    alpha_score: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderbookAnalyzer:
    def __init__(
        self,
        depth_levels: int = 20,
        history_size: int = 100,
    ):
        self._depth_levels = depth_levels
        
        self._imbalance_tracker = ImbalanceTracker(history_size)
        self._liquidity_tracker = LiquidityTracker(history_size)
        self._microprice_tracker = MicropriceTracker(history_size)
        self._pressure_tracker = DepthPressureTracker(history_size)
        
        self._prev_orderbook: Dict[str, Tuple[List, List]] = {}
        self._trade_history: Dict[str, List[Dict]] = {}
        self._order_events: Dict[str, List[Dict]] = {}
        
        logger.info("OrderbookAnalyzer initialized")
    
    def analyze(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        symbol: str,
        trades: Optional[List[Dict[str, Any]]] = None,
        order_events: Optional[List[Dict[str, Any]]] = None,
    ) -> OrderbookAnalysis:
        """
        综合分析订单簿
        """
        timestamp = datetime.now()
        
        imbalance = calculate_imbalance(bids, asks, symbol, self._depth_levels)
        imbalance_trend = self._imbalance_tracker.update(imbalance)
        
        walls = detect_walls(bids, asks, symbol)
        
        sweep_trades = trades or self._trade_history.get(symbol, [])
        sweeps = detect_sweeps(sweep_trades, bids, asks, symbol)
        
        spoof_events = order_events or self._order_events.get(symbol, [])
        spoof = detect_spoofing(spoof_events, (bids, asks), symbol)
        
        prev_book = self._prev_orderbook.get(symbol)
        if prev_book:
            liquidity_shift = detect_liquidity_shift(prev_book, (bids, asks), symbol)
            liquidity_pattern = self._liquidity_tracker.update(liquidity_shift)
        else:
            liquidity_shift = None
            liquidity_pattern = {"pattern": "unknown"}
        
        microprice = calculate_microprice(bids, asks, symbol, imbalance.imbalance_score)
        microprice_trend = self._microprice_tracker.update(microprice)
        
        depth_pressure = calculate_depth_pressure(bids, asks, symbol, self._depth_levels)
        pressure_trend = self._pressure_tracker.update(depth_pressure)
        
        composite_signal = self._calculate_composite_signal(
            imbalance, walls, sweeps, spoof, microprice, depth_pressure
        )
        
        signal_confidence = self._calculate_confidence(
            imbalance, walls, spoof, microprice
        )
        
        alpha_score = composite_signal * signal_confidence
        
        self._prev_orderbook[symbol] = (bids, asks)
        
        return OrderbookAnalysis(
            timestamp=timestamp,
            symbol=symbol,
            imbalance=imbalance,
            walls=walls,
            sweeps=sweeps,
            spoof=spoof,
            liquidity_shift=liquidity_shift,
            microprice=microprice,
            depth_pressure=depth_pressure,
            composite_signal=composite_signal,
            signal_confidence=signal_confidence,
            alpha_score=alpha_score,
            metadata={
                "imbalance_trend": imbalance_trend,
                "liquidity_pattern": liquidity_pattern,
                "microprice_trend": microprice_trend,
                "pressure_trend": pressure_trend,
            },
        )
    
    def _calculate_composite_signal(
        self,
        imbalance: Any,
        walls: Any,
        sweeps: Any,
        spoof: Any,
        microprice: Any,
        depth_pressure: Any,
    ) -> float:
        signals = []
        weights = []
        
        signals.append(imbalance.imbalance_signal)
        weights.append(0.25)
        
        signals.append(walls.wall_pressure)
        weights.append(0.15)
        
        signals.append(sweeps.net_sweep_signal)
        weights.append(0.20)
        
        signals.append(-spoof.net_manipulation_signal)
        weights.append(0.10)
        
        signals.append(microprice.microprice_displacement)
        weights.append(0.15)
        
        signals.append(depth_pressure.pressure_signal)
        weights.append(0.15)
        
        total_weight = sum(weights)
        composite = sum(s * w for s, w in zip(signals, weights)) / total_weight
        
        return np.clip(composite, -1.0, 1.0)
    
    def _calculate_confidence(
        self,
        imbalance: Any,
        walls: Any,
        spoof: Any,
        microprice: Any,
    ) -> float:
        confidence = 1.0
        
        if spoof.spoof_probability > 0.5:
            confidence *= 0.5
        
        confidence *= microprice.value_confidence
        
        if imbalance.bid_levels < 5 or imbalance.ask_levels < 5:
            confidence *= 0.7
        
        return np.clip(confidence, 0.0, 1.0)
    
    def update_trades(self, symbol: str, trades: List[Dict[str, Any]]) -> None:
        if symbol not in self._trade_history:
            self._trade_history[symbol] = []
        self._trade_history[symbol].extend(trades)
        self._trade_history[symbol] = self._trade_history[symbol][-500:]
    
    def update_order_events(self, symbol: str, events: List[Dict[str, Any]]) -> None:
        if symbol not in self._order_events:
            self._order_events[symbol] = []
        self._order_events[symbol].extend(events)
        self._order_events[symbol] = self._order_events[symbol][-500:]
    
    def get_analysis_summary(self, analysis: OrderbookAnalysis) -> Dict[str, Any]:
        return {
            "symbol": analysis.symbol,
            "timestamp": analysis.timestamp.isoformat(),
            "composite_signal": analysis.composite_signal,
            "signal_confidence": analysis.signal_confidence,
            "alpha_score": analysis.alpha_score,
            "imbalance": {
                "score": analysis.imbalance.imbalance_score,
                "signal": analysis.imbalance.imbalance_signal,
            },
            "walls": {
                "bid_walls": len(analysis.walls.bid_walls),
                "ask_walls": len(analysis.walls.ask_walls),
                "pressure": analysis.walls.wall_pressure,
            },
            "sweeps": {
                "buy_count": analysis.sweeps.buy_sweep_count,
                "sell_count": analysis.sweeps.sell_sweep_count,
                "net_signal": analysis.sweeps.net_sweep_signal,
            },
            "spoof": {
                "type": analysis.spoof.spoof_type.value,
                "probability": analysis.spoof.spoof_probability,
                "warning": analysis.spoof.warning_level,
            },
            "microprice": {
                "value": analysis.microprice.microprice,
                "displacement": analysis.microprice.microprice_displacement,
            },
            "depth_pressure": {
                "net": analysis.depth_pressure.net_pressure,
                "signal": analysis.depth_pressure.pressure_signal,
            },
        }
