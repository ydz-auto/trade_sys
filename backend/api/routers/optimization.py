"""
Optimization Router - 参数优化端点

架构：
    API Router (转发)
      ↓
    RuntimeBus.publish_command(run_optimization)
      ↓
    OptimizationService (Application 层，task management)
      ↓
    ReplayRuntime (唯一 execution source)
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
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
    optimization_start: str = Field(..., description="优化期开始 YYYY-MM-DD")
    optimization_end: str = Field(..., description="优化期结束 YYYY-MM-DD")
    backtest_start: str = Field(default="2025-01-01", description="回测期开始")
    backtest_end: str = Field(default="2026-04-30", description="回测期结束")
    method: OptimizationMethod = Field(default=OptimizationMethod.GRID_SEARCH)
    metric: OptimizationMetric = Field(default=OptimizationMetric.SHARPE)
    param_grid: Dict[str, List[Any]] = Field(default=None, description="参数网格")
    n_trials: int = Field(default=50, description="随机搜索次数")
    initial_capital: float = Field(default=10000, description="初始资金")
    commission: float = Field(default=0.0005, description="手续费")
    slippage: float = Field(default=0.0002, description="滑点")
    position_size: float = Field(default=0.3, description="仓位大小")
    stop_loss: float = Field(default=0.02, description="止损")
    take_profit: float = Field(default=0.04, description="止盈")
    max_hold_hours: int = Field(default=48, description="最大持仓时间")
    enable_slippage: bool = Field(default=True, description="启用滑点模拟")
    enable_latency: bool = Field(default=True, description="启用延迟模拟")


class BatchOptimizationRequest(BaseModel):
    symbols: List[str] = Field(default=["BTCUSDT"], description="币种列表")
    strategy_ids: List[str] = Field(..., description="策略ID列表")
    optimization_start: str = Field(default="2024-01-01")
    optimization_end: str = Field(default="2024-12-31")
    backtest_start: str = Field(default="2025-01-01")
    backtest_end: str = Field(default="2026-04-30")
    method: OptimizationMethod = Field(default=OptimizationMethod.GRID_SEARCH)
    metric: OptimizationMetric = Field(default=OptimizationMetric.SHARPE)


_optimization_results: Dict[str, Dict[str, Any]] = {}


@router.post("/optimization")
async def create_optimization(request: OptimizationRequest):
    """创建优化任务 - Router 只转发"""
    import uuid

    optimization_id = str(uuid.uuid4())[:8]
    _optimization_results[optimization_id] = {
        "optimization_id": optimization_id,
        "strategy_id": request.strategy_id,
        "symbol": request.symbol,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    import asyncio

    async def _run():
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
        )

        try:
            task = await service.create_task(
                strategy_id=request.strategy_id,
                symbol=request.symbol,
                config=config,
            )
            result = await service.run_task(task.task_id)

            _optimization_results[optimization_id].update({
                "status": result.status.value,
                "best_params": result.best_params,
                "best_score": result.best_score,
                "all_results": result.all_results,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "error": result.error,
            })
        except Exception as e:
            _optimization_results[optimization_id].update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            })

    asyncio.ensure_future(_run())

    return {
        "optimization_id": optimization_id,
        "strategy_id": request.strategy_id,
        "symbol": request.symbol,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }


@router.get("/optimization/{optimization_id}")
async def get_optimization(optimization_id: str):
    if optimization_id not in _optimization_results:
        raise HTTPException(status_code=404, detail="Optimization not found")
    return _optimization_results[optimization_id]


@router.get("/optimization")
async def list_optimizations():
    return {
        "optimizations": list(_optimization_results.values()),
        "total": len(_optimization_results),
    }


@router.post("/optimization/batch")
async def batch_optimization(request: BatchOptimizationRequest):
    """批量优化 - Router 只转发"""
    import uuid
    import asyncio
    task_ids = []

    for symbol in request.symbols:
        for strategy_id in request.strategy_ids:
            optimization_id = str(uuid.uuid4())[:8]
            task_ids.append(optimization_id)

            _optimization_results[optimization_id] = {
                "optimization_id": optimization_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }

            async def _run(sid: str, sym: str, opt_id: str):
                from application.optimization_service import get_optimization_service
                from application.optimization_service.models import OptimizationConfig

                service = get_optimization_service()
                config = OptimizationConfig(
                    optimization_start=request.optimization_start,
                    optimization_end=request.optimization_end,
                    backtest_start=request.backtest_start,
                    backtest_end=request.backtest_end,
                    method=request.method.value,
                    metric=request.metric.value,
                )

                try:
                    task = await service.create_task(
                        strategy_id=sid,
                        symbol=sym,
                        config=config,
                    )
                    result = await service.run_task(task.task_id)
                    _optimization_results[opt_id].update({
                        "status": result.status.value,
                        "best_params": result.best_params,
                        "best_score": result.best_score,
                        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                    })
                except Exception as e:
                    _optimization_results[opt_id].update({
                        "status": "failed",
                        "error": str(e),
                    })

            asyncio.ensure_future(
                _run(strategy_id, symbol, optimization_id),
            )

    return {
        "success": True,
        "message": f"Created {len(task_ids)} optimization tasks",
        "task_ids": task_ids,
    }


@router.delete("/optimization/{optimization_id}")
async def delete_optimization(optimization_id: str):
    if optimization_id in _optimization_results:
        del _optimization_results[optimization_id]
    return {"success": True}


@router.get("/optimization/strategies")
async def get_available_strategies():
    from application.optimization_service import get_optimization_service
    service = get_optimization_service()
    return {"strategies": service.get_available_strategies()}


@router.get("/optimization/runtime/status")
async def get_runtime_status():
    from application.commands.bus_commands import get_bus_stats

    bus_stats = await get_bus_stats()

    return {
        "runtime_pipeline": {
            "status": "active",
            "dispatch_via": "runtime_bus",
            "bus_stats": bus_stats,
        }
    }
