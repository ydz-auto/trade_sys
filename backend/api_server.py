"""
API Server - Main Entry Point

架构：
    API Server
      ↓
    RuntimeGovernor (lifecycle)
      ↓
    RuntimeBus (统一通信)
      ↓
    Orchestrator → Runtimes
"""
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_router

from infrastructure.logging import get_logger
from infrastructure.runtime import (
    get_runtime_governor,
    RuntimeMode,
)
from infrastructure.websocket import get_ws_gateway

logger = get_logger("api_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  Starting API Server...")
    logger.info("=" * 60)

    governor = get_runtime_governor()
    await governor.start()

    ws_gateway = await get_ws_gateway()
    import asyncio
    asyncio.ensure_future(ws_gateway.run_redis_subscriber())
    logger.info("WebSocket Gateway Redis subscriber started")

    logger.info("API Server started successfully")
    logger.info(f"  Mode: {governor.get_mode().value}")
    logger.info(f"  Queue size: {governor.priority_queue.size()}")

    yield

    logger.info("=" * 60)
    logger.info("  Shutting down API Server...")
    logger.info("=" * 60)

    await ws_gateway.shutdown()
    await governor.stop()

    logger.info("API Server stopped")


app = FastAPI(
    title="Quantitative Trading System API",
    description="AI-assisted quantitative trading system API with Runtime Governor",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:3004",
        "http://127.0.0.1:3004",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix="/api/v1")


from fastapi import APIRouter
from typing import Dict, Any

runtime_router = APIRouter(prefix="/runtime", tags=["runtime"])


@runtime_router.get("/stats")
async def get_runtime_stats() -> Dict[str, Any]:
    governor = get_runtime_governor()
    return governor.get_stats()


@runtime_router.get("/mode")
async def get_runtime_mode() -> Dict[str, Any]:
    governor = get_runtime_governor()
    return {
        "mode": governor.get_mode().value,
        "is_healthy": governor.is_healthy(),
    }


@runtime_router.post("/mode")
async def set_runtime_mode(mode: str, reason: str = "manual") -> Dict[str, str]:
    from runtime.command.command_bus import get_command_bus, CommandType

    bus = get_command_bus()
    result = await bus.execute(
        CommandType.SWITCH_MODE,
        {"target_mode": mode, "reason": reason},
        source="api.runtime",
    )

    if result.success:
        return {
            "mode": mode,
            "message": f"Mode change dispatched via RuntimeCommandBus",
        }
    return {
        "mode": get_runtime_governor().get_mode().value,
        "message": f"Mode change failed: {result.error}",
    }


@runtime_router.post("/recovery")
async def force_recovery() -> Dict[str, str]:
    governor = get_runtime_governor()
    await governor.force_recovery()
    return {
        "mode": governor.get_mode().value,
        "message": "Recovery completed",
    }


@runtime_router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    governor = get_runtime_governor()
    return governor.circuit_breakers.get_all_stats()


@runtime_router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str) -> Dict[str, str]:
    governor = get_runtime_governor()
    governor.circuit_breakers.reset(name)
    return {"message": f"Circuit breaker {name} reset"}


@runtime_router.get("/subscriptions")
async def get_subscriptions() -> Dict[str, Any]:
    governor = get_runtime_governor()
    return governor.subscriptions.get_stats()


@runtime_router.get("/queue")
async def get_queue_stats() -> Dict[str, Any]:
    governor = get_runtime_governor()
    return governor.priority_queue.get_stats()


app.include_router(runtime_router, prefix="/api/v1")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    print("=" * 80)
    print("  Quantitative Trading System API Server")
    print("  with Runtime Governor + RuntimeBus")
    print("=" * 80)
    print(f"  Starting on: http://0.0.0.0:{port}")
    print(f"  Swagger Docs: http://0.0.0.0:{port}/docs")
    print(f"  Runtime Stats: http://0.0.0.0:{port}/api/v1/runtime/stats")
    print("=" * 80)
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
