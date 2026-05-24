"""
Runtime Command Bus - Runtime 命令总线

核心职责:
1. 统一所有 runtime 控制命令
2. 前端 -> Command Bus -> Runtime Manager
3. 支持 START/STOP/SWITCH_MODE/PAUSE/RESUME 等
"""
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid

from domain.trading_mode import TradingMode
from runtime.kernel.event import get_runtime_bus, MessageType
from runtime.kernel.orchestrator import get_runtime_orchestrator
from infrastructure.logging import get_logger

logger = get_logger("runtime.command")


class CommandType(str, Enum):
    START_RUNTIME = "START_RUNTIME"
    STOP_RUNTIME = "STOP_RUNTIME"
    RESTART_RUNTIME = "RESTART_RUNTIME"
    PAUSE_RUNTIME = "PAUSE_RUNTIME"
    RESUME_RUNTIME = "RESUME_RUNTIME"

    START_ALL = "START_ALL"
    STOP_ALL = "STOP_ALL"

    SWITCH_MODE = "SWITCH_MODE"
    START_BACKTEST = "START_BACKTEST"
    START_PAPER = "START_PAPER"
    START_LIVE = "START_LIVE"

    START_REPLAY = "START_REPLAY"
    STOP_REPLAY = "STOP_REPLAY"
    PAUSE_REPLAY = "PAUSE_REPLAY"
    STEP_REPLAY = "STEP_REPLAY"
    SEEK_REPLAY = "SEEK_REPLAY"

    SET_CONFIG = "SET_CONFIG"
    UPDATE_PARAMS = "UPDATE_PARAMS"

    HEALTH_CHECK = "HEALTH_CHECK"
    GET_STATUS = "GET_STATUS"


@dataclass
class RuntimeCommand:
    command_id: str
    command_type: CommandType
    payload: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    timeout: float = 30.0
    requires_ack: bool = True


