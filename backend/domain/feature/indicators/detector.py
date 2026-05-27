from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .panic import PanicDetector, PanicEvent
from .absorption import AbsorptionDetector, AbsorptionEvent
from .breakout import BreakoutDetector, BreakoutEvent
from .liquidation_cascade import LiquidationCascadeDetector, LiquidationCascadeEvent
from .trend_exhaustion import TrendExhaustionDetector, TrendExhaustionEvent
from .mean_reversion import MeanReversionDetector, MeanReversionEvent
from .trade_pressure import TradePressureDetector, TradePressureEvent

import logging

logger = logging.getLogger(__name__)


@dataclass
class BehaviourAnalysis:
    timestamp: datetime
    symbol: str
    
    panic: Optional[PanicEvent]
    absorption: Optional[AbsorptionEvent]
    breakout: Optional[BreakoutEvent]
    liquidation_cascade: Optional[LiquidationCascadeEvent]
    trend_exhaustion: Optional[TrendExhaustionEvent]
    mean_reversion: Optional[MeanReversionEvent]
    trade_pressure: Optional[TradePressureEvent]
    
    composite_signal: float
    dominant_behaviour: str
    confidence: float
    
    actionable: bool
    action_type: str
    action_strength: float
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class BehaviourDetector:
    def __init__(self):
        self._panic_detector = PanicDetector()
        self._absorption_detector = AbsorptionDetector()
        self._breakout_detector = BreakoutDetector()
        self._cascade_detector = LiquidationCascadeDetector()
        self._exhaustion_detector = TrendExhaustionDetector()
        self._reversion_detector = MeanReversionDetector()
        self._trade_pressure_detector = TradePressureDetector()
        
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        
        logger.info("BehaviourDetector initialized")
    
    def analyze(
        self,
        current_price: float,
        current_volume: float,
        trades: List[Dict[str, Any]],
        orderbook: tuple,
        funding_rate: float,
        open_interest: float,
        symbol: str,
        # TradePressure 额外参数
        buy_volume: Optional[float] = None,
        sell_volume: Optional[float] = None,
        orderbook_imbalance: float = 0.0,
        price_change_5min: float = 0.0,
        price_change_15min: float = 0.0,
    ) -> BehaviourAnalysis:
        timestamp = datetime.now()
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(current_price)
        if len(self._price_history[symbol]) > 200:
            self._price_history[symbol] = self._price_history[symbol][-200:]
        
        if symbol not in self._volume_history:
            self._volume_history[symbol] = []
        self._volume_history[symbol].append(current_volume)
        if len(self._volume_history[symbol]) > 200:
            self._volume_history[symbol] = self._volume_history[symbol][-200:]
        
        prices = self._price_history[symbol]
        volumes = self._volume_history[symbol]
        
        panic = self._panic_detector.detect(
            current_price, trades, orderbook, symbol
        )
        
        absorption = self._absorption_detector.detect(
            prices, volumes, trades, orderbook, symbol
        )
        
        breakout = self._breakout_detector.detect(
            current_price, current_volume, prices, volumes, symbol
        )
        
        cascade = self._cascade_detector.detect(
            current_price, prices, funding_rate, open_interest, symbol
        )
        
        exhaustion = self._exhaustion_detector.detect(
            prices, volumes, symbol
        )
        
        reversion = self._reversion_detector.detect(
            current_price, prices, symbol
        )
        
        # 检测 TradePressure 事件
        if buy_volume is None or sell_volume is None:
            # 从 trades 中计算
            buy_volume = sum(t.get("size", 0) for t in trades if t.get("side") == "buy")
            sell_volume = sum(t.get("size", 0) for t in trades if t.get("side") == "sell")
        
        trade_pressure = self._trade_pressure_detector.detect(
            current_price=current_price,
            volume=current_volume,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            orderbook_imbalance=orderbook_imbalance,
            price_change_5min=price_change_5min,
            price_change_15min=price_change_15min,
            symbol=symbol,
            timestamp=timestamp,
        )
        
        composite_signal, dominant = self._calculate_composite(
            panic, absorption, breakout, cascade, exhaustion, reversion, trade_pressure
        )
        
        confidence = self._calculate_confidence(
            panic, absorption, breakout, cascade, exhaustion, reversion, trade_pressure
        )
        
        actionable, action_type, action_strength = self._determine_action(
            composite_signal, dominant, confidence
        )
        
        return BehaviourAnalysis(
            timestamp=timestamp,
            symbol=symbol,
            panic=panic,
            absorption=absorption,
            breakout=breakout,
            liquidation_cascade=cascade,
            trend_exhaustion=exhaustion,
            mean_reversion=reversion,
            trade_pressure=trade_pressure,
            composite_signal=composite_signal,
            dominant_behaviour=dominant,
            confidence=confidence,
            actionable=actionable,
            action_type=action_type,
            action_strength=action_strength,
        )

    def _calculate_composite(
        self,
        panic: PanicEvent,
        absorption: AbsorptionEvent,
        breakout: BreakoutEvent,
        cascade: LiquidationCascadeEvent,
        exhaustion: TrendExhaustionEvent,
        reversion: MeanReversionEvent,
        trade_pressure: Optional[TradePressureEvent] = None,
    ) -> tuple:
        signals = {
            "panic": (panic.signal, 0.20),
            "absorption": (absorption.signal, 0.15),
            "breakout": (breakout.signal, 0.15),
            "cascade": (cascade.signal, 0.10),
            "exhaustion": (exhaustion.signal, 0.10),
            "reversion": (reversion.trade_signal, 0.10),
        }
        
        # 添加 trade_pressure 信号
        if trade_pressure and trade_pressure.event_type:
            tp_signal = trade_pressure.direction * trade_pressure.confidence
            signals["trade_pressure"] = (tp_signal, 0.20)
        
        weighted_sum = sum(s * w for s, w in signals.values())
        total_weight = sum(w for _, w in signals.values())
        
        composite = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        abs_signals = {k: abs(s) for k, (s, _) in signals.items()}
        dominant = max(abs_signals, key=abs_signals.get)
        
        return composite, dominant
    
    def _calculate_confidence(
        self,
        panic: PanicEvent,
        absorption: AbsorptionEvent,
        breakout: BreakoutEvent,
        cascade: LiquidationCascadeEvent,
        exhaustion: TrendExhaustionEvent,
        reversion: MeanReversionEvent,
        trade_pressure: Optional[TradePressureEvent] = None,
    ) -> float:
        scores = [
            panic.panic_score,
            absorption.absorption_score,
            breakout.breakout_strength,
            cascade.cascade_score,
            exhaustion.exhaustion_score,
            abs(reversion.z_score) / 3.0,
        ]
        
        # 添加 trade_pressure 分数
        if trade_pressure:
            scores.append(trade_pressure.confidence)
        
        max_score = max(scores)
        
        active_count = sum(1 for s in scores if s > 0.3)
        
        confidence = max_score * (0.5 + 0.1 * min(3, active_count))
        
        return min(1.0, confidence)

    def _determine_action(
        self,
        composite: float,
        dominant: str,
        confidence: float,
    ) -> tuple:
        if confidence < 0.3:
            return False, "none", 0.0

        if abs(composite) < 0.2:
            return False, "none", 0.0

        if composite > 0.3:
            action_type = "buy"
        elif composite < -0.3:
            action_type = "sell"
        else:
            action_type = "hold"

        strength = min(1.0, abs(composite) * confidence * 2)

        return True, action_type, strength

    def get_analysis_summary(self, analysis: BehaviourAnalysis) -> Dict[str, Any]:
        return {
            "symbol": analysis.symbol,
            "timestamp": analysis.timestamp.isoformat(),
            "composite_signal": analysis.composite_signal,
            "dominant_behaviour": analysis.dominant_behaviour,
            "confidence": analysis.confidence,
            "actionable": analysis.actionable,
            "action": {
                "type": analysis.action_type,
                "strength": analysis.action_strength,
            },
            "behaviours": {
                "panic": {
                    "level": analysis.panic.level.value if analysis.panic else "none",
                    "signal": analysis.panic.signal if analysis.panic else 0.0,
                },
                "absorption": {
                    "type": analysis.absorption.absorption_type.value if analysis.absorption else "none",
                    "signal": analysis.absorption.signal if analysis.absorption else 0.0,
                },
                "breakout": {
                    "type": analysis.breakout.breakout_type.value if analysis.breakout else "none",
                    "signal": analysis.breakout.signal if analysis.breakout else 0.0,
                },
                "cascade": {
                    "phase": analysis.liquidation_cascade.phase.value if analysis.liquidation_cascade else "none",
                    "signal": analysis.liquidation_cascade.signal if analysis.liquidation_cascade else 0.0,
                },
                "exhaustion": {
                    "level": analysis.trend_exhaustion.level.value if analysis.trend_exhaustion else "none",
                    "signal": analysis.trend_exhaustion.signal if analysis.trend_exhaustion else 0.0,
                },
                "reversion": {
                    "signal": analysis.mean_reversion.signal.value if analysis.mean_reversion else "none",
                    "z_score": analysis.mean_reversion.z_score if analysis.mean_reversion else 0.0,
                },
                "trade_pressure": {
                    "type": analysis.trade_pressure.signal_type.value if analysis.trade_pressure else "none",
                    "event": analysis.trade_pressure.event_type.value if (analysis.trade_pressure and analysis.trade_pressure.event_type) else "none",
                    "direction": analysis.trade_pressure.direction if analysis.trade_pressure else 0,
                    "confidence": analysis.trade_pressure.confidence if analysis.trade_pressure else 0.0,
                    "pressure_score": analysis.trade_pressure.pressure_score if analysis.trade_pressure else 0.0,
                },
            },
        }
