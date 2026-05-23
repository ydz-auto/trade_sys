"""Mode Commands - 模式切换写操作"""
from typing import Dict, Any
from domain.trading_mode import TradingMode

async def switch_mode(target_mode: str, reason: str = "") -> Dict[str, Any]:
    from runtime.orchestrator import get_runtime_orchestrator
    orchestrator = get_runtime_orchestrator()
    mode = TradingMode(target_mode)
    return await orchestrator.switch_mode(mode, reason=reason)

def get_trading_mode() -> str:
    from domain.trading_mode import get_trading_mode_manager
    manager = get_trading_mode_manager()
    return manager.mode.value
