"""
API Server - Main Entry Point

架构：
    API Server
      ↓
    RuntimeOrchestrator (lifecycle + dependency-driven startup)
      ↓
    RuntimeBus (统一通信，纯 transport)
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
from runtime.kernel.orchestrator import get_runtime_orchestrator
from runtime.kernel.orchestrator.supervisor import get_runtime_supervisor, RuntimeSupervisor
from infrastructure.utilities.resilience.circuit_breaker import get_circuit_breaker_manager
from infrastructure.messaging.subscription_manager import SubscriptionManager, TopicRegistry
from infrastructure.utilities.priority_queue import PriorityEventQueue
from infrastructure.messaging.websocket import get_ws_gateway

logger = get_logger("api_server")


def _parse_csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _get_cors_origins() -> list[str]:
    explicit = os.getenv("CORS_ORIGINS") or os.getenv("API_CORS_ORIGINS")
    if explicit:
        return _parse_csv_env("CORS_ORIGINS", explicit) if os.getenv("CORS_ORIGINS") else _parse_csv_env("API_CORS_ORIGINS", explicit)

    hosts = _parse_csv_env("FRONTEND_HOSTS", "localhost,127.0.0.1")
    ports = _parse_csv_env("FRONTEND_PORTS", "3000,3001,3002,3003,3004")
    return [f"http://{host}:{port}" for host in hosts for port in ports]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  Starting API Server...")
    logger.info("=" * 60)

    orchestrator = get_runtime_orchestrator()
    result = await orchestrator.start()

    ws_gateway = await get_ws_gateway()
    import asyncio
    asyncio.ensure_future(ws_gateway.run_redis_subscriber())
    logger.info("WebSocket Gateway Redis subscriber started")

    status = orchestrator.get_status()
    logger.info("API Server started successfully")
    logger.info(f"  Mode: {status.mode.value}")
    logger.info(f"  Active runtimes: {status.active_runtimes}")

    yield

    logger.info("=" * 60)
    logger.info("  Shutting down API Server...")
    logger.info("=" * 60)

    await ws_gateway.shutdown()
    await orchestrator.stop()

    logger.info("API Server stopped")


app = FastAPI(
    title="Quantitative Trading System API",
    description="AI-assisted quantitative trading system API with Runtime Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
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
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_stats()


@runtime_router.get("/mode")
async def get_runtime_mode() -> Dict[str, Any]:
    orchestrator = get_runtime_orchestrator()
    status = orchestrator.get_status()
    health = orchestrator.get_health()
    return {
        "mode": status.mode.value,
        "is_healthy": health.get("healthy_count", 0) > 0,
    }


@runtime_router.post("/mode")
async def set_runtime_mode(mode: str, reason: str = "manual") -> Dict[str, str]:
    from application.commands.runtime_command_bus import get_command_bus, CommandType

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
    orchestrator = get_runtime_orchestrator()
    status = orchestrator.get_status()
    return {
        "mode": status.mode.value,
        "message": f"Mode change failed: {result.error}",
    }


@runtime_router.post("/recovery")
async def force_recovery() -> Dict[str, str]:
    supervisor = get_runtime_supervisor()
    await supervisor.force_recovery()
    orchestrator = get_runtime_orchestrator()
    status = orchestrator.get_status()
    return {
        "mode": status.mode.value,
        "message": "Recovery completed",
    }


@runtime_router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    cb_manager = get_circuit_breaker_manager()
    return cb_manager.get_all_stats()


@runtime_router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str) -> Dict[str, str]:
    cb_manager = get_circuit_breaker_manager()
    cb_manager.reset(name)
    return {"message": f"Circuit breaker {name} reset"}


@runtime_router.get("/subscriptions")
async def get_subscriptions() -> Dict[str, Any]:
    from infrastructure.messaging.subscription_manager import SubscriptionManager
    manager = SubscriptionManager()
    return manager.get_stats()


@runtime_router.get("/queue")
async def get_queue_stats() -> Dict[str, Any]:
    from infrastructure.utilities.priority_queue import PriorityEventQueue
    queue = PriorityEventQueue()
    return queue.get_stats()


app.include_router(runtime_router, prefix="/api/v1")


if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", os.getenv("PORT", "8001")))
    print("=" * 80)
    print("  Quantitative Trading System API Server")
    print("  with Runtime Orchestrator + RuntimeBus")
    print("=" * 80)
    print(f"  Starting on: http://{host}:{port}")
    print(f"  Swagger Docs: http://{host}:{port}/docs")
    print(f"  Runtime Stats: http://{host}:{port}/api/v1/runtime/stats")
    print("=" * 80)
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=True,
    )
