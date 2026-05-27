"""
Multi-Timeframe Runtime Coordination

多周期信号协调层

架构：
    1D (Macro) → 4H (Swing) → 1H (Intraday) → 15M (Micro)
         ↓              ↓              ↓              ↓
    ┌─────────────────────────────────────────────────────────┐
    │              Timeframe Coordinator                       │
    │                                                          │
    │  - Regime Hierarchy: 高周期确定方向，低周期找入场        │
    │  - Signal Aggregation: 多周期信号汇总                    │
    │  - Confluence Detection: 信号共振                        │
    │  - Alignment Scoring: 周期对齐评分                      │
    └─────────────────────────────────────────────────────────┘
         ↓
    Portfolio Projection
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class Timeframe(str, Enum):
    """时间周期"""
    MACRO_1D = "1d"
    SWING_4H = "4h"
    INTRADAY_1H = "1h"
    MICRO_15M = "15m"
    TICK_1M = "1m"


class RegimeType(str, Enum):
    """市场状态类型"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class SignalAlignment(str, Enum):
    """信号对齐状态"""
    PERFECT = "perfect"
    STRONG = "strong"
    MIXED = "mixed"
    CONFLICTING = "conflicting"
    NO_SIGNAL = "no_signal"


@dataclass
class TimeframeSignal:
    """周期信号"""
    timeframe: str
    symbol: str

    direction: str
    confidence: float
    strength: float

    regime: RegimeType
    regime_confidence: float

    events: List[Dict[str, Any]] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_bullish(self) -> bool:
        return self.direction.lower() == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.direction.lower() == "bearish"

    @property
    def score(self) -> float:
        return self.confidence * self.strength


@dataclass
class CoordinatedSignal:
    """
    协调后的信号

    多周期协调后的统一信号
    """
    symbol: str

    direction: str

    alignment: SignalAlignment
    alignment_score: float

    macro_signal: Optional[TimeframeSignal] = None
    swing_signal: Optional[TimeframeSignal] = None
    intraday_signal: Optional[TimeframeSignal] = None
    micro_signal: Optional[TimeframeSignal] = None

    confluent_factors: List[str] = field(default_factory=list)
    conflicting_factors: List[str] = field(default_factory=list)

    position_size_multiplier: float = 1.0

    stop_loss_distance: float = 0.0
    take_profit_distance: float = 0.0

    confidence: float = 0.0
    risk_level: str = "medium"

    reasoning: str = ""

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "alignment": self.alignment.value,
            "alignment_score": self.alignment_score,
            "confluent_factors": self.confluent_factors,
            "conflicting_factors": self.conflicting_factors,
            "position_size_multiplier": self.position_size_multiplier,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RegimeHierarchy:
    """状态层级"""
    macro_regime: RegimeType = RegimeType.UNKNOWN
    swing_regime: RegimeType = RegimeType.UNKNOWN
    intraday_regime: RegimeType = RegimeType.UNKNOWN

    macro_confidence: float = 0.5
    swing_confidence: float = 0.5
    intraday_confidence: float = 0.5

    is_aligned: bool = False
    dominant_direction: str = "neutral"

    def get_trade_direction(self) -> str:
        if not self.is_aligned:
            return "neutral"
        return self.dominant_direction


