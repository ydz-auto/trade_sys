from fastapi import APIRouter, HTTPException
from uuid import uuid4

from api.schemas.backtest import (
    BacktestRequest,
    BacktestResult,
    BacktestListResponse,
    BacktestConfig,
    PerformanceMetrics,
    TradeRecord,
)
from application.commands.backtest import create_and_run_backtest, stop_backtest_task
from application.queries.replay import get_backtest, list_backtests

router = APIRouter()


@router.post("/backtest", response_model=BacktestResult)
async def create_and_run_backtest_endpoint(request: BacktestRequest):
    config = request.config.model_dump()
    backtest_id = str(uuid4())[:8]

    await create_and_run_backtest(backtest_id, config)

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
async def list_backtests_endpoint():
    backtests = await list_backtests()

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
async def get_backtest_endpoint(backtest_id: str):
    backtest = await get_backtest(backtest_id)

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
async def stop_backtest_endpoint(backtest_id: str):
    return await stop_backtest_task(backtest_id)
