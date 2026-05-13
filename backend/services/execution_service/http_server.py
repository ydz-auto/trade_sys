"""
Execution Service HTTP Server

提供健康检查、API 端点
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Response
from pydantic import BaseModel

from domain.execution.models import OrderIntent, OrderSide, OrderType, MarketType, Exchange
from services.execution_service.engine import init_execution_engine
from services.execution_service.adapters import MockAdapter, BinanceAdapter, BinanceFuturesAdapter, OKXAdapter
from services.execution_service.risk.risk_engine import RiskEngine
from services.execution_service.risk.position_limit import PositionLimitChecker
from services.execution_service.risk.leverage_limit import LeverageLimitChecker
from services.execution_service.risk.daily_loss_limit import DailyLossLimitChecker
from services.execution_service.risk.cooldown_checker import CooldownChecker
from services.execution_service.risk.drawdown_limit import DrawdownLimitChecker
from services.execution_service.risk.order_size_limit import OrderSizeLimitChecker
from services.execution_service.risk.symbol_blacklist import SymbolBlacklistChecker
from services.execution_service.risk.stop_loss_check import StopLossTPCheckChecker
from services.execution_service.storage import init_db
from services.execution_service.metrics import get_execution_metrics
from infrastructure.logging import get_logger

logger = get_logger("execution_service.http")

app = FastAPI(title="Execution Service", version="1.0.0")

# 全局实例
_engine = None
_risk_engine = None
_metrics = None


class HealthResponse(BaseModel):
    status: str
    engine: str
    database: str
    exchanges: Dict[str, str]
    timestamp: str


class ExecuteOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str = "MARKET"
    exchange: str = "BINANCE"
    market_type: str = "SPOT"
    leverage: int = 1
    reduce_only: bool = False


class ExecuteOrderResponse(BaseModel):
    success: bool
    order_id: str | None = None
    error: str | None = None
    status: str | None = None


@app.on_event("startup")
async def startup_event():
    """启动时初始化服务"""
    global _engine, _risk_engine, _metrics

    print("=" * 60)
    print("Starting Execution Service HTTP Server")
    print("=" * 60)

    # 初始化指标
    _metrics = get_execution_metrics()

    # 初始化数据库（如果启用）
    use_orm = os.getenv("EXECUTION_USE_ORM", "false").lower() == "true"
    db_manager = None

    if use_orm:
        try:
            db_manager = await init_db()
            await db_manager.create_tables()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️ Database init failed: {e}")
            use_orm = False

    # 初始化引擎
    _engine = await init_execution_engine(
        use_orm=use_orm,
        db_manager=db_manager,
        load_from_db=True,
    )

    # 注册适配器
    use_mock = os.getenv("EXECUTION_MOCK", "true").lower() == "true"
    exchange_name = os.getenv("EXECUTION_EXCHANGE", "binance").lower()
    testnet = os.getenv("EXECUTION_TESTNET", "true").lower() == "true"
    market_type_str = os.getenv("EXECUTION_MARKET_TYPE", "spot").lower()

    if use_mock:
        adapter = MockAdapter()
        print("✅ Using Mock Adapter")
    elif exchange_name == "okx":
        adapter = OKXAdapter(
            api_key=os.getenv("OKX_API_KEY"),
            api_secret=os.getenv("OKX_API_SECRET"),
            passphrase=os.getenv("OKX_PASSPHRASE"),
            testnet=testnet,
            market_type=MarketType(market_type_str.upper()),
        )
        print(f"✅ Using OKX Adapter (testnet={testnet}, market={market_type_str})")
    elif market_type_str in ["usdt_futures", "coin_futures"]:
        adapter = BinanceFuturesAdapter(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
            testnet=testnet,
        )
        print(f"✅ Using Binance Futures Adapter (testnet={testnet})")
    else:
        adapter = BinanceAdapter(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
            testnet=testnet,
        )
        print(f"✅ Using Binance Spot Adapter (testnet={testnet})")

    _engine.register_adapter(adapter)
    await _engine.connect_all()

    # 初始化风险引擎 (带所有检查器)
    _risk_engine = RiskEngine()
    _risk_engine.register_checker(PositionLimitChecker())
    _risk_engine.register_checker(LeverageLimitChecker())
    _risk_engine.register_checker(DailyLossLimitChecker())
    _risk_engine.register_checker(CooldownChecker())
    _risk_engine.register_checker(DrawdownLimitChecker())
    _risk_engine.register_checker(OrderSizeLimitChecker())
    _risk_engine.register_checker(StopLossTPCheckChecker())
    print(f"✅ Risk engine initialized with {len(_risk_engine.checkers)} checkers")

    print("=" * 60)
    print("Execution Service Ready - Health: http://localhost:8000/health")
    print("                   Metrics: http://localhost:8000/metrics")
    print("                   API Docs: http://localhost:8000/docs")
    print("=" * 60)


@app.get("/health")
async def health_check() -> HealthResponse:
    """健康检查端点"""
    from datetime import datetime

    engine_status = "ok" if _engine else "not_initialized"

    # 检查数据库
    db_status = "ok"
    if hasattr(_engine, "_use_orm") and _engine._use_orm:
        try:
            async with _engine._db_manager.session():
                pass
        except Exception as e:
            logger.error(f"DB health check failed: {e}")
            db_status = "error"
    else:
        db_status = "disabled"

    # 检查交易所连接
    exchange_statuses = {}
    if _engine:
        for exchange, adapter in _engine._adapters.items():
            exchange_statuses[exchange.value] = "connected" if adapter.is_connected() else "disconnected"

    return HealthResponse(
        status="ok" if engine_status == "ok" else "degraded",
        engine=engine_status,
        database=db_status,
        exchanges=exchange_statuses,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/metrics")
async def get_metrics() -> Response:
    """Prometheus 指标端点"""
    metrics = get_execution_metrics()
    return Response(
        content=metrics.export_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/api/v1/orders/execute")
async def execute_order(request: ExecuteOrderRequest) -> ExecuteOrderResponse:
    """执行订单端点"""
    global _engine, _risk_engine, _metrics

    if not _engine:
        return ExecuteOrderResponse(success=False, error="Engine not initialized")

    try:
        start_time = datetime.now()

        # 解析枚举
        side = OrderSide(request.side.lower())
        order_type = OrderType(request.order_type.lower())
        exchange = Exchange(request.exchange.upper())
        market_type = MarketType(request.market_type.upper())

        intent = OrderIntent(
            symbol=request.symbol,
            side=side,
            quantity=request.quantity,
            price=request.price,
            exchange=exchange,
            market_type=market_type,
            leverage=request.leverage,
            reduce_only=request.reduce_only,
        )

        # 风控检查
        if _risk_engine:
            risk_result = await _risk_engine.check(intent)
            if not risk_result.passed:
                _metrics.risk_check_failed(risk_result.reason)
                return ExecuteOrderResponse(
                    success=False,
                    error=f"Risk check failed: {risk_result.reason}",
                )
            _metrics.risk_check_passed()
            if risk_result.warnings:
                _metrics.risk_warning()

        _metrics.order_submitted(request.symbol)

        result = await _engine.execute_intent(intent)

        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        _metrics.record_order_latency(latency_ms)

        if result.success and result.order:
            if result.order.status.value in ["FILLED", "filled"]:
                _metrics.order_filled(request.symbol)
            return ExecuteOrderResponse(
                success=result.success,
                order_id=result.order.order_id,
                status=result.order.status.value if hasattr(result.order.status, "value") else str(result.order.status),
                error=result.error,
            )
        elif not result.success:
            _metrics.order_failed(request.symbol)
            return ExecuteOrderResponse(
                success=False,
                error=result.error,
            )
        else:
            _metrics.order_rejected(request.symbol)
            return ExecuteOrderResponse(success=False, error="Order rejected")

    except Exception as e:
        logger.error(f"Failed to execute order: {e}")
        _metrics.order_failed(request.symbol)
        return ExecuteOrderResponse(success=False, error=str(e))


@app.get("/api/v1/orders")
async def get_orders(symbol: str | None = None):
    """获取订单列表"""
    if not _engine:
        return {"orders": []}

    orders = _engine.get_order_history()
    if symbol:
        orders = [o for o in orders if o.symbol == symbol]

    return {"orders": [
        {
            "order_id": o.order_id,
            "symbol": o.symbol,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "filled_quantity": o.filled_quantity,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]}


@app.get("/api/v1/positions")
async def get_positions():
    """获取持仓列表"""
    global _metrics

    if not _engine:
        return {"positions": []}

    positions = _engine.get_all_positions()

    # 更新指标
    open_count = len(positions)
    total_pnl = sum(p.realized_pnl or 0 for p in positions)
    unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)
    _metrics.update_positions(open_count, unrealized_pnl, total_pnl)

    return {"positions": [
        {
            "symbol": p.symbol,
            "quantity": p.quantity,
            "unrealized_pnl": p.unrealized_pnl,
            "leverage": p.leverage,
        }
        for p in positions
    ]}


@app.post("/api/v1/positions/{symbol}/close")
async def close_position(symbol: str, exchange: str = "BINANCE", market_type: str = "USDT_FUTURES"):
    """平仓端点"""
    global _metrics

    if not _engine:
        return ExecuteOrderResponse(success=False, error="Engine not initialized")

    try:
        exchange_enum = Exchange(exchange.upper())
        market_type_enum = MarketType(market_type.upper())
        result = await _engine.close_position(symbol, exchange_enum, market_type_enum)

        if result.success:
            _metrics.order_submitted(symbol)
            _metrics.order_filled(symbol)

        return ExecuteOrderResponse(
            success=result.success,
            order_id=result.order.order_id if result.order else None,
            error=result.error,
        )
    except Exception as e:
        return ExecuteOrderResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(app, host=host, port=port)
