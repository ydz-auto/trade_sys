from typing import Any, Dict, Optional
from domain.logging import get_logger
from infrastructure.messaging.schema.base_event import BaseEvent

logger = get_logger(__name__)


async def publish_event(event: BaseEvent, source: str = "api") -> bool:
    from runtime.bus.runtime_bus import get_runtime_bus
    bus = get_runtime_bus()
    if bus:
        await bus.publish_event(event)
        return True
    return False


async def publish_command(command_type: str, data: Dict[str, Any], target: Optional[str] = None) -> bool:
    from runtime.bus.runtime_bus import get_runtime_bus
    bus = get_runtime_bus()
    if bus:
        await bus.publish_command(
            command=command_type,
            target=target or "runtime",
            params=data,
            source="api",
        )
        return True
    return False


async def request_refresh(symbol: str, timeframe: str = "1m", source: str = "api") -> bool:
    from runtime.bus.runtime_bus import get_runtime_bus, MessageType
    bus = get_runtime_bus()
    if bus:
        await bus.publish(
            "refresh_request",
            {"symbol": symbol, "timeframe": timeframe},
            message_type=MessageType.COMMAND,
            source=source,
        )
        return True
    return False


async def get_bus_stats() -> Dict[str, Any]:
    from runtime.bus.runtime_bus import get_runtime_bus
    bus = get_runtime_bus()
    if bus:
        return bus.get_stats()
    return {}


async def safe_execute_order(request) -> Any:
    from runtime.execution.router import safe_execute
    return await safe_execute(request)


def get_execution_blocked_error() -> Any:
    from runtime.execution.router import ExecutionBlockedError
    return ExecutionBlockedError
