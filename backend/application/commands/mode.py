"""Mode Commands - 模式切换写操作"""
from typing import Dict, Any


async def switch_mode(target_mode: str, reason: str = "") -> Dict[str, Any]:
    from domain.trading_mode import TradingMode
    from application.workflows.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    mode = TradingMode(target_mode)
    return await orchestrator.switch_mode(mode, reason=reason)


def get_trading_mode() -> str:
    from domain.trading_mode.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    return manager.mode.value


async def transition_mode(target_mode: str, reason: str = "", confirmed: bool = False, force: bool = False) -> Dict[str, Any]:
    from domain.trading_mode import TradingMode
    from domain.trading_mode.trading_mode_manager import get_trading_mode_manager

    cmd_result = await switch_mode(target_mode=target_mode, reason=reason)
    if cmd_result.get("success"):
        return {
            "success": True,
            "mode": target_mode.lower(),
            "message": "Mode transition dispatched via RuntimeCommandBus",
            "dispatch_via": "runtime_command_bus",
        }

    manager = get_trading_mode_manager()
    mode = TradingMode(target_mode)
    return await manager.transition_to(
        target_mode=mode,
        reason=reason,
        confirmed=confirmed,
        force=force,
    )


def set_exchange(exchange: str) -> Dict[str, Any]:
    from domain.trading_mode.trading_mode_manager import get_trading_mode_manager
    manager = get_trading_mode_manager()
    manager.set_exchange(exchange)
    return {"success": True, "exchange": exchange, "mode": manager.mode.value}
