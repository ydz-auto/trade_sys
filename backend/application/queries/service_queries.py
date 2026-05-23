from typing import Any, Dict, List, Optional
from domain.logging import get_logger

logger = get_logger(__name__)


async def get_feature_matrix(symbol: str, timeframe: str = "1m") -> Dict[str, Any]:
    from services.strategy_service.feature_matrix import FeatureMatrix
    fm = FeatureMatrix()
    return await fm.get_matrix(symbol, timeframe)


async def get_symbol_registry() -> Any:
    from services.strategy_service.symbol_registry import get_symbol_registry
    registry = get_symbol_registry()
    return registry


async def get_strategy_params(strategy_id: str) -> Dict[str, Any]:
    from services.strategy_service.strategy_param_store import get_strategy_param_store
    store = get_strategy_param_store()
    if store:
        return store.get_params(strategy_id)
    return {}


async def save_strategy_params(strategy_id: str, params: Dict[str, Any]) -> bool:
    from services.strategy_service.strategy_param_store import get_strategy_param_store
    store = get_strategy_param_store()
    if store:
        await store.save_params(strategy_id, params)
        return True
    return False


async def discover_strategies(symbol: str) -> List[Dict[str, Any]]:
    from services.strategy_service.strategy_discovery import StrategyDiscoveryEngine
    engine = StrategyDiscoveryEngine()
    return await engine.discover(symbol)


async def get_aggregation_status() -> Dict[str, Any]:
    from services.aggregation_service import get_aggregation_service
    service = get_aggregation_service()
    if service:
        return service.get_status()
    return {}


async def get_aggregation_feature_status(symbol: str, interval: Optional[str] = None) -> List[Dict[str, Any]]:
    from services.aggregation_service import get_feature_status as get_aggregation_feature_status
    return await get_aggregation_feature_status(symbol, interval)


async def extract_historical_features(symbol: str, years: List[int], intervals: List[str]) -> List[Dict[str, Any]]:
    from services.aggregation_service import extract_historical_features
    return await extract_historical_features(symbol, years, intervals)


async def get_correlation_service() -> Any:
    from services.correlation_service import get_correlation_service
    return await get_correlation_service()


async def get_projection_keys() -> Any:
    from services.projection_service.state_keys import ProjectionKeys
    return ProjectionKeys


async def get_projection_channels() -> Any:
    from services.projection_service.state_keys import ProjectionChannels
    return ProjectionChannels


def get_twitter_cookie_monitor() -> Any:
    from services.data_service.collectors.twitter_cookie_monitor import get_twitter_cookie_monitor
    return get_twitter_cookie_monitor()


def get_telegram_adapter() -> Any:
    from services.data_service.collectors.telegram_adapter import TelegramAdapter
    return TelegramAdapter


def get_strategy_param_store() -> Any:
    from services.strategy_service.strategy_param_store import get_strategy_param_store
    return get_strategy_param_store()


def get_strategy_discovery_engine(symbols: List[str] = None, **kwargs) -> Any:
    from services.strategy_service.strategy_discovery import StrategyDiscoveryEngine
    return StrategyDiscoveryEngine(symbols=symbols or [], **kwargs)


def get_feature_matrix_cls() -> Any:
    from services.strategy_service.feature_matrix import FeatureMatrix
    return FeatureMatrix
