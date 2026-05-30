import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from application.queries.infrastructure_queries import get_redis_client_sync, init_redis
import logging
from application.queries.service_queries import get_projection_keys

logger = logging.getLogger(__name__)


class ProjectionReader:

    def __init__(self):
        self.redis = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            self.redis = await init_redis()
            self._initialized = True
            logger.info("ProjectionReader initialized")
        except Exception as e:
            logger.warning(f"ProjectionReader init failed: {e}")
            self.redis = None

    def _keys(self):
        return get_projection_keys()

    async def _get_json(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        try:
            return await self.redis.get_json(key)
        except Exception as e:
            logger.error(f"Redis get failed for {key}: {e}")
            return None

    async def _get_list(self, key: str, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.redis:
            return []
        try:
            items = await self.redis.lrange(key, 0, limit - 1)
            result = []
            for item in items:
                try:
                    result.append(json.loads(item) if isinstance(item, str) else item)
                except json.JSONDecodeError:
                    continue
            return result
        except Exception as e:
            logger.error(f"Redis list get failed for {key}: {e}")
            return []

    async def get_dashboard_state(self) -> Dict[str, Any]:
        state = await self._get_json(self._keys().dashboard_state())

        if state:
            return state

        return {
            "prices": {},
            "factors": {},
            "regime": {},
            "signals": {},
            "news": [],
            "compositeScore": 0.5,
            "last_update": None,
            "source": "fallback",
        }

    async def get_prices(self) -> List[Dict[str, Any]]:
        state = await self.get_dashboard_state()
        prices = state.get("prices", {})

        return [
            {
                "symbol": symbol,
                "price": data.get("price", 0),
                "change24h": data.get("change24h", 0),
                "volume_24h": data.get("volume_24h", 0),
                "exchange": data.get("exchange", "binance"),
            }
            for symbol, data in prices.items()
        ]

    async def get_factors(self) -> Dict[str, Any]:
        state = await self.get_dashboard_state()
        return state.get("factors", {})

    async def get_regime(self, symbol: str = "BTC") -> Dict[str, Any]:
        state = await self.get_dashboard_state()
        regimes = state.get("regime", {})
        return regimes.get(symbol, {
            "state": "neutral",
            "confidence": 0.5,
            "trendStrength": 0.5,
        })

    async def get_signals(self, symbol: str = None) -> Dict[str, Any]:
        state = await self.get_dashboard_state()
        signals = state.get("signals", {})

        if symbol:
            return signals.get(symbol, {})
        return signals

    async def get_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        state = await self.get_dashboard_state()
        return state.get("news", [])[:limit]

    async def get_decision_latest(self, symbol: str = None) -> Dict[str, Any]:
        if symbol:
            return await self._get_json(ProjectionKeys.decision_latest(symbol)) or {}
        return await self._get_json(ProjectionKeys.decision_latest()) or {}

    async def get_decision_history(self, symbol: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        if symbol:
            return await self._get_list(ProjectionKeys.decision_history(symbol), limit)
        return await self._get_list(ProjectionKeys.decision_history(), limit)

    async def get_decision_stats(self) -> Dict[str, Any]:
        return await self._get_json(ProjectionKeys.decision_stats()) or {
            "total": 0,
            "long": 0,
            "short": 0,
            "hold": 0,
            "approved": 0,
            "rejected": 0,
            "avg_confidence": 0.0,
        }

    async def get_risk_state(self) -> Dict[str, Any]:
        return await self._get_json(ProjectionKeys.risk_state()) or {
            "level": "unknown",
            "score": None,
            "components": {
                "volatility": 0.0,
                "flow": 0.0,
                "sentiment": 0.0,
                "macro": 0.0,
            },
            "warnings": [],
            "last_check": None,
        }

    async def get_risk_level(self) -> str:
        state = await self.get_risk_state()
        return state.get("level", "low")

    async def get_risk_daily_metrics(self) -> Dict[str, Any]:
        return await self._get_json(ProjectionKeys.risk_daily_metrics()) or {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "trades": 0,
            "approved": 0,
            "rejected": 0,
            "total_volume": 0.0,
            "total_pnl": 0.0,
        }

    async def get_positions(self) -> Dict[str, Dict[str, Any]]:
        return await self._get_json(ProjectionKeys.position_current()) or {}

    async def get_position(self, symbol: str) -> Dict[str, Any]:
        positions = await self.get_positions()
        return positions.get(symbol, {})

    async def get_position_pnl(self) -> Dict[str, Any]:
        return await self._get_json(ProjectionKeys.position_pnl()) or {
            "total_unrealized": 0.0,
            "total_realized": 0.0,
            "total_pnl": 0.0,
            "positions_count": 0,
            "long_count": 0,
            "short_count": 0,
        }

    async def get_timeline(self, symbol: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        if symbol:
            return await self._get_list(ProjectionKeys.timeline_by_symbol(symbol), limit)
        return await self._get_list(ProjectionKeys.timeline_events(), limit)

    async def get_metrics(self) -> Dict[str, Any]:
        system = await self._get_json(ProjectionKeys.metrics_system()) or {}
        kafka_lag = await self._get_json(ProjectionKeys.metrics_kafka_lag()) or {}

        return {
            "system": system,
            "kafka_lag": kafka_lag,
        }


_projection_reader: Optional[ProjectionReader] = None


async def get_projection_reader() -> ProjectionReader:
    global _projection_reader
    if _projection_reader is None:
        _projection_reader = ProjectionReader()
        await _projection_reader.initialize()
    return _projection_reader


async def get_projection_state() -> Dict[str, Any]:
    # TODO: migrate to new runtime architecture - runtime.projection_runtime removed
    # from runtime.projection_runtime.runtime import get_projection_runtime
    # runtime = get_projection_runtime()
    # if runtime and hasattr(runtime, 'get_state'):
    #     return runtime.get_state()
    return {}


async def get_projection_full_state(symbol: str) -> Dict[str, Any]:
    reader = await get_projection_reader()
    return await reader.get_full_state(symbol=symbol)


async def get_projection_position(symbol: str) -> Dict[str, Any]:
    reader = await get_projection_reader()
    return await reader.get_position(symbol=symbol)


async def get_projection_decision(symbol: str) -> Dict[str, Any]:
    reader = await get_projection_reader()
    return await reader.get_decision(symbol=symbol)


async def get_projection_risk(symbol: str) -> Dict[str, Any]:
    reader = await get_projection_reader()
    return await reader.get_risk(symbol=symbol)


async def get_projection_price(symbol: str) -> Dict[str, Any]:
    reader = await get_projection_reader()
    return await reader.get_price(symbol=symbol)


async def get_projection_metrics(symbol: str) -> Dict[str, Any]:
    reader = await get_projection_reader()
    return await reader.get_metrics(symbol=symbol)
