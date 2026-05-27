"""
Infrastructure Storage Module - 基础设施存储模块
"""

from .interfaces import StorageAdapter, AsyncStorageAdapter

__all__ = [
    "StorageAdapter",
    "AsyncStorageAdapter",
]