@dataclass
class CommandResult:
    command_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class RuntimeCommandBus:
    _instance: Optional['RuntimeCommandBus'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True

        self._bus = get_runtime_bus()
        self._orchestrator = get_runtime_orchestrator()

        self._handlers: Dict[CommandType, Callable] = {}
        self._pending_commands: Dict[str, asyncio.Future] = {}

        self._command_history: List[RuntimeCommand] = []
        self._result_history: List[CommandResult] = []
        self._max_history = 1000

        self._stats = {
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
        }

        self._setup_default_handlers()
        self._subscribe_to_bus()

        logger.info("RuntimeCommandBus initialized")

    def _setup_default_handlers(self) -> None:
        self._handlers[CommandType.START_ALL] = self._handle_start_all
        self._handlers[CommandType.STOP_ALL] = self._handle_stop_all
        self._handlers[CommandType.SWITCH_MODE] = self._handle_switch_mode
        self._handlers[CommandType.START_BACKTEST] = self._handle_start_backtest
        self._handlers[CommandType.START_PAPER] = self._handle_start_paper
        self._handlers[CommandType.START_LIVE] = self._handle_start_live
        self._handlers[CommandType.GET_STATUS] = self._handle_get_status
        self._handlers[CommandType.HEALTH_CHECK] = self._handle_health_check

    def _subscribe_to_bus(self) -> None:
        self._bus.subscribe("command.runtime", self._on_command)

    async def _on_command(self, message: Any) -> None:
        pass

    def register_handler(self, command_type: CommandType, handler: Callable) -> None:
        self._handlers[command_type] = handler
        logger.info(f"Registered command handler: {command_type.value}")

    async def execute(
        self,
        command_type: CommandType,
        payload: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        timeout: float = 30.0,
    ) -> CommandResult:
        command_id = f"cmd_{uuid.uuid4().hex[:8]}"

        command = RuntimeCommand(
            command_id=command_id,
            command_type=command_type,
            payload=payload or {},
            source=source,
            timeout=timeout,
        )

        self._command_history.append(command)
        if len(self._command_history) > self._max_history:
            self._command_history = self._command_history[-self._max_history:]

        self._stats["total_commands"] += 1

        logger.info(f"Executing command: {command_type.value} (id={command_id})")

        handler = self._handlers.get(command_type)

        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(command)
                else:
                    result = handler(command)

                self._stats["successful_commands"] += 1

                cmd_result = CommandResult(
                    command_id=command_id,
                    success=True,
                    result=result,
                )

            except Exception as e:
                self._stats["failed_commands"] += 1
                logger.error(f"Command failed: {command_type.value} - {e}")

                cmd_result = CommandResult(
                    command_id=command_id,
                    success=False,
                    error=str(e),
                )
        else:
            self._stats["failed_commands"] += 1
            cmd_result = CommandResult(
                command_id=command_id,
                success=False,
                error=f"No handler for command: {command_type.value}",
            )

        self._result_history.append(cmd_result)
        if len(self._result_history) > self._max_history:
            self._result_history = self._result_history[-self._max_history:]

        await self._bus.publish(
            f"command.result.{command_id}",
            {
                "success": cmd_result.success,
                "result": cmd_result.result,
                "error": cmd_result.error,
            },
            message_type=MessageType.COMMAND,
        )

        return cmd_result

    async def _handle_start_all(self, command: RuntimeCommand) -> Dict[str, Any]:
        result = await self._orchestrator.start()
        return result

    async def _handle_stop_all(self, command: RuntimeCommand) -> Dict[str, Any]:
        result = await self._orchestrator.stop()
        return result

    async def _handle_switch_mode(self, command: RuntimeCommand) -> Dict[str, Any]:
        target_mode = command.payload.get("target_mode")
        reason = command.payload.get("reason", "")

        if not target_mode:
            raise ValueError("target_mode is required")

        try:
            mode = TradingMode(target_mode.lower())
        except ValueError:
            raise ValueError(f"Invalid mode: {target_mode}")

        result = await self._orchestrator.switch_mode(mode, reason)
        return result

    async def _handle_start_backtest(self, command: RuntimeCommand) -> Dict[str, Any]:
        return await self._orchestrator.switch_mode(TradingMode.BACKTEST, "Start backtest")

    async def _handle_start_paper(self, command: RuntimeCommand) -> Dict[str, Any]:
        return await self._orchestrator.switch_mode(TradingMode.PAPER, "Start paper trading")

    async def _handle_start_live(self, command: RuntimeCommand) -> Dict[str, Any]:
        confirmed = command.payload.get("confirmed", False)
        if not confirmed:
            raise ValueError("Live mode requires confirmation")
        return await self._orchestrator.switch_mode(TradingMode.LIVE, "Start live trading")

    async def _handle_get_status(self, command: RuntimeCommand) -> Dict[str, Any]:
        return self._orchestrator.get_stats()

    async def _handle_health_check(self, command: RuntimeCommand) -> Dict[str, Any]:
        from runtime.kernel.orchestrator import get_runtime_inspector
        inspector = get_runtime_inspector()
        inspection = await inspector.inspect_all()
        return {
            "healthy": inspection.healthy_runtimes,
            "unhealthy": inspection.unhealthy_runtimes,
            "issues": inspection.issues,
        }

    async def start_all(self) -> CommandResult:
        return await self.execute(CommandType.START_ALL)

    async def stop_all(self) -> CommandResult:
        return await self.execute(CommandType.STOP_ALL)

    async def switch_mode(self, target_mode: str, reason: str = "") -> CommandResult:
        return await self.execute(
            CommandType.SWITCH_MODE,
            {"target_mode": target_mode, "reason": reason},
        )

    async def start_replay(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        speed: float = 1.0,
    ) -> CommandResult:
        return await self.execute(
            CommandType.START_REPLAY,
            {"start_time": start_time, "end_time": end_time, "speed": speed},
        )

    async def pause_replay(self) -> CommandResult:
        return await self.execute(CommandType.PAUSE_REPLAY)

    async def step_replay(self) -> CommandResult:
        return await self.execute(CommandType.STEP_REPLAY)

    def get_command_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [
            {
                "command_id": cmd.command_id,
                "command_type": cmd.command_type.value,
                "payload": cmd.payload,
                "source": cmd.source,
                "timestamp": cmd.timestamp.isoformat(),
            }
            for cmd in self._command_history[-limit:]
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "stats": self._stats.copy(),
            "handlers": [ct.value for ct in self._handlers.keys()],
        }


def get_command_bus() -> RuntimeCommandBus:
    return RuntimeCommandBus()


async def execute_command(command_type: CommandType, **kwargs) -> CommandResult:
    bus = get_command_bus()
    return await bus.execute(command_type, **kwargs)
