"""
Backtest Router - 回测管理端点

架构：
    API Router (转发)
      ↓
    RuntimeBus.publish_command(run_backtest)
      ↓
    BacktestManager (task persistence)
      ↓
    ReplayRuntime (唯一 execution source)
"""
from fastapi import APIRouter, HTTPException

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
    """创建并运行回测 - Router 只转发"""
    from runtime.bus.runtime_bus import get_runtime_bus
    from uuid import uuid4

    bus = get_runtime_bus()
    config = request.config.model_dump()
    backtest_id = str(uuid4())[:8]

    await bus.publish_command(
        command="run_backtest",
        target="replay_runtime",
        params={"backtest_id": backtest_id, **config},
        source="api.backtest",
    )

    manager = await get_manager()
    await manager.start(backtest_id, config)

    return BacktestResult(
        id=backtest_id,
        status="pending",
        config=BacktestConfig(**config),
        metrics=None,
        trades=[],
        equity_curve=[],
        drawdown_curve=[],
        created_at="",
    )


@router.get("/backtest", response_model=BacktestListResponse)
async def list_backtests():
    """获取回测列表"""
    manager = await get_manager()
    backtests = await manager.list()

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
    backtest = await manager.query(backtest_id)

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


@router.delete("/backtest/{backtest_id}")
async def stop_backtest(backtest_id: str):
    """停止回测"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="stop_backtest",
        target="replay_runtime",
        params={"backtest_id": backtest_id},
        source="api.backtest",
    )

    manager = await get_manager()
    return await manager.stop(backtest_id)
