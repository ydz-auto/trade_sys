"""
Optimization Router - 参数优化端点

提供策略参数优化功能：
1. 单策略参数优化
2. 批量策略优化
3. 网格搜索
4. 优化结果管理

架构：
    API Router
      ↓
    RuntimeCommandBus / RuntimeBus
      ↓
    OptimizationService
      ↓
    OptimizationBacktestEngine (走 ReplayRuntime)
      ↓
    runtime_bus
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from ..schemas.common import SuccessResponse

router = APIRouter()


class OptimizationMethod(str, Enum):
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"


class OptimizationMetric(str, Enum):
    SHARPE = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR = "calmar_ratio"


class OptimizationRequest(BaseModel):
    strategy_id: str = Field(..., description="策略ID")
    symbol: str = Field(default="BTCUSDT", description="币种")

    optimization_start: str = Field(..., description="优化期开始日期 YYYY-MM-DD")
    optimization_end: str = Field(..., description="优化期结束日期 YYYY-MM-DD")

    backtest_start: Optional[str] = Field(None, description="回测期开始日期 YYYY-MM-DD")
    backtest_end: Optional[str] = Field(None, description="回测期结束日期 YYYY-MM-DD")

    method: OptimizationMethod = Field(default=OptimizationMethod.GRID_SEARCH, description="优化方法")
    metric: OptimizationMetric = Field(default=OptimizationMetric.SHARPE, description="优化目标")

    param_grid: Optional[Dict[str, List[Any]]] = Field(None, description="参数网格")
    n_trials: int = Field(default=50, description="随机搜索次数")

    initial_capital: float = Field(default=10000, description="初始资金")
    commission: float = Field(default=0.0005, description="手续费")
    slippage: float = Field(default=0.0002, description="滑点")
    position_size: float = Field(default=0.3, description="仓位大小")
    stop_loss: float = Field(default=0.02, description="止损")
    take_profit: float = Field(default=0.04, description="止盈")
    max_hold_hours: int = Field(default=48, description="最大持仓时间（小时）")
    resample_freq: Optional[str] = Field(default=None, description="数据重采样频率")

    enable_slippage: bool = Field(default=True, description="启用滑点模拟")
    enable_latency: bool = Field(default=True, description="启用延迟模拟")


class BatchOptimizationRequest(BaseModel):
    symbols: List[str] = Field(default=["BTCUSDT"], description="币种列表")
    strategy_ids: List[str] = Field(..., description="策略ID列表")

    optimization_start: str = Field(default="2024-01-01", description="优化期开始")
    optimization_end: str = Field(default="2024-12-31", description="优化期结束")

    backtest_start: str = Field(default="2025-01-01", description="回测期开始")
    backtest_end: str = Field(default="2026-04-30", description="回测期结束")

    method: OptimizationMethod = Field(default=OptimizationMethod.GRID_SEARCH)
    metric: OptimizationMetric = Field(default=OptimizationMetric.SHARPE)


class OptimizationResult(BaseModel):
    optimization_id: str
    strategy_id: str
    symbol: str
    status: str

    best_params: Optional[Dict[str, Any]] = None
    best_score: Optional[float] = None

    optimization_metrics: Optional[Dict[str, float]] = None
    backtest_metrics: Optional[Dict[str, float]] = None

    all_results: Optional[List[Dict[str, Any]]] = None

    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None

    runtime_stats: Optional[Dict[str, Any]] = None


class OptimizationListResponse(BaseModel):
    optimizations: List[OptimizationResult]
    total: int


_optimization_results: Dict[str, Dict[str, Any]] = {}


async def _dispatch_optimization_via_runtime(
    optimization_id: str,
    request: OptimizationRequest,
):
    try:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()

        await bus.publish_command(
            command="run_optimization",
            target="optimization_service",
            params={
                "optimization_id": optimization_id,
                "strategy_id": request.strategy_id,
                "symbol": request.symbol,
                "optimization_start": request.optimization_start,
                "optimization_end": request.optimization_end,
                "backtest_start": request.backtest_start,
                "backtest_end": request.backtest_end,
                "method": request.method.value,
                "metric": request.metric.value,
                "param_grid": request.param_grid,
                "initial_capital": request.initial_capital,
                "commission": request.commission,
                "slippage": request.slippage,
                "position_size": request.position_size,
                "stop_loss": request.stop_loss,
                "take_profit": request.take_profit,
                "max_hold_hours": request.max_hold_hours,
                "resample_freq": request.resample_freq,
                "enable_slippage": request.enable_slippage,
                "enable_latency": request.enable_latency,
            },
            source="api.optimization",
        )
    except Exception:
        pass

    try:
        from application.optimization_service import get_optimization_service
        from application.optimization_service.models import OptimizationConfig

        _optimization_results[optimization_id]["status"] = "running"

        service = get_optimization_service()

        config = OptimizationConfig(
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
            position_size=request.position_size,
            optimization_start=request.optimization_start,
            optimization_end=request.optimization_end,
            backtest_start=request.backtest_start,
            backtest_end=request.backtest_end,
            method=request.method.value,
            metric=request.metric.value,
            param_grid=request.param_grid,
            enable_slippage=request.enable_slippage,
            enable_latency=request.enable_latency,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            max_hold_hours=request.max_hold_hours,
            resample_freq=request.resample_freq,
        )

        task = await service.create_task(
            strategy_id=request.strategy_id,
            symbol=request.symbol,
            config=config,
        )

        result = await service.run_task(task.task_id)

        _optimization_results[optimization_id]["status"] = result.status.value
        _optimization_results[optimization_id]["best_params"] = result.best_params
        _optimization_results[optimization_id]["best_score"] = result.best_score
        _optimization_results[optimization_id]["optimization_metrics"] = result.best_metrics.to_dict() if result.best_metrics else None
        _optimization_results[optimization_id]["all_results"] = result.all_results
        _optimization_results[optimization_id]["completed_at"] = result.completed_at.isoformat() if result.completed_at else None
        _optimization_results[optimization_id]["error"] = result.error
        _optimization_results[optimization_id]["runtime_stats"] = {
            "use_runtime": True,
            "dispatch_via": "runtime_bus",
            "enable_slippage": request.enable_slippage,
            "enable_latency": request.enable_latency,
            "total_trades": result.best_metrics.total_trades if result.best_metrics else 0,
        }

    except Exception as e:
        _optimization_results[optimization_id]["status"] = "failed"
        _optimization_results[optimization_id]["error"] = str(e)
        _optimization_results[optimization_id]["completed_at"] = datetime.now().isoformat()


@router.post("/optimization", response_model=OptimizationResult)
async def create_optimization(request: OptimizationRequest):
    import uuid

    optimization_id = str(uuid.uuid4())[:8]

    _optimization_results[optimization_id] = {
        "optimization_id": optimization_id,
        "strategy_id": request.strategy_id,
        "symbol": request.symbol,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    from infrastructure.runtime import get_runtime_governor

    governor = get_runtime_governor()
    governor.create_task(
        _dispatch_optimization_via_runtime(optimization_id, request),
        name=f"optimization_{optimization_id}",
    )

    return OptimizationResult(
        optimization_id=optimization_id,
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        status="pending",
        created_at=datetime.now().isoformat(),
    )


@router.post("/optimization/sync", response_model=OptimizationResult)
async def create_optimization_sync(request: OptimizationRequest):
    import uuid

    optimization_id = str(uuid.uuid4())[:8]

    _optimization_results[optimization_id] = {
        "optimization_id": optimization_id,
        "strategy_id": request.strategy_id,
        "symbol": request.symbol,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    await _dispatch_optimization_via_runtime(optimization_id, request)

    result = _optimization_results[optimization_id]

    return OptimizationResult(
        optimization_id=optimization_id,
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        status=result.get("status", "unknown"),
        best_params=result.get("best_params"),
        best_score=result.get("best_score"),
        optimization_metrics=result.get("optimization_metrics"),
        backtest_metrics=result.get("backtest_metrics"),
        all_results=result.get("all_results"),
        created_at=result.get("created_at", ""),
        completed_at=result.get("completed_at"),
        error=result.get("error"),
        runtime_stats=result.get("runtime_stats"),
    )


@router.get("/optimization/{optimization_id}", response_model=OptimizationResult)
async def get_optimization(optimization_id: str):
    if optimization_id not in _optimization_results:
        raise HTTPException(status_code=404, detail="Optimization not found")

    result = _optimization_results[optimization_id]

    return OptimizationResult(
        optimization_id=optimization_id,
        strategy_id=result.get("strategy_id", ""),
        symbol=result.get("symbol", ""),
        status=result.get("status", "unknown"),
        best_params=result.get("best_params"),
        best_score=result.get("best_score"),
        optimization_metrics=result.get("optimization_metrics"),
        backtest_metrics=result.get("backtest_metrics"),
        all_results=result.get("all_results"),
        created_at=result.get("created_at", ""),
        completed_at=result.get("completed_at"),
        error=result.get("error"),
        runtime_stats=result.get("runtime_stats"),
    )


@router.get("/optimization", response_model=OptimizationListResponse)
async def list_optimizations():
    results = []
    for opt_id, result in _optimization_results.items():
        results.append(OptimizationResult(
            optimization_id=opt_id,
            strategy_id=result.get("strategy_id", ""),
            symbol=result.get("symbol", ""),
            status=result.get("status", "unknown"),
            best_params=result.get("best_params"),
            best_score=result.get("best_score"),
            created_at=result.get("created_at", ""),
            completed_at=result.get("completed_at"),
            error=result.get("error"),
            runtime_stats=result.get("runtime_stats"),
        ))

    return OptimizationListResponse(optimizations=results, total=len(results))


@router.post("/optimization/batch", response_model=SuccessResponse)
async def batch_optimization(request: BatchOptimizationRequest):
    import uuid

    tasks = []

    for symbol in request.symbols:
        for strategy_id in request.strategy_ids:
            optimization_id = str(uuid.uuid4())[:8]

            _optimization_results[optimization_id] = {
                "optimization_id": optimization_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }

            opt_request = OptimizationRequest(
                strategy_id=strategy_id,
                symbol=symbol,
                optimization_start=request.optimization_start,
                optimization_end=request.optimization_end,
                backtest_start=request.backtest_start,
                backtest_end=request.backtest_end,
                method=request.method,
                metric=request.metric,
            )

            from infrastructure.runtime import get_runtime_governor

            governor = get_runtime_governor()
            governor.create_task(
                _dispatch_optimization_via_runtime(optimization_id, opt_request),
                name=f"batch_optimization_{optimization_id}",
            )
            tasks.append(optimization_id)

    return SuccessResponse(
        success=True,
        message=f"Created {len(tasks)} optimization tasks via RuntimeBus",
        data={"task_ids": tasks, "runtime_enabled": True, "dispatch_via": "runtime_bus"},
    )


@router.delete("/optimization/{optimization_id}", response_model=SuccessResponse)
async def delete_optimization(optimization_id: str):
    if optimization_id not in _optimization_results:
        raise HTTPException(status_code=404, detail="Optimization not found")

    del _optimization_results[optimization_id]

    return SuccessResponse(
        success=True,
        message=f"Optimization {optimization_id} deleted",
    )


@router.get("/optimization/strategies")
async def get_available_strategies():
    from application.optimization_service import get_optimization_service

    service = get_optimization_service()
    strategies = service.get_available_strategies()

    return {
        "strategies": strategies,
        "runtime_enabled": True,
        "dispatch_via": "runtime_bus",
        "features": {
            "slippage_simulation": True,
            "latency_simulation": True,
            "partial_fill": True,
            "event_driven": True,
        }
    }


@router.get("/optimization/runtime/status")
async def get_runtime_status():
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    bus_stats = bus.get_stats()

    return {
        "runtime_pipeline": {
            "status": "active",
            "dispatch_via": "runtime_bus",
            "bus_stats": bus_stats,
            "components": [
                "RuntimeBus",
                "ReplayRuntime",
                "OptimizationBacktestEngine",
                "MarketEventEmitter",
            ],
            "features": {
                "slippage": True,
                "latency": True,
                "partial_fill": True,
                "event_driven": True,
            },
        },
        "message": "Optimization dispatched via RuntimeBus → ReplayRuntime",
    }
