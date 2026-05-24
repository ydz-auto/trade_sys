from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from application.queries.strategy import (
    discover_strategies,
    get_discovered_strategies,
    add_to_watchlist,
    remove_from_watchlist,
    run_backtest,
    get_backtest,
    list_backtests,
    get_strategy_configs,
    get_strategy_config,
    update_strategy_config,
    enable_strategy,
    disable_strategy,
    get_strategy_performance,
    get_active_strategies,
    get_symbol_params,
    update_feature_range,
    batch_update_params,
    get_param_history,
    restore_version,
)
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


class BatchUpdateRequest(BaseModel):
    updates: List[dict] = Field(..., description="更新列表")


@router.post("/strategy/discover")
async def discover_strategies_endpoint(request: StrategyDiscoveryRequest):
    return await discover_strategies(request.symbol)


@router.get("/strategy/discovered/{symbol}")
async def get_discovered_strategies_endpoint(symbol: str):
    return await get_discovered_strategies(symbol)


@router.post("/strategy/watchlist/{strategy_id}")
async def add_to_watchlist_endpoint(strategy_id: str):
    result = await add_to_watchlist(strategy_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Strategy not found"))
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} added to watchlist")


@router.delete("/strategy/watchlist/{strategy_id}")
async def remove_from_watchlist_endpoint(strategy_id: str):
    result = await remove_from_watchlist(strategy_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Strategy not found"))
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} removed from watchlist")


@router.post("/strategy/backtest")
async def run_backtest_endpoint(request: BacktestRequest):
    return await run_backtest(
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
    )


@router.get("/strategy/backtest/{backtest_id}")
async def get_backtest_endpoint(backtest_id: str):
    result = await get_backtest(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result


@router.get("/strategy/backtest/history")
async def list_backtests_endpoint():
    return await list_backtests()


@router.get("/strategy/configs")
async def get_strategy_configs_endpoint():
    return await get_strategy_configs()


@router.get("/strategy/configs/{strategy_id}/{symbol}")
async def get_strategy_config_endpoint(strategy_id: str, symbol: str):
    config = await get_strategy_config(strategy_id, symbol)
    if not config:
        return {"strategy_id": strategy_id, "symbol": symbol, "weight": 1.0, "enabled": False, "parameters": {}}
    return config


@router.put("/strategy/configs/{strategy_id}/{symbol}")
async def update_strategy_config_endpoint(
    strategy_id: str,
    symbol: str,
    config: StrategyConfigUpdate,
):
    config_dict = config.model_dump(exclude_none=True)
    result = await update_strategy_config(strategy_id, symbol, config_dict)
    return SuccessResponse(
        success=True,
        message=f"Config updated for {strategy_id}/{symbol}",
        data=result["config"],
    )


@router.post("/strategy/enable/{strategy_id}/{symbol}")
async def enable_strategy_endpoint(strategy_id: str, symbol: str):
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="enable_strategy",
        data={"strategy_id": strategy_id, "symbol": symbol},
        target="signal_runtime",
    )

    await enable_strategy(strategy_id, symbol)
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} enabled for {symbol}")


@router.post("/strategy/disable/{strategy_id}/{symbol}")
async def disable_strategy_endpoint(strategy_id: str, symbol: str):
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="disable_strategy",
        data={"strategy_id": strategy_id, "symbol": symbol},
        target="signal_runtime",
    )

    await disable_strategy(strategy_id, symbol)
    return SuccessResponse(success=True, message=f"Strategy {strategy_id} disabled for {symbol}")


@router.get("/strategy/performance/{strategy_id}/{symbol}")
async def get_strategy_performance_endpoint(strategy_id: str, symbol: str):
    return await get_strategy_performance(strategy_id, symbol)


@router.get("/strategy/active")
async def get_active_strategies_endpoint():
    return await get_active_strategies()


@router.get("/strategy/params/{symbol}")
async def get_symbol_params_endpoint(symbol: str):
    return await get_symbol_params(symbol)


@router.put("/strategy/feature-range/{strategy_id}/{symbol}")
async def update_feature_range_endpoint(strategy_id: str, symbol: str, feature_range: dict):
    result = await update_feature_range(strategy_id, symbol, feature_range)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update"))
    return SuccessResponse(success=True, message=f"Feature range updated for {strategy_id}/{symbol}", data=result["config"])


@router.post("/strategy/params/batch")
async def batch_update_params_endpoint(request: BatchUpdateRequest):
    result = await batch_update_params(request.updates)
    return SuccessResponse(
        success=True,
        message=f"Batch update completed: {result['success']} success, {result['failed']} failed",
        data=result,
    )


@router.get("/strategy/history/{strategy_id}/{symbol}")
async def get_param_history_endpoint(strategy_id: str, symbol: str, limit: int = 10):
    return await get_param_history(strategy_id, symbol, limit)


@router.post("/strategy/restore/{strategy_id}/{symbol}/{version}")
async def restore_param_version_endpoint(strategy_id: str, symbol: str, version: int):
    result = await restore_version(strategy_id, symbol, version)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to restore"))
    return SuccessResponse(success=True, message=f"Restored {strategy_id}/{symbol} to version {version}", data=result["config"])


@router.get("/strategy/defaults/{strategy_type}")
async def get_strategy_defaults(strategy_type: str):
    from application.queries.domain_queries import get_strategy_default_params

    defaults = get_strategy_default_params()
    if strategy_type not in defaults:
        raise HTTPException(status_code=404, detail=f"Unknown strategy type: {strategy_type}")
    return {"strategy_type": strategy_type, "defaults": defaults[strategy_type]}
