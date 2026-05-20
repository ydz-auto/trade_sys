"""
Feature Matrix Router - Feature Matrix Endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List

from ..schemas.feature_matrix import (
    FeatureMetadataItem,
    FeatureValueItem,
    FeatureMatrixSummary,
    UpdateFeatureWeightRequest,
    UpdateSymbolFeaturesRequest,
    FeatureCategory,
)
from ..schemas.common import SuccessResponse
from ..services import feature_matrix as fm_service

router = APIRouter()


@router.get("/features/metadata", response_model=List[FeatureMetadataItem])
async def get_feature_metadata_endpoint():
    """获取所有特征元数据"""
    return fm_service.get_all_feature_metadata()


@router.get("/features/metadata/{feature_name}", response_model=FeatureMetadataItem)
async def get_single_feature_metadata_endpoint(feature_name: str):
    """获取单个特征元数据"""
    meta = fm_service.get_feature_metadata(feature_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Feature {feature_name} not found")
    return meta


@router.get("/features/{symbol}", response_model=List[FeatureValueItem])
async def get_symbol_features_endpoint(symbol: str):
    """获取币种特征矩阵"""
    return fm_service.get_all_features(symbol)


@router.get("/features/{symbol}/summary", response_model=FeatureMatrixSummary)
async def get_feature_matrix_summary_endpoint(symbol: str):
    """获取特征矩阵摘要"""
    return fm_service.get_feature_matrix_summary(symbol)


@router.get("/features/{symbol}/category/{category}", response_model=List[FeatureValueItem])
async def get_features_by_category_endpoint(symbol: str, category: FeatureCategory):
    """按分类获取特征"""
    return fm_service.get_features_by_category(symbol, category)


@router.put("/features/{symbol}/weight/{feature_name}", response_model=SuccessResponse)
async def update_feature_weight_endpoint(
    symbol: str,
    feature_name: str,
    request: UpdateFeatureWeightRequest
):
    """更新特征权重"""
    success = fm_service.update_feature_weight(symbol, feature_name, request.weight)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update feature weight")
    return SuccessResponse(
        success=True,
        message=f"Weight updated for {feature_name} in {symbol}",
    )


@router.put("/features/{symbol}", response_model=SuccessResponse)
async def update_symbol_features_endpoint(
    symbol: str,
    request: UpdateSymbolFeaturesRequest
):
    """更新币种特征配置"""
    success = fm_service.update_symbol_features(symbol, request.features, request.thresholds)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update symbol features")
    return SuccessResponse(
        success=True,
        message=f"Features updated for {symbol}",
    )


@router.post("/features/{symbol}/backtest", response_model=SuccessResponse)
async def trigger_backtest_endpoint(symbol: str):
    """触发特征回测"""
    result = fm_service.trigger_backtest(symbol)
    return SuccessResponse(
        success=True,
        message=result.get("message"),
        data=result,
    )
