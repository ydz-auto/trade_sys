"""
Base Guard - 守卫基类

所有守卫必须继承自这里
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from domain.event.protocol import ImmutableEvent
from domain.logging import get_logger

logger = get_logger("runtime.guards.base")


class GuardViolation(Exception):
    """守卫违规异常"""
    
    def __init__(
        self,
        guard_name: str,
        message: str,
        event: Optional[ImmutableEvent] = None,
    ):
        self.guard_name = guard_name
        self.message = message
        self.event = event
        
        event_str = f", event={event}" if event else ""
        super().__init__(f"[{guard_name}] {message}{event_str}")


class BaseGuard(ABC):
    """守卫基类"""
    
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.violation_count = 0
        self.processed_count = 0
    
    def before_process(self, event: ImmutableEvent) -> None:
        """
        处理前检查
        
        违反时抛出 GuardViolation
        
        Args:
            event: 要处理的事件
        """
        if not self.enabled:
            return
        
        self.processed_count += 1
        self._before_process_impl(event)
    
    def after_process(self, event: ImmutableEvent, result: Any) -> None:
        """
        处理后检查
        
        违反时抛出 GuardViolation
        
        Args:
            event: 已处理的事件
            result: 处理结果
        """
        if not self.enabled:
            return
        
        self._after_process_impl(event, result)
    
    @abstractmethod
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """
        处理前检查的具体实现（子类必须重写）
        
        Args:
            event: 要处理的事件
        """
        pass
    
    def _after_process_impl(self, event: ImmutableEvent, result: Any) -> None:
        """
        处理后检查的具体实现（子类可选重写）
        
        Args:
            event: 已处理的事件
            result: 处理结果
        """
        pass
    
    def _violation(self, message: str, event: Optional[ImmutableEvent] = None) -> None:
        """
        报告违规
        
        Args:
            message: 违规信息
            event: 相关事件
        
        Raises:
            GuardViolation
        """
        self.violation_count += 1
        logger.error(f"Guard violation: {self.name} - {message}")
        raise GuardViolation(self.name, message, event)
    
    def reset(self) -> None:
        """重置计数"""
        self.violation_count = 0
        self.processed_count = 0
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"enabled={self.enabled}, "
            f"violations={self.violation_count}, "
            f"processed={self.processed_count})"
        )
