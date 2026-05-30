"""
Feature Store - 特征存储

核心职责:
1. 存储 feature snapshot 供 AI/Replay 使用
2. 支持 behaviour state 存储
3. 支持 signal context 存储
4. 支持 market regime 存储

用途:
- AI 训练: 需要 feature vector 历史
- Replay: 需要 feature snapshot 回放
- 策略分析: 需要 signal context
- 市场状态: 需要 regime snapshot
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.storage.feature_store")


class TradingMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class FeatureSnapshot:
    timestamp: datetime
    symbol: str
    features: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "features": self.features,
            "metadata": self.metadata,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureSnapshot':
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            symbol=data["symbol"],
            features=data["features"],
            metadata=data.get("metadata", {}),
            version=data.get("version", 1),
        )


@dataclass
class BehaviourState:
    timestamp: datetime
    behaviour_type: str
    symbol: str
    confidence: float
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "behaviour_type": self.behaviour_type,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "context": self.context,
        }


@dataclass
class SignalContext:
    timestamp: datetime
    signal_id: str
    strategy: str
    symbol: str
    features: Dict[str, float]
    action: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "signal_id": self.signal_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "features": self.features,
            "action": self.action,
            "confidence": self.confidence,
        }


@dataclass
class RegimeSnapshot:
    timestamp: datetime
    regime: str
    confidence: float
    indicators: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime,
            "confidence": self.confidence,
            "indicators": self.indicators,
        }


class FeatureStore:
    _instance: Optional['FeatureStore'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_snapshots: int = 10000,
        mode_provider: Optional[Callable[[], TradingMode]] = None,
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        self._mode_provider = mode_provider
        self._max_snapshots = max_snapshots

        self._feature_snapshots: Dict[str, List[FeatureSnapshot]] = {}
        self._behaviour_states: List[BehaviourState] = []
        self._signal_contexts: List[SignalContext] = []
        self._regime_snapshots: List[RegimeSnapshot] = []

        self._isolated_stores: Dict[TradingMode, Dict[str, List]] = {
            TradingMode.BACKTEST: {
                "features": {},
                "behaviours": [],
                "signals": [],
                "regimes": [],
            },
            TradingMode.PAPER: {
                "features": {},
                "behaviours": [],
                "signals": [],
                "regimes": [],
            },
            TradingMode.LIVE: {
                "features": {},
                "behaviours": [],
                "signals": [],
                "regimes": [],
            },
        }

        self._stats = {
            "features_stored": 0,
            "behaviours_stored": 0,
            "signals_stored": 0,
            "regimes_stored": 0,
        }

        logger.info("FeatureStore initialized")

    def _get_current_mode(self) -> TradingMode:
        if self._mode_provider is not None:
            return self._mode_provider()
        return TradingMode.PAPER

    def _get_store(self, use_namespace: bool = True) -> Dict[str, List]:
        if use_namespace:
            mode = self._get_current_mode()
            return self._isolated_stores[mode]
        return {
            "features": self._feature_snapshots,
            "behaviours": self._behaviour_states,
            "signals": self._signal_contexts,
            "regimes": self._regime_snapshots,
        }

    def store_features(
        self,
        symbol: str,
        features: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
        use_namespace: bool = True,
    ) -> FeatureSnapshot:
        snapshot = FeatureSnapshot(
            timestamp=datetime.now(),
            symbol=symbol,
            features=features,
            metadata=metadata or {},
        )

        store = self._get_store(use_namespace)
        if symbol not in store["features"]:
            store["features"][symbol] = []

        store["features"][symbol].append(snapshot)

        if len(store["features"][symbol]) > self._max_snapshots:
            store["features"][symbol] = store["features"][symbol][-self._max_snapshots:]

        self._stats["features_stored"] += 1

        return snapshot

    def store_behaviour(
        self,
        behaviour_type: str,
        symbol: str,
        confidence: float,
        context: Optional[Dict[str, Any]] = None,
        use_namespace: bool = True,
    ) -> BehaviourState:
        state = BehaviourState(
            timestamp=datetime.now(),
            behaviour_type=behaviour_type,
            symbol=symbol,
            confidence=confidence,
            context=context or {},
        )

        store = self._get_store(use_namespace)
        store["behaviours"].append(state)

        if len(store["behaviours"]) > self._max_snapshots:
            store["behaviours"] = store["behaviours"][-self._max_snapshots:]

        self._stats["behaviours_stored"] += 1

        return state

    def store_signal_context(
        self,
        signal_id: str,
        strategy: str,
        symbol: str,
        features: Dict[str, float],
        action: str,
        confidence: float,
        use_namespace: bool = True,
    ) -> SignalContext:
        context = SignalContext(
            timestamp=datetime.now(),
            signal_id=signal_id,
            strategy=strategy,
            symbol=symbol,
            features=features,
            action=action,
            confidence=confidence,
        )

        store = self._get_store(use_namespace)
        store["signals"].append(context)

        if len(store["signals"]) > self._max_snapshots:
            store["signals"] = store["signals"][-self._max_snapshots:]

        self._stats["signals_stored"] += 1

        return context

    def store_regime(
        self,
        regime: str,
        confidence: float,
        indicators: Optional[Dict[str, Any]] = None,
        use_namespace: bool = True,
    ) -> RegimeSnapshot:
        snapshot = RegimeSnapshot(
            timestamp=datetime.now(),
            regime=regime,
            confidence=confidence,
            indicators=indicators or {},
        )

        store = self._get_store(use_namespace)
        store["regimes"].append(snapshot)

        if len(store["regimes"]) > self._max_snapshots:
            store["regimes"] = store["regimes"][-self._max_snapshots:]

        self._stats["regimes_stored"] += 1

        return snapshot

    def get_features(
        self,
        symbol: str,
        limit: int = 100,
        use_namespace: bool = True,
    ) -> List[FeatureSnapshot]:
        store = self._get_store(use_namespace)
        snapshots = store["features"].get(symbol, [])
        return snapshots[-limit:]

    def get_behaviours(
        self,
        limit: int = 100,
        use_namespace: bool = True,
    ) -> List[BehaviourState]:
        store = self._get_store(use_namespace)
        return store["behaviours"][-limit:]

    def get_signal_contexts(
        self,
        limit: int = 100,
        use_namespace: bool = True,
    ) -> List[SignalContext]:
        store = self._get_store(use_namespace)
        return store["signals"][-limit:]

    def get_regimes(
        self,
        limit: int = 100,
        use_namespace: bool = True,
    ) -> List[RegimeSnapshot]:
        store = self._get_store(use_namespace)
        return store["regimes"][-limit:]

    def get_latest_features(
        self,
        symbol: str,
        use_namespace: bool = True,
    ) -> Optional[FeatureSnapshot]:
        features = self.get_features(symbol, limit=1, use_namespace=use_namespace)
        return features[0] if features else None

    def get_latest_regime(
        self,
        use_namespace: bool = True,
    ) -> Optional[RegimeSnapshot]:
        regimes = self.get_regimes(limit=1, use_namespace=use_namespace)
        return regimes[0] if regimes else None

    def export_for_training(
        self,
        use_namespace: bool = True,
    ) -> Dict[str, Any]:
        store = self._get_store(use_namespace)

        return {
            "features": {
                symbol: [s.to_dict() for s in snapshots]
                for symbol, snapshots in store["features"].items()
            },
            "behaviours": [b.to_dict() for b in store["behaviours"]],
            "signals": [s.to_dict() for s in store["signals"]],
            "regimes": [r.to_dict() for r in store["regimes"]],
        }

    def clear(self, use_namespace: bool = True) -> None:
        store = self._get_store(use_namespace)
        store["features"] = {}
        store["behaviours"] = []
        store["signals"] = []
        store["regimes"] = []
        logger.info("FeatureStore cleared")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self._get_current_mode().value,
            "max_snapshots": self._max_snapshots,
            "stats": self._stats.copy(),
        }


def get_feature_store(
    mode_provider: Optional[Callable[[], TradingMode]] = None,
) -> FeatureStore:
    return FeatureStore(mode_provider=mode_provider)


def store_features(symbol: str, features: Dict[str, float], **kwargs) -> FeatureSnapshot:
    store = get_feature_store()
    return store.store_features(symbol, features, **kwargs)


def store_behaviour(behaviour_type: str, symbol: str, confidence: float, **kwargs) -> BehaviourState:
    store = get_feature_store()
    return store.store_behaviour(behaviour_type, symbol, confidence, **kwargs)


def store_signal_context(signal_id: str, strategy: str, symbol: str, features: Dict[str, float], action: str, confidence: float, **kwargs) -> SignalContext:
    store = get_feature_store()
    return store.store_signal_context(signal_id, strategy, symbol, features, action, confidence, **kwargs)
