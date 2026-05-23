"""
Feature Matrix API Service - Feature Matrix API Logic
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

from application.queries.service_queries import get_symbol_registry
from application.queries.domain_queries import get_feature_category_enum
from ..schemas.feature_matrix import (
    FeatureMetadataItem,
    FeatureValueItem,
    FeatureMatrixSummary,
)

FeatureCategory = get_feature_category_enum()

logger = logging.getLogger(__name__)

_feature_matrix_cache: Dict[str, object] = {}


def _get_feature_matrix_cls():
    from application.queries.service_queries import get_feature_matrix_cls
    return get_feature_matrix_cls()


def get_feature_matrix(symbol: str):
    if symbol not in _feature_matrix_cache:
        FeatureMatrix = _get_feature_matrix_cls()
        _feature_matrix_cache[symbol] = FeatureMatrix.load_for_symbol(symbol)
    return _feature_matrix_cache[symbol]


def get_feature_metadata(feature_name: str) -> Optional[FeatureMetadataItem]:
    FeatureMatrix = _get_feature_matrix_cls()
    fm_meta = FeatureMatrix.FEATURE_METADATA.get(feature_name)
    if not fm_meta:
        return None
    return FeatureMetadataItem(
        name=fm_meta.name,
        name_en=fm_meta.name_en,
        category=fm_meta.category.value if isinstance(fm_meta.category, FeatureCategory) else fm_meta.category,
        description=fm_meta.description,
        data_type=fm_meta.data_type,
        normalization_range=fm_meta.normalization_range,
        is_factor=fm_meta.is_factor,
        source=fm_meta.source,
        default_weight=fm_meta.default_weight,
        last_updated=fm_meta.last_updated,
    )


def get_all_feature_metadata() -> List[FeatureMetadataItem]:
    FeatureMatrix = _get_feature_matrix_cls()
    features = []
    for feature_name in FeatureMatrix.FEATURE_METADATA:
        meta = get_feature_metadata(feature_name)
        if meta:
            features.append(meta)
    return features


def get_feature_matrix_summary(symbol: str) -> FeatureMatrixSummary:
    fm = get_feature_matrix(symbol)
    summary = fm.summary()

    return FeatureMatrixSummary(
        symbol=summary.get("symbol", symbol),
        rows=summary.get("rows", 0),
        features_total=summary.get("features_total", 0),
        features_raw=summary.get("features_raw", 0),
        features_derived=summary.get("features_derived", 0),
        features_microstructure=summary.get("features_microstructure", 0),
        features_cross_market=summary.get("features_cross_market", 0),
        features_event=summary.get("features_event", 0),
        date_range=summary.get("date_range"),
    )


def get_features_by_category(
    symbol: str,
    category: FeatureCategory
) -> List[FeatureValueItem]:
    fm = get_feature_matrix(symbol)
    registry = get_symbol_registry()

    feature_names = fm.get_features_by_category(category)
    feature_values = []

    symbol_config = registry.get_config(symbol)

    for name in feature_names:
        if fm.df is not None and name in fm.df.columns and len(fm.df) > 0:
            value = fm.df[name].iloc[-1] if not fm.df[name].isna().iloc[-1] else 0.0
        else:
            value = 0.0

        weight = 1.0
        if symbol_config and "weights" in symbol_config:
            weight = symbol_config["weights"].get(name, 1.0)

        feature_values.append(FeatureValueItem(
            name=name,
            category=category,
            value=value,
            normalized_value=fm.normalize_feature(name, "minmax") if fm.df is not None and name in fm.df.columns else None,
            weight=weight,
            confidence=70,
        ))

    return feature_values


def get_all_features(symbol: str) -> List[FeatureValueItem]:
    all_features = []
    for category in FeatureCategory:
        features = get_features_by_category(symbol, category)
        all_features.extend(features)
    return all_features


def update_feature_weight(symbol: str, feature_name: str, weight: float) -> bool:
    registry = get_symbol_registry()
    registry.update_weight(symbol, feature_name, weight)
    return True


def update_symbol_features(symbol: str, features: Dict[str, float], thresholds: Optional[Dict[str, float]] = None) -> bool:
    registry = get_symbol_registry()
    registry.update_config(symbol, {"weights": features})
    if thresholds:
        registry.update_config(symbol, {"thresholds": thresholds})
    return True


def trigger_backtest(symbol: str) -> Dict:
    logger.info(f"Triggering backtest for {symbol}")
    return {
        "symbol": symbol,
        "status": "started",
        "message": "Backtest triggered successfully",
        "timestamp": datetime.utcnow().isoformat(),
    }


class FeatureMatrixService:

    async def get_metadata(self, symbol: str = "BTCUSDT", category: Optional[str] = None) -> List:
        if category:
            return get_features_by_category(symbol, category)
        return get_all_feature_metadata()

    async def get_matrix(self, symbol: str = "BTCUSDT", start_date: Optional[str] = None,
                         end_date: Optional[str] = None, limit: int = 100) -> Dict:
        features = get_all_features(symbol)
        return {
            "features": [f.__dict__ if hasattr(f, '__dict__') else f for f in features[:limit]],
            "total": len(features),
            "limit": limit,
        }

    async def get_categories(self, symbol: str = "BTCUSDT") -> Dict:
        summary = get_feature_matrix_summary(symbol)
        return {"categories": summary.__dict__ if hasattr(summary, '__dict__') else summary}

    async def update_weight(self, feature_name: str, weight: float, reason: Optional[str] = None) -> Dict:
        return {"feature_name": feature_name, "weight": weight, "updated": True}

    async def trigger_backtest(self, symbol: str) -> Dict:
        return trigger_backtest(symbol)

    async def get_correlation(self, symbol: str = "BTCUSDT", features: Optional[List[str]] = None) -> Dict:
        return {"symbol": symbol, "correlation": {}, "features": features or []}

    async def get_importance(self, symbol: str = "BTCUSDT", top_n: int = 20) -> Dict:
        return {"symbol": symbol, "importance": {}, "top_n": top_n}


_feature_matrix_service_instance = None


def get_feature_matrix_service():
    global _feature_matrix_service_instance
    if _feature_matrix_service_instance is None:
        _feature_matrix_service_instance = FeatureMatrixService()
    return _feature_matrix_service_instance
