"""
Runtime Commands - Runtime 命令定义

所有可用的 runtime 控制命令
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RuntimeCommandType(str, Enum):
    START_RUNTIME = "START_RUNTIME"
    STOP_RUNTIME = "STOP_RUNTIME"
    RESTART_RUNTIME = "RESTART_RUNTIME"
    PAUSE_RUNTIME = "PAUSE_RUNTIME"
    RESUME_RUNTIME = "RESUME_RUNTIME"
    
    START_ALL = "START_ALL"
    STOP_ALL = "STOP_ALL"
    RESTART_ALL = "RESTART_ALL"
    
    SWITCH_MODE = "SWITCH_MODE"
    START_BACKTEST = "START_BACKTEST"
    START_PAPER = "START_PAPER"
    START_LIVE = "START_LIVE"
    
    START_REPLAY = "START_REPLAY"
    STOP_REPLAY = "STOP_REPLAY"
    PAUSE_REPLAY = "PAUSE_REPLAY"
    RESUME_REPLAY = "RESUME_REPLAY"
    STEP_REPLAY = "STEP_REPLAY"
    SEEK_REPLAY = "SEEK_REPLAY"
    SET_REPLAY_SPEED = "SET_REPLAY_SPEED"
    
    SET_CONFIG = "SET_CONFIG"
    UPDATE_PARAMS = "UPDATE_PARAMS"
    RELOAD_CONFIG = "RELOAD_CONFIG"
    
    HEALTH_CHECK = "HEALTH_CHECK"
    GET_STATUS = "GET_STATUS"
    GET_METRICS = "GET_METRICS"
    
    ENABLE_STRATEGY = "ENABLE_STRATEGY"
    DISABLE_STRATEGY = "DISABLE_STRATEGY"
    UPDATE_STRATEGY_PARAMS = "UPDATE_STRATEGY_PARAMS"
    
    SET_RISK_LIMIT = "SET_RISK_LIMIT"
    ENABLE_CIRCUIT_BREAKER = "ENABLE_CIRCUIT_BREAKER"
    DISABLE_CIRCUIT_BREAKER = "DISABLE_CIRCUIT_BREAKER"
    
    CLEAR_CACHE = "CLEAR_CACHE"
    RESET_STATE = "RESET_STATE"


@dataclass
class RuntimeCommand:
    command_type: RuntimeCommandType
    payload: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    command_id: Optional[str] = None
    requires_ack: bool = True
    timeout: float = 30.0


COMMAND_SCHEMAS = {
    RuntimeCommandType.START_RUNTIME: {
        "runtime_id": {"type": "string", "required": True},
    },
    RuntimeCommandType.STOP_RUNTIME: {
        "runtime_id": {"type": "string", "required": True},
        "graceful": {"type": "boolean", "required": False, "default": True},
    },
    RuntimeCommandType.SWITCH_MODE: {
        "target_mode": {"type": "string", "required": True, "enum": ["backtest", "paper", "live"]},
        "reason": {"type": "string", "required": False},
        "confirmed": {"type": "boolean", "required": False, "default": False},
    },
    RuntimeCommandType.START_REPLAY: {
        "start_time": {"type": "string", "required": False},
        "end_time": {"type": "string", "required": False},
        "speed": {"type": "number", "required": False, "default": 1.0},
        "symbols": {"type": "array", "required": False},
    },
    RuntimeCommandType.SEEK_REPLAY: {
        "timestamp": {"type": "string", "required": True},
    },
    RuntimeCommandType.SET_REPLAY_SPEED: {
        "speed": {"type": "number", "required": True, "min": 0.1, "max": 100.0},
    },
    RuntimeCommandType.SET_CONFIG: {
        "key": {"type": "string", "required": True},
        "value": {"type": "any", "required": True},
    },
    RuntimeCommandType.SET_RISK_LIMIT: {
        "limit_type": {"type": "string", "required": True},
        "value": {"type": "number", "required": True},
    },
    RuntimeCommandType.ENABLE_STRATEGY: {
        "strategy_id": {"type": "string", "required": True},
    },
    RuntimeCommandType.UPDATE_STRATEGY_PARAMS: {
        "strategy_id": {"type": "string", "required": True},
        "params": {"type": "object", "required": True},
    },
}


def validate_command(command: RuntimeCommand) -> tuple[bool, Optional[str]]:
    schema = COMMAND_SCHEMAS.get(command.command_type)
    if not schema:
        return True, None
    
    for field_name, field_spec in schema.items():
        if field_spec.get("required", False):
            if field_name not in command.payload:
                return False, f"Missing required field: {field_name}"
        
        if field_name in command.payload:
            value = command.payload[field_name]
            expected_type = field_spec.get("type")
            
            if expected_type == "string" and not isinstance(value, str):
                return False, f"Field {field_name} must be string"
            elif expected_type == "number" and not isinstance(value, (int, float)):
                return False, f"Field {field_name} must be number"
            elif expected_type == "boolean" and not isinstance(value, bool):
                return False, f"Field {field_name} must be boolean"
            elif expected_type == "array" and not isinstance(value, list):
                return False, f"Field {field_name} must be array"
            elif expected_type == "object" and not isinstance(value, dict):
                return False, f"Field {field_name} must be object"
            
            if "enum" in field_spec and value not in field_spec["enum"]:
                return False, f"Field {field_name} must be one of: {field_spec['enum']}"
            
            if "min" in field_spec and value < field_spec["min"]:
                return False, f"Field {field_name} must be >= {field_spec['min']}"
            
            if "max" in field_spec and value > field_spec["max"]:
                return False, f"Field {field_name} must be <= {field_spec['max']}"
    
    return True, None


def create_command(
    command_type: RuntimeCommandType,
    **kwargs,
) -> RuntimeCommand:
    import uuid
    return RuntimeCommand(
        command_type=command_type,
        payload=kwargs,
        command_id=f"cmd_{uuid.uuid4().hex[:8]}",
    )
