import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from infrastructure.logging import get_logger
from engines.compute.correlation.compute import (
    SignalWeight,
    compute_signal_weight,
    compute_all_weights,
    filter_strong_signals,
    compute_summary,
)

logger = get_logger("correlation_service.strategy")


class CorrelationStrategyAdapter:
    def __init__(self, results_dir: str = "./data/correlation_results"):
        self.results_dir = Path(results_dir)
        self._cache: Dict[str, Dict] = {}
        self._last_refresh: Optional[datetime] = None

    def refresh(self):
        if not self.results_dir.exists():
            logger.debug(f"Results directory not found: {self.results_dir}")
            return

        for result_file in self.results_dir.rglob("correlation_*.json"):
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                symbol = data.get("symbol", "UNKNOWN")
                timeframe = data.get("timeframe", "1h")
                cache_key = f"{symbol}:{timeframe}"

                existing = self._cache.get(cache_key)
                if existing is None or data.get("timestamp", "") > existing.get("timestamp", ""):
                    self._cache[cache_key] = data

            except Exception as e:
                logger.debug(f"Failed to read result file {result_file}: {e}")

        self._last_refresh = datetime.now()
        logger.debug(f"Refreshed correlation cache: {len(self._cache)} results")

    def update_from_kafka(self, result_dict: Dict, symbol: str, timeframe: str):
        cache_key = f"{symbol}:{timeframe}"
        self._cache[cache_key] = result_dict
        self._last_refresh = datetime.now()

    def get_signal_weight(
        self,
        feature: str,
        symbol: str = "BTC",
        timeframe: str = "1h",
    ) -> SignalWeight:
        self._auto_refresh()

        cache_key = f"{symbol}:{timeframe}"
        result = self._cache.get(cache_key, {})
        assessments = result.get("signal_assessments", {})
        assessment = assessments.get(feature, {})

        return compute_signal_weight(feature, assessment)

    def get_all_weights(
        self,
        symbol: str = "BTC",
        timeframe: str = "1h",
    ) -> Dict[str, SignalWeight]:
        self._auto_refresh()

        cache_key = f"{symbol}:{timeframe}"
        result = self._cache.get(cache_key, {})
        assessments = result.get("signal_assessments", {})

        return compute_all_weights(assessments)

    def get_strong_signals(
        self,
        symbol: str = "BTC",
        timeframe: str = "1h",
        min_confidence: float = 0.7,
        direction: Optional[str] = None,
    ) -> List[SignalWeight]:
        all_weights = self.get_all_weights(symbol, timeframe)
        return filter_strong_signals(all_weights, min_confidence, direction)

    def get_signal_direction(
        self,
        feature: str,
        symbol: str = "BTC",
        timeframe: str = "1h",
    ) -> str:
        sw = self.get_signal_weight(feature, symbol, timeframe)
        return sw.direction

    def get_positive_signals(self, symbol: str = "BTC", timeframe: str = "1h") -> List[str]:
        result = self._cache.get(f"{symbol}:{timeframe}", {})
        return result.get("positive_signals", [])

    def get_negative_signals(self, symbol: str = "BTC", timeframe: str = "1h") -> List[str]:
        result = self._cache.get(f"{symbol}:{timeframe}", {})
        return result.get("negative_signals", [])

    def get_summary(self, symbol: str = "BTC", timeframe: str = "1h") -> Dict:
        self._auto_refresh()

        cache_key = f"{symbol}:{timeframe}"
        result = self._cache.get(cache_key, {})
        weights = self.get_all_weights(symbol, timeframe)

        return compute_summary(result, symbol, timeframe, weights)

    def _auto_refresh(self):
        if self._last_refresh is None:
            self.refresh()
        elif (datetime.now() - self._last_refresh).total_seconds() > 60:
            self.refresh()


_adapter: Optional[CorrelationStrategyAdapter] = None


def get_correlation_adapter(
    results_dir: str = "./data/correlation_results"
) -> CorrelationStrategyAdapter:
    global _adapter
    if _adapter is None:
        _adapter = CorrelationStrategyAdapter(results_dir)
    return _adapter
