from abc import ABC, abstractmethod
from typing import Any, Optional

from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class GuardViolation(Exception):
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
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.violation_count = 0
        self.processed_count = 0

    def before_process(self, event: ImmutableEvent) -> None:
        if not self.enabled:
            return

        self.processed_count += 1
        self._before_process_impl(event)

    def after_process(self, event: ImmutableEvent, result: Any) -> None:
        if not self.enabled:
            return

        self._after_process_impl(event, result)

    @abstractmethod
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        pass

    def _after_process_impl(self, event: ImmutableEvent, result: Any) -> None:
        pass

    def _violation(self, message: str, event: Optional[ImmutableEvent] = None) -> None:
        self.violation_count += 1
        logger.error(f"Guard violation: {self.name} - {message}")
        raise GuardViolation(self.name, message, event)

    def reset(self) -> None:
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
