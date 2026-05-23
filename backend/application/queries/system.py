"""System Queries - 系统状态查询"""
from typing import Dict, Any, List

async def get_system_status() -> Dict[str, Any]:
    from runtime.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    status = orchestrator.get_status()
    return {
        "is_running": status.is_running,
        "mode": status.mode.value,
        "active_runtimes": status.active_runtimes,
        "failed_runtimes": status.failed_runtimes,
        "uptime_seconds": status.uptime_seconds,
    }

async def get_runtime_info() -> List[Dict[str, Any]]:
    from runtime.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_runtime_info()

async def get_system_stats() -> Dict[str, Any]:
    from runtime.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_stats()

async def get_system_health() -> Dict[str, Any]:
    from runtime.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_health()

async def get_system_alerts(limit: int = 20) -> list:
    from runtime.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_alerts(limit=limit)
