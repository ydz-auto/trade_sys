"""
Config 核心类型定义
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ConfigEntry:
    key: str
    value: Any
    category: str
    scope: str = "GLOBAL"
    version: int = 1
    is_active: bool = True
    description: Optional[str] = None
    created_at: int = 0
    updated_at: int = 0
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "scope": self.scope,
            "version": self.version,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }


@dataclass
class ConfigVersion:
    version: int
    config_key: str
    old_value: Any
    new_value: Any
    changed_by: str
    changed_at: int
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "config_key": self.config_key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at,
            "reason": self.reason,
        }


@dataclass
class ConfigSchema:
    key: str
    value_type: str
    default: Any
    description: str
    category: str
    scope: str = "GLOBAL"
    validation: Optional[Dict[str, Any]] = None
    options: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    required: bool = False

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        if self.required and value is None:
            return False, f"Config {self.key} is required"

        if self.value_type == "int":
            if not isinstance(value, int):
                return False, f"Config {self.key} must be an integer"
            if self.min_value is not None and value < self.min_value:
                return False, f"Config {self.key} must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Config {self.key} must be <= {self.max_value}"

        elif self.value_type == "float":
            if not isinstance(value, (int, float)):
                return False, f"Config {self.key} must be a number"
            if self.min_value is not None and value < self.min_value:
                return False, f"Config {self.key} must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Config {self.key} must be <= {self.max_value}"

        elif self.value_type == "string":
            if not isinstance(value, str):
                return False, f"Config {self.key} must be a string"
            if self.pattern:
                import re
                if not re.match(self.pattern, value):
                    return False, f"Config {self.key} does not match pattern {self.pattern}"

        elif self.value_type == "bool":
            if not isinstance(value, bool):
                return False, f"Config {self.key} must be a boolean"

        elif self.value_type == "list":
            if not isinstance(value, list):
                return False, f"Config {self.key} must be a list"

        elif self.value_type == "dict":
            if not isinstance(value, dict):
                return False, f"Config {self.key} must be a dictionary"

        if self.options and value not in self.options:
            return False, f"Config {self.key} must be one of {self.options}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value_type": self.value_type,
            "default": self.default,
            "description": self.description,
            "category": self.category,
            "scope": self.scope,
            "validation": self.validation,
            "options": self.options,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "pattern": self.pattern,
            "required": self.required,
        }