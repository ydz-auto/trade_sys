"""
Feature Matrix Schemas - Feature Matrix Models
"""
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime

from application.queries.domain_queries import get_feature_category_enum

FeatureCategory = get_feature_category_enum()


class FeatureMetadataItem(BaseModel):
    """特征元数据项"""
    name: str
    name_en: str
    category: FeatureCategory
    description: str
    data_type: str = "float"
    normalization_range: Optional[tuple] = None
    is_factor: bool = False
    source: str = "internal"
    default_weight: float = 1.0
    last_updated: datetime = datetime.utcnow()


class FeatureValueItem(BaseModel):
    """特征值项"""
    name: str
    category: FeatureCategory
    value: float
    normalized_value: Optional[float] = None
    weight: float = 1.0
    confidence: int = 50


class FeatureMatrixSummary(BaseModel):
    """特征矩阵摘要"""
    symbol: str
    rows: int
    features_total: int
    features_raw: int
    features_derived: int
    features_microstructure: int
    features_cross_market: int
    features_event: int
    date_range: Optional[Dict[str, Any]] = None


class UpdateFeatureWeightRequest(BaseModel):
    """更新特征权重请求"""
    weight: float


class UpdateSymbolFeaturesRequest(BaseModel):
    """更新币种特征配置请求"""
    features: Dict[str, float]
    thresholds: Optional[Dict[str, float]] = None
