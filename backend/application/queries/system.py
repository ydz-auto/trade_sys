"""System Queries - 系统状态查询"""
from typing import Dict, Any, List


async def get_system_status() -> Dict[str, Any]:
    from runtime.kernel.orchestrator import get_runtime_orchestrator
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
    from runtime.kernel.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_runtime_info()


async def get_system_stats() -> Dict[str, Any]:
    from runtime.kernel.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_stats()


async def get_system_health() -> Dict[str, Any]:
    from runtime.kernel.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_health()


async def get_system_alerts(limit: int = 20) -> list:
    from runtime.kernel.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    return orchestrator.get_alerts(limit=limit)


def get_trading_mode_enum() -> Any:
    from domain.trading_mode import TradingMode
    return TradingMode


def get_trading_mode_status() -> Dict[str, Any]:
    from domain.trading_mode import TradingMode
    from runtimes.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    status = manager.get_status()
    config = manager.config
    return {
        "mode": status.mode.value,
        "state": status.state.value,
        "previous_mode": status.previous_mode.value if status.previous_mode else None,
        "config": {
            "market_data_source": config.market_data_source,
            "order_execution": config.order_execution,
            "risk_engine": config.risk_engine,
            "portfolio_isolated": config.portfolio_isolated,
            "require_confirmation": config.require_confirmation,
            "color": config.color,
            "warning": config.warning,
        },
        "is_safe_to_trade": manager.is_safe_to_trade(),
    }


def get_all_modes() -> Dict[str, Any]:
    from runtimes.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    modes = manager.get_all_modes_info()
    return {"modes": modes, "current_mode": manager.mode.value}


def get_trading_mode_portfolio(mode: str = None) -> Dict[str, Any]:
    from domain.trading_mode import TradingMode
    from runtimes.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    target_mode = None
    if mode:
        target_mode = TradingMode(mode.lower())
    portfolio = manager.get_portfolio(target_mode)
    return {"mode": (target_mode or manager.mode).value, "portfolio": portfolio}


def get_trading_mode_stats() -> Dict[str, Any]:
    from runtimes.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    return manager.get_stats()


def get_trading_mode_safety() -> Dict[str, Any]:
    from runtimes.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    is_safe, message = manager.is_safe_to_trade()
    return {"is_safe": is_safe, "message": message, "mode": manager.mode.value, "state": manager.state.value}


async def preview_mode_transition(target_mode: str) -> Dict[str, Any]:
    from domain.trading_mode import TradingMode
    from runtimes.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    tm = TradingMode(target_mode.lower())
    can_transition, message = await manager.can_transition_to(tm)
    target_config = manager.get_all_modes_info()
    target_info = next((m for m in target_config if m["mode"] == tm.value), None)
    return {
        "can_transition": can_transition,
        "message": message,
        "current_mode": manager.mode.value,
        "target_mode": tm.value,
        "target_config": target_info["config"] if target_info else None,
        "requires_confirmation": target_info["config"]["require_confirmation"] if target_info else False,
    }


def get_health():
    import os
    from datetime import datetime
    from api.schemas import HealthResponse
    mock_mode = os.getenv("DATA_MOCK_MODE", "false").lower() == "true" or \
                os.getenv("DASHBOARD_MOCK", "false").lower() == "true"
    return HealthResponse(
        status="healthy",
        mock_mode=mock_mode,
        timestamp=datetime.now()
    )
