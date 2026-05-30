"""
信号汇合引擎 - 将多个策略信号合并为统一的交易决策

核心逻辑：
1. 按币种分组信号
2. 分离多空阵营
3. 计算汇合度（策略一致性）
4. 应用市场状态权重
5. 生成汇合信号
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from engines.compute.strategy.strategies import StrategySignal, ActionType
from domain.market_state import MarketRegime
from infrastructure.logging import get_logger

logger = get_logger("confluence_engine")


@dataclass
class ConfluenceSignal:
    id: str
    timestamp: datetime
    symbol: str
    direction: str
    confidence: float
    confluence_score: float
    contributing_strategies: list[str] = field(default_factory=list)
    conflicting_strategies: list[str] = field(default_factory=list)
    avg_confidence: float = 0.0
    strategy_count: int = 0
    regime: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and self.strategy_count >= 3

    @property
    def is_moderate(self) -> bool:
        return self.confidence >= 0.5 and self.strategy_count >= 2

    @property
    def has_conflict(self) -> bool:
        return len(self.conflicting_strategies) > 0


REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    MarketRegime.HIGH_VOLATILITY.value: {
        "breakout": 1.3,
        "momentum_ignition": 1.2,
        "volatility_expansion": 1.3,
    },
    MarketRegime.LOW_VOLATILITY.value: {
        "mean_reversion": 1.3,
        "bb_compression_breakout": 1.2,
    },
    MarketRegime.TRENDING.value: {
        "trend_following": 1.3,
        "momentum_ignition": 1.2,
        "breakout": 1.1,
    },
    MarketRegime.RANGING.value: {
        "funding_exhaustion_trap": 1.2,
        "imbalance_pressure": 1.1,
    },
    MarketRegime.LIQUIDATION_CASCADE.value: {
        "panic_reversal": 1.4,
        "oi_flush": 1.3,
        "long_liquidation_bounce": 1.3,
    },
    MarketRegime.NARRATIVE_BURST.value: {
        "momentum_ignition": 1.3,
        "trend_following": 1.2,
    },
    MarketRegime.LIQUIDITY_DRAIN.value: {
        "liquidity_vacuum": 1.3,
        "imbalance_pressure": 1.2,
    },
    MarketRegime.UNKNOWN.value: {},
}


class SignalConfluenceEngine:
    def __init__(
        self,
        min_confidence: float = 0.4,
        confluence_boost: float = 0.15,
        conflict_penalty: float = 0.2,
    ):
        self.min_confidence = min_confidence
        self.confluence_boost = confluence_boost
        self.conflict_penalty = conflict_penalty

    def process_signals(
        self,
        signals: List[StrategySignal],
        regime: Optional[str] = None,
    ) -> List[ConfluenceSignal]:
        if not signals:
            return []

        by_symbol: dict[str, list[StrategySignal]] = defaultdict(list)
        for signal in signals:
            by_symbol[signal.symbol].append(signal)

        regime_weights = self.get_regime_weights(regime) if regime else {}

        results: List[ConfluenceSignal] = []
        for symbol, symbol_signals in by_symbol.items():
            confluence_signals = self._process_symbol(symbol, symbol_signals, regime, regime_weights)
            results.extend(confluence_signals)

        results.sort(key=lambda s: s.confidence, reverse=True)

        logger.debug(
            f"Confluence processed {len(signals)} signals -> {len(results)} confluence signals "
            f"(regime={regime})"
        )

        return results

    def _process_symbol(
        self,
        symbol: str,
        signals: List[StrategySignal],
        regime: Optional[str],
        regime_weights: Dict[str, float],
    ) -> List[ConfluenceSignal]:
        long_camp: list[StrategySignal] = []
        short_camp: list[StrategySignal] = []

        for signal in signals:
            if signal.action == ActionType.LONG:
                long_camp.append(signal)
            elif signal.action == ActionType.SHORT:
                short_camp.append(signal)

        results: List[ConfluenceSignal] = []
        total_count = len(long_camp) + len(short_camp)

        if total_count == 0:
            return results

        if long_camp:
            signal = self._build_confluence(
                symbol=symbol,
                direction="long",
                camp=long_camp,
                opposing_count=len(short_camp),
                opposing_ids=[s.strategy_id for s in short_camp],
                total_count=total_count,
                regime=regime,
                regime_weights=regime_weights,
            )
            if signal:
                results.append(signal)

        if short_camp:
            signal = self._build_confluence(
                symbol=symbol,
                direction="short",
                camp=short_camp,
                opposing_count=len(long_camp),
                opposing_ids=[s.strategy_id for s in long_camp],
                total_count=total_count,
                regime=regime,
                regime_weights=regime_weights,
            )
            if signal:
                results.append(signal)

        return results

    def _build_confluence(
        self,
        symbol: str,
        direction: str,
        camp: list[StrategySignal],
        opposing_count: int,
        opposing_ids: list[str],
        total_count: int,
        regime: Optional[str],
        regime_weights: Dict[str, float],
    ) -> Optional[ConfluenceSignal]:
        agreeing_count = len(camp)

        weighted_confidences: list[float] = []
        for s in camp:
            weight = self._get_strategy_weight(s.strategy_id, regime_weights)
            weighted_confidences.append(s.confidence * weight)

        avg_confidence = (
            sum(weighted_confidences) / len(weighted_confidences)
            if weighted_confidences
            else 0.0
        )

        confluence_score = (agreeing_count / total_count) * avg_confidence

        final_confidence = (
            avg_confidence
            + (self.confluence_boost * (agreeing_count - 1))
            - (self.conflict_penalty * opposing_count)
        )
        final_confidence = max(0.0, min(1.0, final_confidence))

        if final_confidence < self.min_confidence:
            return None

        contributing = [s.strategy_id for s in camp]

        return ConfluenceSignal(
            id=f"conf_{symbol}_{direction}_{int(datetime.utcnow().timestamp() * 1000)}",
            timestamp=datetime.utcnow(),
            symbol=symbol,
            direction=direction,
            confidence=round(final_confidence, 4),
            confluence_score=round(confluence_score, 4),
            contributing_strategies=contributing,
            conflicting_strategies=opposing_ids,
            avg_confidence=round(avg_confidence, 4),
            strategy_count=agreeing_count,
            regime=regime,
            metadata={
                "confluence_boost_applied": round(self.confluence_boost * (agreeing_count - 1), 4),
                "conflict_penalty_applied": round(self.conflict_penalty * opposing_count, 4),
                "regime_weights_applied": regime_weights is not None and len(regime_weights) > 0,
            },
        )

    def _get_strategy_weight(self, strategy_id: str, regime_weights: Dict[str, float]) -> float:
        base_id = strategy_id.split("_")[0] if "_" in strategy_id else strategy_id

        for key, weight in regime_weights.items():
            if key in strategy_id or strategy_id.startswith(key) or key.startswith(base_id):
                return weight

        return 1.0

    def get_regime_weights(self, regime: str) -> Dict[str, float]:
        return dict(REGIME_WEIGHTS.get(regime, {}))
