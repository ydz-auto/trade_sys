"""
Messaging Adapter - Bridge between runtime kernel and infrastructure messaging.

Kernel code should use this adapter instead of importing
infrastructure.messaging directly.
"""
from typing import Any, Optional


_messaging_providers: dict = {}


def register_messaging_provider(name: str, provider: Any):
    """Register an infrastructure messaging provider."""
    _messaging_providers[name] = provider


def get_messaging_provider(name: str) -> Optional[Any]:
    """Get a registered messaging provider by name."""
    return _messaging_providers.get(name)
