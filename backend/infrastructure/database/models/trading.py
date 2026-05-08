"""
Trading Models - 交易账户和持仓模型
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.sqlalchemy_base import Base


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class TradingAccount(Base):
    __tablename__ = "trading_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_name: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    account_type: Mapped[str] = mapped_column(String(20), default="spot")
    status: Mapped[str] = mapped_column(String(20), default="active")
    balance: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    equity: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    margin_used: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    margin_available: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="trading_accounts")
    positions: Mapped[List["Position"]] = relationship(
        "Position", back_populates="account", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TradingAccount(id={self.id}, user_id={self.user_id}, exchange='{self.exchange}')>"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    current_price: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    leverage: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)
    margin_used: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    liquidation_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    account: Mapped["TradingAccount"] = relationship("TradingAccount", back_populates="positions")

    __table_args__ = (
        Index("ix_positions_account_symbol", "account_id", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<Position(id={self.id}, symbol='{self.symbol}', side='{self.side}')>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id", ondelete="CASCADE"))
    order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    filled_quantity: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    avg_fill_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    commission: Mapped[float] = mapped_column(Numeric(20, 8), default=0.0)
    commission_asset: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    account: Mapped["TradingAccount"] = relationship("TradingAccount", back_populates="orders")

    __table_args__ = (
        Index("ix_orders_account_symbol", "account_id", "symbol"),
        Index("ix_orders_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, order_id='{self.order_id}', symbol='{self.symbol}')>"
