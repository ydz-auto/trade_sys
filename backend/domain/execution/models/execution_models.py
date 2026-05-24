"""
Execution Service ORM Models

执行服务数据库模型（使用 SQLAlchemy ORM + UUID）
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import String, DateTime, Numeric, Boolean, Index, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from infrastructure.persistence.database.sqlalchemy_base import Base


class ExecutionOrder(Base):
    __tablename__ = "execution_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market_type: Mapped[str] = mapped_column(String(20), nullable=False, default="spot")

    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    filled_quantity: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    avg_fill_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)

    leverage: Mapped[int] = mapped_column(Numeric(4, 0), default=1)
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False)
    time_in_force: Mapped[str] = mapped_column(String(10), default="GTC")

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    fills: Mapped[List["ExecutionFill"]] = relationship(
        "ExecutionFill", back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_execution_orders_symbol_exchange", "symbol", "exchange"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "market_type": self.market_type,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": float(self.quantity) if self.quantity else 0,
            "price": float(self.price) if self.price else None,
            "stop_price": float(self.stop_price) if self.stop_price else None,
            "status": self.status,
            "filled_quantity": float(self.filled_quantity) if self.filled_quantity else 0,
            "avg_fill_price": float(self.avg_fill_price) if self.avg_fill_price else None,
            "leverage": self.leverage,
            "reduce_only": self.reduce_only,
            "time_in_force": self.time_in_force,
            "error_message": self.error_message,
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ExecutionFill(Base):
    __tablename__ = "execution_fills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fill_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("execution_orders.order_id"), nullable=False)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    market_type: Mapped[str] = mapped_column(String(20), nullable=False)

    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)

    fee: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    extra_data: Mapped[Dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped["ExecutionOrder"] = relationship("ExecutionOrder", back_populates="fills")

    __table_args__ = (
        Index("ix_execution_fills_order_id", "order_id"),
        Index("ix_execution_fills_symbol_exchange", "symbol", "exchange"),
    )


class ExecutionPosition(Base):
    __tablename__ = "execution_positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    position_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    market_type: Mapped[str] = mapped_column(String(20), nullable=False, default="spot")

    quantity: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    avg_entry_price: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    current_price: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    realized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0)

    leverage: Mapped[int] = mapped_column(Numeric(4, 0), default=1)
    margin: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    liquidation_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)

    extra_data: Mapped[Dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_execution_positions_symbol_exchange_market", "symbol", "exchange", "market_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "position_id": self.position_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "market_type": self.market_type,
            "quantity": float(self.quantity) if self.quantity else 0,
            "avg_entry_price": float(self.avg_entry_price) if self.avg_entry_price else 0,
            "current_price": float(self.current_price) if self.current_price else 0,
            "unrealized_pnl": float(self.unrealized_pnl) if self.unrealized_pnl else 0,
            "realized_pnl": float(self.realized_pnl) if self.realized_pnl else 0,
            "leverage": self.leverage,
            "margin": float(self.margin) if self.margin else 0,
            "liquidation_price": float(self.liquidation_price) if self.liquidation_price else None,
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    payload: Mapped[Dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_execution_events_order_id", "order_id"),
    )
