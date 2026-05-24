from typing import Any, Dict, List, Optional


def get_trading_modes() -> Dict[str, Any]:
    from domain.trading_mode import TradingMode, MODE_CONFIGS
    return {"modes": [m.value for m in TradingMode], "configs": {k: v for k, v in MODE_CONFIGS.items()}}


def get_trading_mode_manager() -> Any:
    from runtimes.trading_mode_manager import get_trading_mode_manager
    return get_trading_mode_manager()


def get_order_types() -> List[str]:
    from domain.execution.models import OrderType
    return [t.value for t in OrderType]


def get_order_sides() -> List[str]:
    from domain.execution.models import OrderSide
    return [s.value for s in OrderSide]


def get_exchanges() -> List[str]:
    from domain.execution.models import Exchange
    return [e.value for e in Exchange]


def get_market_types() -> List[str]:
    from domain.execution.models import MarketType
    return [m.value for m in MarketType]


def get_order_status_enum() -> Any:
    from domain.execution.models import OrderStatus
    return OrderStatus


def get_order_side_enum() -> Any:
    from domain.execution.models import OrderSide
    return OrderSide


def get_order_type_enum() -> Any:
    from domain.execution.models import OrderType
    return OrderType


def get_exchange_enum() -> Any:
    from domain.execution.models import Exchange
    return Exchange


def get_market_type_enum() -> Any:
    from domain.execution.models import MarketType
    return MarketType


def get_order_request_class() -> Any:
    from domain.execution.models import OrderRequest
    return OrderRequest


def get_feature_categories() -> Dict[str, Any]:
    from domain.feature.metadata import FeatureCategory
    return {c.name: c.value for c in FeatureCategory}


def get_feature_category_enum() -> Any:
    from domain.feature.metadata import FeatureCategory
    return FeatureCategory


def get_feature_matrix_info(symbol: str) -> Dict[str, Any]:
    from domain.feature.feature_matrix import get_feature_matrix_store
    store = get_feature_matrix_store()
    if store:
        return store.get_info(symbol)
    return {}


def get_historical_feature_matrix(symbol: str, **kwargs) -> Any:
    from domain.feature.feature_matrix import get_historical_feature_matrix
    return get_historical_feature_matrix(symbol=symbol, **kwargs)


def get_available_features() -> Any:
    from domain.feature.feature_matrix import get_available_features
    return get_available_features()


def get_materializer_status() -> Dict[str, Any]:
    return get_materializer_status()


def get_schema_registry() -> Any:
    from domain.feature.materializer.schema_registry import get_schema_registry
    return get_schema_registry()


def get_historical_feature_materializer(data_lake_root) -> Any:
    from engines.compute.feature.historical_materializer import HistoricalFeatureMaterializer
    return HistoricalFeatureMaterializer(data_lake_root)


def get_materializer_feature_category_enum() -> Any:
    from domain.feature.materializer.schema_registry import FeatureCategory
    return FeatureCategory


def get_symbol_config(symbol: str) -> Dict[str, Any]:
    from domain.strategy.symbol_config import get_symbol_config
    config = get_symbol_config(symbol)
    return config if config else {}


def get_strategy_default_params() -> Dict[str, Any]:
    from domain.strategy.symbol_config import (
        RSIStrategyParams, MACDStrategyParams, PanicReversalParams,
        LongLiquidationBounceParams, VolumeClimaxFadeParams, WeakBounceShortParams,
    )
    return {
        "rsi": RSIStrategyParams().__dict__,
        "macd": MACDStrategyParams().__dict__,
        "panic_reversal": PanicReversalParams().__dict__,
        "long_liquidation_bounce": LongLiquidationBounceParams().__dict__,
        "volume_climax_fade": VolumeClimaxFadeParams().__dict__,
        "weak_bounce_short": WeakBounceShortParams().__dict__,
    }


def get_execution_trading_mode() -> Any:
    from domain.execution.trading_mode import TradingMode
    return TradingMode


def get_execution_trading_mode_config() -> Any:
    from domain.execution.trading_mode import get_trading_mode_config
    return get_trading_mode_config()


def get_strategy_param_store() -> Any:
    from infrastructure.persistence.state.strategy_param_store import get_strategy_param_store
    return get_strategy_param_store()


def get_strategy_parameters_class() -> Any:
    from infrastructure.persistence.state.strategy_param_store import StrategyParameters
    return StrategyParameters


def get_feature_range_class() -> Any:
    from infrastructure.persistence.state.strategy_param_store import FeatureRange
    return FeatureRange
