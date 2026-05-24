"""
Execution Events

执行领域事件
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from domain.execution.models.order import Order
from domain.execution.models.position import Position
from domain.execution.models.enums import OrderStatus


@dataclass
class OrderCreated:
    """订单创建事件"""
    order: Order
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "order_created"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "order": self.order.to_dict(),
        }


@dataclass
class OrderUpdated:
    """订单更新事件"""
    order: Order
    old_status: OrderStatus
    new_status: OrderStatus
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "order_updated"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "order": self.order.to_dict(),
            "old_status": self.old_status.value,
            "new_status": self.new_status.value,
        }


@dataclass
class OrderFilled:
    """订单成交事件"""
    order: Order
    fill_quantity: float
    fill_price: float
    fill_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "order_filled"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "order": self.order.to_dict(),
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "fill_id": self.fill_id,
        }


@dataclass
class PositionUpdated:
    """持仓更新事件"""
    position: Position
    old_quantity: float
    new_quantity: float
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "position_updated"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "position": self.position.to_dict(),
            "old_quantity": self.old_quantity,
            "new_quantity": self.new_quantity,
        }
