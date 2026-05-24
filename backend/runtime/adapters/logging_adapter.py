"""
Logging Adapter - Bridge between runtime kernel and infrastructure logging.

Kernel code should use this adapter instead of importing infrastructure.logging directly.
This allows kernel to remain infrastructure-agnostic.
"""
import logging
from typing import Optional


_infrastructure_logger_factory = None


def set_logger_factory(factory):
    """Inject infrastructure logger factory.

    Call this at application startup:
        from infrastructure.logging import get_logger
        from runtime.adapters.logging_adapter import set_logger_factory
        set_logger_factory(get_logger)
    """
    global _infrastructure_logger_factory
    _infrastructure_logger_factory = factory


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    If infrastructure logging is available, use it.
    Otherwise fall back to stdlib logging.
    """
    if _infrastructure_logger_factory is not None:
        return _infrastructure_logger_factory(name)
    return logging.getLogger(name)
