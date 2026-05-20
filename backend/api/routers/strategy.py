"""
Strategy Router - 策略管理端点

提供策略发现、回测、配置、启用/停用等功能
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
    parameters: Optional[dict] = Field(None, description="策略参数")


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
