"""
Storage Module

存储模块

支持两种存储模式：
1. 内存存储（默认）- 用于开发测试
2. PostgreSQL ORM - 用于生产环境

ORM 模型：
- ExecutionOrder: 订单表
- ExecutionPosition: 持仓表
- ExecutionFill: 成交记录表
"""

from services.execution_service.storage.order_repository import OrderRepository
from services.execution_service.storage.position_repository import PositionRepository
from services.execution_service.storage.orm_order_repository import ORMOrderRepository
from services.execution_service.storage.orm_position_repository import ORMPositionRepository
from infrastructure.database.session import DatabaseSessionManager, get_db_manager, init_db, close_db

__all__ = [
    "OrderRepository",
    "PositionRepository",
    "ORMOrderRepository",
    "ORMPositionRepository",
    "DatabaseSessionManager",
    "get_db_manager",
    "init_db",
    "close_db",
]
