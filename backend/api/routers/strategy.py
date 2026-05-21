"""
Strategy Router - 策略管理端点

提供策略发现、回测、配置、启用/停用等功能
支持每个币种独立的策略参数管理
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ..services.strategy_api_service import get_strategy_api_service
from ..schemas.common import SuccessResponse

router = APIRouter()


class StrategyDiscoveryRequest(BaseModel):
    """策略发现请求"""
    symbol: str = Field(..., description="币种，如 BTCUSDT")


class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_id: str = Field(..., description="策略ID")
    symbol: str = Field(..., description="币种")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(default=10000, description="初始资金")


class StrategyConfigUpdate(BaseModel):
    """策略配置更新"""
    weight: Optional[float] = Field(None, description="权重")
    enabled: Optional[bool] = Field(None, description="是否启用")
    entry_params: Optional[dict] = Field(None, description="入场参数")
    exit_params: Optional[dict] = Field(None, description="出场参数")
    risk_params: Optional[dict] = Field(None, description="风险参数")
    feature_range: Optional[dict] = Field(None, description="历史数据特征范围")
    metadata: Optional[dict] = Field(None, description="元数据")


class FeatureRangeUpdate(BaseModel):
    """特征范围更新"""
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    volatility_range: Optional[str] = Field(None, description="波动率范围: low/medium/high/all")
    trend_range: Optional[str] = Field(None, description="趋势范围: up/down/ranging/all")
    volume_profile: Optional[str] = Field(None, description="成交量特征: low/medium/high/all")
    funding_range: Optional[str] = Field(None, description="资金费率范围")
    custom_filters: Optional[dict] = Field(None, description="自定义过滤条件")


class BatchUpdateRequest(BaseModel):
    """批量更新请求"""
    updates: List[dict] = Field(..., description="更新列表")


class DiscoveredStrategyResponse(BaseModel):
    """发现的策略响应"""
    id: str
    name: str
    description: str
    direction: int
    win_rate: float
    avg_return: float
    sample_size: int
    confidence: float
    strength: str
    features: dict
    conditions: List[str]
    created_at: str
    status: str


class StrategyDiscoveryResponse(BaseModel):
    """策略发现响应"""
    symbol: str
    strategies_found: int
    strategies: List[DiscoveredStrategyResponse]
    timestamp: str
    error: Optional[str] = None


class StrategyParamResponse(BaseModel):
    """策略参数响应"""
    strategy_id: str
    symbol: str
    enabled: bool
    weight: float
    entry_params: dict
    exit_params: dict
    risk_params: dict
    feature_range: dict
    source: str
    version: int
    created_at: str
    updated_at: str


def get_service():
    return get_strategy_api_service()


@router.post("/strategy/discover", response_model=StrategyDiscoveryResponse)
async def discover_strategies(request: StrategyDiscoveryRequest):
    """
    发现策略

    基于历史特征数据，自动扫描并发现有效的策略模式
    """
    result = await get_service().discover_strategies(request.symbol)

    strategies = [
        DiscoveredStrategyResponse(**s)
        for s in result.get("strategies", [])
    ]

    return StrategyDiscoveryResponse(
        symbol=result["symbol"],
        strategies_found=result["strategies_found"],
        strategies=strategies,
        timestamp=result["timestamp"],
        error=result.get("error"),
    )


@router.get("/strategy/discovered/{symbol}", response_model=List[DiscoveredStrategyResponse])
async def get_discovered_strategies(symbol: str):
    """获取已发现的策略"""
    strategies = await get_service().get_discovered_strategies(symbol)
    return [DiscoveredStrategyResponse(**s) for s in strategies]


@router.post("/strategy/watchlist/{strategy_id}", response_model=SuccessResponse)
async def add_to_watchlist(strategy_id: str):
    """添加到观察列表"""
    result = await get_service().add_to_watchlist(strategy_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Strategy not found"))
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} added to watchlist")


@router.delete("/strategy/watchlist/{strategy_id}", response_model=SuccessResponse)
async def remove_from_watchlist(strategy_id: str):
    """从观察列表移除"""
    result = await get_service().remove_from_watchlist(strategy_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Strategy not found"))
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} removed from watchlist")


@router.post("/strategy/backtest")
async def run_backtest(request: BacktestRequest):
    """运行回测"""
    result = await get_service().run_backtest(
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
    )
    return result


@router.get("/strategy/backtest/{backtest_id}")
async def get_backtest(backtest_id: str):
    """获取回测结果"""
    result = await get_service().get_backtest(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result


@router.get("/strategy/backtest/history")
async def list_backtests():
    """获取回测历史"""
    return await get_service().list_backtests()


@router.get("/strategy/configs")
async def get_strategy_configs():
    """获取所有策略配置"""
    return await get_service().get_strategy_configs()


@router.get("/strategy/configs/{strategy_id}/{symbol}")
async def get_strategy_config(strategy_id: str, symbol: str):
    """获取策略配置"""
    config = await get_service().get_strategy_config(strategy_id, symbol)
    if not config:
        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "weight": 1.0,
            "enabled": False,
            "parameters": {},
        }
    return config


@router.put("/strategy/configs/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def update_strategy_config(
    strategy_id: str,
    symbol: str,
    config: StrategyConfigUpdate,
):
    """更新策略配置"""
    config_dict = config.model_dump(exclude_none=True)
    result = await get_service().update_strategy_config(strategy_id, symbol, config_dict)
    return SuccessResponse(
        success=True,
        message=f"Config updated for {strategy_id}/{symbol}",
        data=result["config"],
    )


@router.post("/strategy/enable/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def enable_strategy(strategy_id: str, symbol: str):
    """启用策略"""
    result = await get_service().enable_strategy(strategy_id, symbol)
    return SuccessResponse(
        success=True,
        message=f"Strategy {strategy_id} enabled for {symbol}",
    )


@router.post("/strategy/disable/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def disable_strategy(strategy_id: str, symbol: str):
    """停用策略"""
    result = await get_service().disable_strategy(strategy_id, symbol)
    return SuccessResponse(
        success=True,
        message=f"Strategy {strategy_id} disabled for {symbol}",
    )


@router.get("/strategy/performance/{strategy_id}/{symbol}")
async def get_strategy_performance(strategy_id: str, symbol: str):
    """获取策略表现"""
    return await get_service().get_strategy_performance(strategy_id, symbol)


@router.get("/strategy/active")
async def get_active_strategies():
    """获取活跃策略"""
    return await get_service().get_active_strategies()


@router.get("/strategy/params/{symbol}")
async def get_symbol_params(symbol: str):
    """
    获取币种的所有策略参数
    
    返回指定币种下所有策略的参数配置
    """
    return await get_service().get_symbol_params(symbol)


@router.put("/strategy/feature-range/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def update_feature_range(
    strategy_id: str,
    symbol: str,
    feature_range: FeatureRangeUpdate,
):
    """
    更新历史数据特征范围
    
    用于选择回测/训练时使用的历史数据特征范围：
    - start_date/end_date: 时间范围
    - volatility_range: 波动率筛选 (low/medium/high/all)
    - trend_range: 趋势筛选 (up/down/ranging/all)
    - volume_profile: 成交量特征筛选
    - funding_range: 资金费率筛选
    """
    feature_dict = feature_range.model_dump(exclude_none=True)
    result = await get_service().update_feature_range(strategy_id, symbol, feature_dict)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update"))
    
    return SuccessResponse(
        success=True,
        message=f"Feature range updated for {strategy_id}/{symbol}",
        data=result["config"],
    )


@router.post("/strategy/params/batch", response_model=SuccessResponse)
async def batch_update_params(request: BatchUpdateRequest):
    """
    批量更新策略参数
    
    用于同时更新多个币种/策略的参数
    
    请求体示例:
    {
        "updates": [
            {
                "symbol": "BTCUSDT",
                "strategy_id": "rsi_strategy",
                "params": {"weight": 1.5, "enabled": true}
            },
            {
                "symbol": "ETHUSDT",
                "strategy_id": "macd_strategy",
                "params": {"weight": 1.2}
            }
        ]
    }
    """
    result = await get_service().batch_update_params(request.updates)
    
    return SuccessResponse(
        success=True,
        message=f"Batch update completed: {result['success']} success, {result['failed']} failed",
        data=result,
    )


@router.get("/strategy/history/{strategy_id}/{symbol}")
async def get_param_history(strategy_id: str, symbol: str, limit: int = 10):
    """
    获取参数历史版本
    
    返回策略参数的修改历史，用于审计和回滚
    """
    return await get_service().get_param_history(strategy_id, symbol, limit)


@router.post("/strategy/restore/{strategy_id}/{symbol}/{version}", response_model=SuccessResponse)
async def restore_param_version(strategy_id: str, symbol: str, version: int):
    """
    恢复到指定版本
    
    将策略参数恢复到历史版本
    """
    result = await get_service().restore_version(strategy_id, symbol, version)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to restore"))
    
    return SuccessResponse(
        success=True,
        message=f"Restored {strategy_id}/{symbol} to version {version}",
        data=result["config"],
    )


@router.get("/strategy/defaults/{strategy_type}")
async def get_strategy_defaults(strategy_type: str):
    """
    获取策略默认参数
    
    返回指定类型策略的默认参数配置
    """
    from domain.strategy.symbol_config import (
        RSIStrategyParams,
        MACDStrategyParams,
        PanicReversalParams,
        LongLiquidationBounceParams,
        VolumeClimaxFadeParams,
        WeakBounceShortParams,
    )
    
    defaults = {
        "rsi": RSIStrategyParams().__dict__,
        "macd": MACDStrategyParams().__dict__,
        "panic_reversal": PanicReversalParams().__dict__,
        "long_liquidation_bounce": LongLiquidationBounceParams().__dict__,
        "volume_climax_fade": VolumeClimaxFadeParams().__dict__,
        "weak_bounce_short": WeakBounceShortParams().__dict__,
    }
    
    if strategy_type not in defaults:
        raise HTTPException(status_code=404, detail=f"Unknown strategy type: {strategy_type}")
    
    return {
        "strategy_type": strategy_type,
        "defaults": defaults[strategy_type],
    }
