"""
Storage Adapter - Bridge between runtime kernel and infrastructure storage.

Kernel code should use this adapter instead of importing
infrastructure.storage / infrastructure.persistence directly.
"""
from typing import Any, Optional


_storage_providers: dict = {}


def register_storage_provider(name: str, provider: Any):
    """Register an infrastructure storage provider."""
    _storage_providers[name] = provider


def get_storage_provider(name: str) -> Optional[Any]:
    """Get a registered storage provider by name."""
    return _storage_providers.get(name)
