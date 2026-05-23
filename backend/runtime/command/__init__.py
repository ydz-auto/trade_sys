"""
Runtime Command Module - Runtime 命令模块

核心组件:
- RuntimeCommandBus: 命令总线
- RuntimeCommandType: 命令类型定义
"""
from application.commands.runtime_command_bus import (
    CommandType,
    RuntimeCommand,
    CommandResult,
    RuntimeCommandBus,
    get_command_bus,
    execute_command,
)

from domain.runtime_commands import (
    RuntimeCommandType,
    RuntimeCommand as RuntimeCommandDef,
    COMMAND_SCHEMAS,
    validate_command,
    create_command,
)

__all__ = [
    "CommandType",
    "RuntimeCommand",
    "CommandResult",
    "RuntimeCommandBus",
    "get_command_bus",
    "execute_command",
    
    "RuntimeCommandType",
    "RuntimeCommandDef",
    "COMMAND_SCHEMAS",
    "validate_command",
    "create_command",
]
