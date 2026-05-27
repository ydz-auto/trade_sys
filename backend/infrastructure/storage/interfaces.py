"""
Storage Adapter - 存储适配器接口

定义底层存储的抽象接口。
Strategy/FeatureEngine 不直接依赖具体存储实现。
"""

from typing import Protocol, Any, List, Dict, Optional
from abc import ABC, abstractmethod
import asyncio


class StorageAdapter(Protocol):
    """存储适配器协议"""
    
    async def fetch(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果"""
        ...
    
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """执行DDL/DML语句"""
        ...
    
    async def insert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """批量插入数据"""
        ...


class AsyncStorageAdapter(ABC):
    """异步存储适配器基类"""
    
    @abstractmethod
    async def fetch(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果"""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """执行DDL/DML语句"""
        pass
    
    @abstractmethod
    async def insert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """批量插入数据"""
        pass


__all__ = [
    "StorageAdapter",
    "AsyncStorageAdapter",
]
