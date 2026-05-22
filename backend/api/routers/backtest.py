"""
Backtest Router - 回测管理端点

架构：
    API Router
      ↓
    RuntimeBus (publish_command)
      ↓
    BacktestService
      ↓
    OptimizationBacktestEngine (走 ReplayRuntime)
      ↓
    runtime_bus
"""
from fastapi import APIRouter, HTTPException
from typing import List

from ..schemas.backtest import (
    BacktestRequest,
    BacktestResult,
    BacktestListResponse,
    BacktestConfig,
    PerformanceMetrics,
    TradeRecord,
)

from ..services.backtest_service import get_backtest_manager

router = APIRouter()


async def get_manager():
    manager = get_backtest_manager()
    await manager.ensure_connection()
    return manager


@router.post("/backtest", response_model=BacktestResult)
async def create_and_run_backtest(request: BacktestRequest):
    """创建并运行回测 - 通过 RuntimeBus 调度"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    config = request.config.model_dump()

    await bus.publish_command(
        command="run_backtest",
        target="backtest_service",
        params=config,
        source="api.backtest",
    )

    manager = await get_manager()

    backtest = await manager.create_backtest(config)
    backtest_id = backtest["id"]

    result = await manager.run_backtest(backtest_id)

    metrics = None
    if result.get("metrics"):
        metrics = PerformanceMetrics(**result["metrics"])

    trades = [TradeRecord(**t) for t in result.get("trades", [])]

    return BacktestResult(
        id=result["id"],
        status=result["status"],
        config=BacktestConfig(**result["config"]),
        metrics=metrics,
        trades=trades,
        equity_curve=result.get("equity_curve", []),
        drawdown_curve=result.get("drawdown_curve", []),
        start_date=result.get("start_date"),
        end_date=result.get("end_date"),
        duration_days=result.get("duration_days", 0),
        created_at=result["created_at"],
        completed_at=result.get("completed_at"),
        error_message=result.get("error_message"),
    )


@router.get("/backtest", response_model=BacktestListResponse)
async def list_backtests():
    """获取回测列表"""
    manager = await get_manager()
    backtests = await manager.list_backtests()

    results = []
    for b in backtests:
        metrics = None
        if b.get("metrics"):
            try:
                metrics = PerformanceMetrics(**b["metrics"])
            except:
                pass

        trades = []
        for t in b.get("trades", []):
            try:
                trades.append(TradeRecord(**t))
            except:
                pass

        results.append(BacktestResult(
            id=b["id"],
            status=b["status"],
            config=BacktestConfig(**b["config"]) if b.get("config") else BacktestConfig(start_date="", end_date=""),
            metrics=metrics,
            trades=trades,
            equity_curve=b.get("equity_curve", []),
            drawdown_curve=b.get("drawdown_curve", []),
            created_at=b["created_at"],
            completed_at=b.get("completed_at"),
            error_message=b.get("error_message"),
        ))

    return BacktestListResponse(backtests=results, total=len(results))


@router.get("/backtest/{backtest_id}", response_model=BacktestResult)
async def get_backtest(backtest_id: str):
    """获取回测详情"""
    manager = await get_manager()
    backtest = await manager.get_backtest(backtest_id)

    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")

    metrics = None
    if backtest.get("metrics"):
        try:
            metrics = PerformanceMetrics(**backtest["metrics"])
        except:
            pass

    trades = []
    for t in backtest.get("trades", []):
        try:
            trades.append(TradeRecord(**t))
        except:
            pass

    return BacktestResult(
        id=backtest["id"],
        status=backtest["status"],
        config=BacktestConfig(**backtest["config"]) if backtest.get("config") else BacktestConfig(start_date="", end_date=""),
        metrics=metrics,
        trades=trades,
        equity_curve=backtest.get("equity_curve", []),
        drawdown_curve=backtest.get("drawdown_curve", []),
        start_date=backtest.get("start_date"),
        end_date=backtest.get("end_date"),
        duration_days=backtest.get("duration_days", 0),
        created_at=backtest["created_at"],
        completed_at=backtest.get("completed_at"),
        error_message=backtest.get("error_message"),
    )
