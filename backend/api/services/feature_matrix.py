"""
Feature Matrix API Service - Feature Matrix API Logic
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

from ...services.strategy_service.feature_matrix import (
    FeatureMatrix,
    FeatureCategory,
)
from ...services.strategy_service.symbol_registry import (
    SymbolStrategyRegistry,
    get_symbol_registry,
)
from ..schemas.feature_matrix import (
    FeatureMetadataItem,
    FeatureValueItem,
    FeatureMatrixSummary,
)

logger = logging.getLogger(__name__)

# 全局 Feature Matrix 实例缓存
_feature_matrix_cache: Dict[str, FeatureMatrix] = {}


def get_feature_matrix(symbol: str) -> FeatureMatrix:
    """获取并缓存 Feature Matrix 实例"""
    if symbol not in _feature_matrix_cache:
        _feature_matrix_cache[symbol] = FeatureMatrix.load_for_symbol(symbol)
    return _feature_matrix_cache[symbol]


def get_feature_metadata(feature_name: str) -> Optional[FeatureMetadataItem]:
    """获取特征元数据"""
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
    """获取所有特征元数据"""
    features = []
    for feature_name in FeatureMatrix.FEATURE_METADATA:
        meta = get_feature_metadata(feature_name)
        if meta:
            features.append(meta)
    return features


def get_feature_matrix_summary(symbol: str) -> FeatureMatrixSummary:
    """获取特征矩阵摘要"""
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
    """按分类获取特征值"""
    fm = get_feature_matrix(symbol)
    registry = get_symbol_registry()
    
    feature_names = fm.get_features_by_category(category)
    feature_values = []
    
    # 从注册表获取权重，否则使用默认值
    symbol_config = registry.get_config(symbol)
    
    for name in feature_names:
        if fm.df is not None and name in fm.df.columns and len(fm.df) > 0:
            # 获取最新值
            value = fm.df[name].iloc[-1] if not fm.df[name].isna().iloc[-1] else 0.0
        else:
            value = 0.0
        
        # 获取权重
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
    """获取所有特征值"""
    all_features = []
    for category in FeatureCategory:
        features = get_features_by_category(symbol, category)
        all_features.extend(features)
    return all_features


def update_feature_weight(symbol: str, feature_name: str, weight: float) -> bool:
    """更新特征权重"""
    registry = get_symbol_registry()
    registry.update_weight(symbol, feature_name, weight)
    return True


def update_symbol_features(symbol: str, features: Dict[str, float], thresholds: Optional[Dict[str, float]] = None) -> bool:
    """更新币种特征配置"""
    registry = get_symbol_registry()
    registry.update_config(symbol, {"weights": features})
    if thresholds:
        registry.update_config(symbol, {"thresholds": thresholds})
    return True


def trigger_backtest(symbol: str) -> Dict:
    """触发回测（占位实现）"""
    # TODO: 实现真实的回测逻辑
    logger.info(f"Triggering backtest for {symbol}")
    return {
        "symbol": symbol,
        "status": "started",
        "message": "Backtest triggered successfully",
        "timestamp": datetime.utcnow().isoformat(),
    }
