"""
Strategy Router - 策略管理端点

架构：
    API Router
      ↓
    StrategyAPIService (配置管理)
      ↓
    RuntimeBus (回测命令 → ReplayRuntime)
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ..services.strategy_api_service import get_strategy_api_service
from ..schemas.common import SuccessResponse

router = APIRouter()


class StrategyDiscoveryRequest(BaseModel):
    symbol: str = Field(..., description="币种，如 BTCUSDT")


class BacktestRequest(BaseModel):
    strategy_id: str = Field(..., description="策略ID")
    symbol: str = Field(..., description="币种")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(default=10000, description="初始资金")


class StrategyConfigUpdate(BaseModel):
    weight: Optional[float] = Field(None, description="权重")
    enabled: Optional[bool] = Field(None, description="是否启用")
    entry_params: Optional[dict] = Field(None, description="入场参数")
    exit_params: Optional[dict] = Field(None, description="出场参数")
    risk_params: Optional[dict] = Field(None, description="风险参数")
    feature_range: Optional[dict] = Field(None, description="历史数据特征范围")
    metadata: Optional[dict] = Field(None, description="元数据")


class FeatureRangeUpdate(BaseModel):
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    volatility_range: Optional[str] = Field(None, description="波动率范围: low/medium/high/all")
    trend_range: Optional[str] = Field(None, description="趋势范围: up/down/ranging/all")
    volume_profile: Optional[str] = Field(None, description="成交量特征: low/medium/high/all")
    funding_range: Optional[str] = Field(None, description="资金费率范围")
    custom_filters: Optional[dict] = Field(None, description="自定义过滤条件")


class BatchUpdateRequest(BaseModel):
    updates: List[dict] = Field(..., description="更新列表")


class DiscoveredStrategyResponse(BaseModel):
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
    symbol: str
    strategies_found: int
    strategies: List[DiscoveredStrategyResponse]
    timestamp: str
    error: Optional[str] = None


class StrategyParamResponse(BaseModel):
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
    strategies = await get_service().get_discovered_strategies(symbol)
    return [DiscoveredStrategyResponse(**s) for s in strategies]


@router.post("/strategy/watchlist/{strategy_id}", response_model=SuccessResponse)
async def add_to_watchlist(strategy_id: str):
    result = await get_service().add_to_watchlist(strategy_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Strategy not found"))
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} added to watchlist")


@router.delete("/strategy/watchlist/{strategy_id}", response_model=SuccessResponse)
async def remove_from_watchlist(strategy_id: str):
    result = await get_service().remove_from_watchlist(strategy_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Strategy not found"))
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} removed from watchlist")


@router.post("/strategy/backtest")
async def run_backtest(request: BacktestRequest):
    """运行回测 - 通过 RuntimeBus 调度到 ReplayRuntime"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="run_backtest",
        target="backtest_service",
        params={
            "strategy_id": request.strategy_id,
            "symbol": request.symbol,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "initial_capital": request.initial_capital,
        },
        source="api.strategy",
    )

    result = await get_service().run_backtest_via_runtime(
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
    )
    return result


@router.get("/strategy/backtest/{backtest_id}")
async def get_backtest(backtest_id: str):
    result = await get_service().get_backtest(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result


@router.get("/strategy/backtest/history")
async def list_backtests():
    return await get_service().list_backtests()


@router.get("/strategy/configs")
async def get_strategy_configs():
    return await get_service().get_strategy_configs()


@router.get("/strategy/configs/{strategy_id}/{symbol}")
async def get_strategy_config(strategy_id: str, symbol: str):
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
    config_dict = config.model_dump(exclude_none=True)
    result = await get_service().update_strategy_config(strategy_id, symbol, config_dict)
    return SuccessResponse(
        success=True,
        message=f"Config updated for {strategy_id}/{symbol}",
        data=result["config"],
    )


@router.post("/strategy/enable/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def enable_strategy(strategy_id: str, symbol: str):
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="enable_strategy",
        target="signal_runtime",
        params={"strategy_id": strategy_id, "symbol": symbol},
        source="api.strategy",
    )

    result = await get_service().enable_strategy(strategy_id, symbol)
    return SuccessResponse(
        success=True,
        message=f"Strategy {strategy_id} enabled for {symbol}",
    )


@router.post("/strategy/disable/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def disable_strategy(strategy_id: str, symbol: str):
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="disable_strategy",
        target="signal_runtime",
        params={"strategy_id": strategy_id, "symbol": symbol},
        source="api.strategy",
    )

    result = await get_service().disable_strategy(strategy_id, symbol)
    return SuccessResponse(
        success=True,
        message=f"Strategy {strategy_id} disabled for {symbol}",
    )


@router.get("/strategy/performance/{strategy_id}/{symbol}")
async def get_strategy_performance(strategy_id: str, symbol: str):
    return await get_service().get_strategy_performance(strategy_id, symbol)


@router.get("/strategy/active")
async def get_active_strategies():
    return await get_service().get_active_strategies()


@router.get("/strategy/params/{symbol}")
async def get_symbol_params(symbol: str):
    return await get_service().get_symbol_params(symbol)


@router.put("/strategy/feature-range/{strategy_id}/{symbol}", response_model=SuccessResponse)
async def update_feature_range(
    strategy_id: str,
    symbol: str,
    feature_range: FeatureRangeUpdate,
):
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
    result = await get_service().batch_update_params(request.updates)

    return SuccessResponse(
        success=True,
        message=f"Batch update completed: {result['success']} success, {result['failed']} failed",
        data=result,
    )


@router.get("/strategy/history/{strategy_id}/{symbol}")
async def get_param_history(strategy_id: str, symbol: str, limit: int = 10):
    return await get_service().get_param_history(strategy_id, symbol, limit)


@router.post("/strategy/restore/{strategy_id}/{symbol}/{version}", response_model=SuccessResponse)
async def restore_param_version(strategy_id: str, symbol: str, version: int):
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