class TimeframeCoordinator:
    """
    多周期协调器

    职责：
    1. 管理多周期信号
    2. 检测周期对齐
    3. 生成协调信号
    4. 计算仓位大小
    """

    TIMEFRAME_HIERARCHY = [
        Timeframe.MACRO_1D,
        Timeframe.SWING_4H,
        Timeframe.INTRADAY_1H,
        Timeframe.MICRO_15M,
    ]

    def __init__(self):
        self._signals: Dict[str, Dict[str, TimeframeSignal]] = {}
        self._regimes: Dict[str, RegimeHierarchy] = {}

        self._alignment_weights = {
            Timeframe.MACRO_1D: 0.4,
            Timeframe.SWING_4H: 0.35,
            Timeframe.INTRADAY_1H: 0.15,
            Timeframe.MICRO_15M: 0.1,
        }

        self._stats = {
            "signals_coordinated": 0,
            "perfect_alignments": 0,
            "conflicting_signals": 0,
        }

    def update_signal(self, signal: TimeframeSignal) -> None:
        """
        更新周期信号

        Args:
            signal: 周期信号
        """
        symbol = signal.symbol

        if symbol not in self._signals:
            self._signals[symbol] = {}

        self._signals[symbol][signal.timeframe] = signal

        logger.debug(
            f"Signal updated: {symbol} {signal.timeframe} "
            f"{signal.direction} ({signal.confidence:.2f})"
        )

    def get_signal(self, symbol: str, timeframe: str) -> Optional[TimeframeSignal]:
        """获取周期信号"""
        return self._signals.get(symbol, {}).get(timeframe)

    def get_all_signals(self, symbol: str) -> Dict[str, TimeframeSignal]:
        """获取所有周期信号"""
        return self._signals.get(symbol, {})

    def calculate_alignment(
        self,
        symbol: str
    ) -> Tuple[SignalAlignment, float, List[str], List[str]]:
        """
        计算信号对齐度

        Returns:
            (alignment, score, confluent_factors, conflicting_factors)
        """
        signals = self._signals.get(symbol, {})

        if not signals:
            return SignalAlignment.NO_SIGNAL, 0.0, [], []

        bullish_weight = 0.0
        bearish_weight = 0.0
        confluent = []
        conflicting = []

        for tf in self.TIMEFRAME_HIERARCHY:
            signal = signals.get(tf.value)
            if not signal:
                continue

            weight = self._alignment_weights.get(tf, 0.1)

            if signal.is_bullish:
                bullish_weight += weight * signal.score
                confluent.append(f"{tf.value}:bullish")
            elif signal.is_bearish:
                bearish_weight += weight * signal.score
                confluent.append(f"{tf.value}:bearish")

        total_weight = bullish_weight + bearish_weight
        if total_weight == 0:
            return SignalAlignment.NO_SIGNAL, 0.0, [], []

        alignment_score = abs(bullish_weight - bearish_weight) / total_weight

        if alignment_score >= 0.8:
            alignment = SignalAlignment.PERFECT
            self._stats["perfect_alignments"] += 1
        elif alignment_score >= 0.5:
            alignment = SignalAlignment.STRONG
        elif alignment_score >= 0.2:
            alignment = SignalAlignment.MIXED
        else:
            alignment = SignalAlignment.CONFLICTING
            self._stats["conflicting_signals"] += 1

        direction = "bullish" if bullish_weight > bearish_weight else "bearish"
        direction = direction if alignment_score >= 0.2 else "neutral"

        conflicting = []
        if alignment == SignalAlignment.CONFLICTING:
            conflicting = [
                "Multi-timeframe signals are conflicting",
                f"Bullish: {bullish_weight:.2f} vs Bearish: {bearish_weight:.2f}",
            ]

        return alignment, alignment_score, confluent, conflicting

    def coordinate_signals(self, symbol: str) -> CoordinatedSignal:
        """
        协调多周期信号

        Args:
            symbol: 品种

        Returns:
            CoordinatedSignal: 协调后的信号
        """
        signals = self._signals.get(symbol, {})

        alignment, alignment_score, confluent, conflicting = self.calculate_alignment(symbol)

        macro = signals.get(Timeframe.MACRO_1D.value)
        swing = signals.get(Timeframe.SWING_4H.value)
        intraday = signals.get(Timeframe.INTRADAY_1H.value)
        micro = signals.get(Timeframe.MICRO_15M.value)

        bullish = sum(
            s.score for s in [macro, swing, intraday, micro]
            if s and s.is_bullish
        )
        bearish = sum(
            s.score for s in [macro, swing, intraday, micro]
            if s and s.is_bearish
        )

        direction = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"

        confidence = max(bullish, bearish) if direction != "neutral" else 0.5

        size_multiplier = self._calculate_size_multiplier(
            alignment, alignment_score, confidence
        )

        sl_distance, tp_distance = self._calculate_stop_take(
            direction, signals
        )

        risk_level = self._determine_risk_level(
            alignment, alignment_score, signals
        )

        reasoning = self._generate_reasoning(
            symbol, direction, alignment, confluent, conflicting, signals
        )

        coordinated = CoordinatedSignal(
            symbol=symbol,
            direction=direction,
            alignment=alignment,
            alignment_score=alignment_score,
            macro_signal=macro,
            swing_signal=swing,
            intraday_signal=intraday,
            micro_signal=micro,
            confluent_factors=confluent,
            conflicting_factors=conflicting,
            position_size_multiplier=size_multiplier,
            stop_loss_distance=sl_distance,
            take_profit_distance=tp_distance,
            confidence=confidence,
            risk_level=risk_level,
            reasoning=reasoning,
        )

        self._stats["signals_coordinated"] += 1

        return coordinated

    def _calculate_size_multiplier(
        self,
        alignment: SignalAlignment,
        alignment_score: float,
        confidence: float,
    ) -> float:
        """计算仓位大小乘数"""
        base = 1.0

        if alignment == SignalAlignment.PERFECT:
            base *= 1.5
        elif alignment == SignalAlignment.STRONG:
            base *= 1.2
        elif alignment == SignalAlignment.MIXED:
            base *= 0.7
        elif alignment == SignalAlignment.CONFLICTING:
            base *= 0.3

        base *= (0.5 + confidence)

        return min(max(base, 0.1), 2.0)

    def _calculate_stop_take(
        self,
        direction: str,
        signals: Dict[str, TimeframeSignal],
    ) -> Tuple[float, float]:
        """计算止损止盈距离（百分比）"""
        swing = signals.get(Timeframe.SWING_4H.value)

        if not swing:
            return 2.0, 6.0

        sl_base = 1.5
        tp_base = 4.5

        if swing.strength > 0.7:
            sl_base *= 0.8
            tp_base *= 1.2
        elif swing.strength < 0.4:
            sl_base *= 1.2
            tp_base *= 0.8

        return sl_base, tp_base

    def _determine_risk_level(
        self,
        alignment: SignalAlignment,
        alignment_score: float,
        signals: Dict[str, TimeframeSignal],
    ) -> str:
        """确定风险等级"""
        if alignment == SignalAlignment.CONFLICTING:
            return "high"

        if alignment == SignalAlignment.MIXED:
            return "medium"

        swing = signals.get(Timeframe.SWING_4H.value)
        if swing and swing.regime in [RegimeType.VOLATILE, RegimeType.RANGING]:
            return "medium"

        if alignment_score >= 0.7:
            return "low"

        return "medium"

    def _generate_reasoning(
        self,
        symbol: str,
        direction: str,
        alignment: SignalAlignment,
        confluent: List[str],
        conflicting: List[str],
        signals: Dict[str, TimeframeSignal],
    ) -> str:
        """生成推理说明"""
        parts = []

        parts.append(f"{symbol.upper()} {direction.upper()} signal")

        if alignment == SignalAlignment.PERFECT:
            parts.append("Perfect multi-timeframe alignment")
        elif alignment == SignalAlignment.STRONG:
            parts.append("Strong alignment across timeframes")
        elif alignment == SignalAlignment.MIXED:
            parts.append("Mixed signals, caution advised")
        elif alignment == SignalAlignment.CONFLICTING:
            parts.append("Conflicting signals, avoid entry")

        if confluent:
            tf_list = ", ".join([tf.split(":")[0] for tf in confluent[:3]])
            parts.append(f"Confluent on {tf_list}")

        swing = signals.get(Timeframe.SWING_4H.value)
        if swing and swing.regime != RegimeType.UNKNOWN:
            parts.append(f"Swing regime: {swing.regime.value}")

        return ". ".join(parts)

    def update_regime(self, symbol: str, regime: RegimeHierarchy) -> None:
        """更新状态层级"""
        self._regimes[symbol] = regime

        logger.info(
            f"Regime updated: {symbol} "
            f"macro={regime.macro_regime.value} "
            f"swing={regime.swing_regime.value} "
            f"aligned={regime.is_aligned}"
        )

    def get_regime(self, symbol: str) -> RegimeHierarchy:
        """获取状态层级"""
        return self._regimes.get(symbol, RegimeHierarchy())

    def get_trade_direction(self, symbol: str) -> str:
        """获取交易方向"""
        regime = self._regimes.get(symbol)
        if regime:
            return regime.get_trade_direction()

        coordinated = self.coordinate_signals(symbol)
        return coordinated.direction

    def clear_signals(self, symbol: str) -> None:
        """清除信号"""
        if symbol in self._signals:
            self._signals.pop(symbol)
        if symbol in self._regimes:
            self._regimes.pop(symbol)

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "symbols_tracked": len(self._signals),
            "regimes_tracked": len(self._regimes),
        }


_timeframe_coordinator: Optional[TimeframeCoordinator] = None


def get_timeframe_coordinator() -> TimeframeCoordinator:
    """获取 TimeframeCoordinator 单例"""
    global _timeframe_coordinator
    if _timeframe_coordinator is None:
        _timeframe_coordinator = TimeframeCoordinator()
    return _timeframe_coordinator
