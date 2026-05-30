"""Feature Queries - 特征状态查询入口

API Router 只调此模块，不直接碰 runtime/services/infrastructure。
"""
from typing import Dict, Any, List, Optional

import logging

logger = logging.getLogger(__name__)


async def get_feature_state() -> Dict[str, Any]:
    # TODO: migrate to new runtime architecture - runtime.feature_runtime removed
    # from runtime.feature_runtime import get_feature_runtime
    # runtime = get_feature_runtime()
    # if runtime and hasattr(runtime, 'get_state'):
    #     return runtime.get_state()
    return {}


async def get_feature_matrix_state() -> Dict[str, Any]:
    # TODO: migrate to new runtime architecture - runtime.feature_runtime removed
    # from runtime.feature_runtime.feature_matrix_runtime import get_feature_matrix_runtime
    # runtime = get_feature_matrix_runtime()
    # if runtime and hasattr(runtime, 'get_state'):
    #     return runtime.get_state()
    return {}


async def get_feature_metadata(symbol: str = "BTCUSDT", category: Optional[str] = None) -> List[Dict[str, Any]]:
    from application.queries.domain_queries import get_feature_category_enum, get_available_features

    FeatureCategory = get_feature_category_enum()
    features = get_available_features()

    if category:
        cat_enum = FeatureCategory(category)
        return [f for f in features if f.get("category") == cat_enum.value]
    return features


async def get_feature_matrix(
    symbol: str = "BTCUSDT",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    from application.queries.service_queries import get_feature_matrix_cls

    FeatureMatrix = get_feature_matrix_cls()
    fm = FeatureMatrix.load_for_symbol(symbol)
    features = []

    if fm and hasattr(fm, 'df') and fm.df is not None:
        for col in fm.df.columns[:limit]:
            val = fm.df[col].iloc[-1] if len(fm.df) > 0 and not fm.df[col].isna().iloc[-1] else 0.0
            features.append({"name": col, "value": val})

    return {"features": features, "total": len(features), "limit": limit}


async def get_feature_categories(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    from application.queries.domain_queries import get_feature_category_enum

    FeatureCategory = get_feature_category_enum()
    categories = [{"name": c.name, "value": c.value} for c in FeatureCategory]
    return {"categories": categories}


async def update_feature_weight(feature_name: str, weight: float, reason: Optional[str] = None) -> Dict[str, Any]:
    from application.queries.service_queries import get_symbol_registry

    registry = get_symbol_registry()
    if registry and hasattr(registry, 'update_weight'):
        registry.update_weight("BTCUSDT", feature_name, weight)
    return {"feature_name": feature_name, "weight": weight, "updated": True}


async def trigger_feature_backtest(symbol: str) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="run_backtest",
        data={"symbol": symbol, "source": "feature_matrix"},
        target="replay_runtime",
    )
    return {
        "symbol": symbol,
        "status": "started",
        "message": "Backtest triggered via RuntimeBus",
    }


async def get_feature_correlation(symbol: str = "BTCUSDT", features: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"symbol": symbol, "correlation": {}, "features": features or []}


async def get_feature_importance(symbol: str = "BTCUSDT", top_n: int = 20) -> Dict[str, Any]:
    return {"symbol": symbol, "importance": {}, "top_n": top_n}
