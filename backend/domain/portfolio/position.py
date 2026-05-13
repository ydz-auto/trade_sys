"""
Position - 持仓实体

增强版持仓模型，支持多策略、多交易所
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


class PositionSide(str, Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class PositionStatus(str, Enum):
    """持仓状态"""
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"


@dataclass
class Position:
    """
    持仓实体
    
    支持多策略、多交易所的持仓管理
    """
    
    position_id: str
    symbol: str
    exchange: str
    
    side: PositionSide = PositionSide.FLAT
    status: PositionStatus = PositionStatus.OPEN
    
    quantity: float = 0.0
    available_quantity: float = 0.0
    
    entry_price: float = 0.0
    average_price: float = 0.0
    current_price: float = 0.0
    
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    leverage: int = 1
    margin: float = 0.0
    liquidation_price: float = 0.0
    
    strategy_id: str = ""
    account_id: str = ""
    
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.quantity > 0:
            self.side = PositionSide.LONG
        elif self.quantity < 0:
            self.side = PositionSide.SHORT
        else:
            self.side = PositionSide.FLAT
    
    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG
    
    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT
    
    @property
    def is_flat(self) -> bool:
        return self.side == PositionSide.FLAT or abs(self.quantity) < 1e-8
    
    @property
    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN
    
    @property
    def notional_value(self) -> float:
        """名义价值"""
        return abs(self.quantity) * self.current_price
    
    @property
    def margin_used(self) -> float:
        """已用保证金"""
        if self.leverage > 0:
            return self.notional_value / self.leverage
        return 0.0
    
    @property
    def pnl_percent(self) -> float:
        """盈亏百分比"""
        if self.entry_price > 0:
            return (self.current_price - self.entry_price) / self.entry_price * 100 * (1 if self.is_long else -1)
        return 0.0
    
    def update_price(self, current_price: float) -> None:
        """更新价格和未实现盈亏"""
        self.current_price = current_price
        
        if self.quantity != 0:
            if self.is_long:
                self.unrealized_pnl = (current_price - self.average_price) * self.quantity
            else:
                self.unrealized_pnl = (self.average_price - current_price) * abs(self.quantity)
        
        self.updated_at = datetime.utcnow()
    
    def add_quantity(self, quantity: float, price: float) -> None:
        """增加持仓"""
        if quantity == 0:
            return
        
        new_quantity = self.quantity + quantity
        
        if self.quantity == 0:
            self.entry_price = price
            self.average_price = price
        elif (self.quantity > 0 and quantity > 0) or (self.quantity < 0 and quantity < 0):
            total_cost = abs(self.quantity) * self.average_price + abs(quantity) * price
            total_qty = abs(new_quantity)
            self.average_price = total_cost / total_qty if total_qty > 0 else 0.0
        
        self.quantity = new_quantity
        self.available_quantity = new_quantity
        self.__post_init__()
        self.updated_at = datetime.utcnow()
    
    def reduce_quantity(self, quantity: float, price: float) -> float:
        """减少持仓，返回已实现盈亏"""
        if quantity == 0 or self.is_flat:
            return 0.0
        
        close_quantity = min(abs(self.quantity), abs(quantity))
        if self.is_long:
            realized = (price - self.average_price) * close_quantity
        else:
            realized = (self.average_price - price) * close_quantity
        
        self.realized_pnl += realized
        
        if self.quantity > 0:
            self.quantity -= close_quantity
        else:
            self.quantity += close_quantity
        
        self.available_quantity = self.quantity
        self.__post_init__()
        
        if self.is_flat:
            self.status = PositionStatus.CLOSED
            self.closed_at = datetime.utcnow()
        
        self.updated_at = datetime.utcnow()
        return realized
    
    def set_stop_loss(self, price: float) -> None:
        """设置止损"""
        self.stop_loss = price
        self.updated_at = datetime.utcnow()
    
    def set_take_profit(self, price: float) -> None:
        """设置止盈"""
        self.take_profit = price
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "status": self.status.value,
            "quantity": self.quantity,
            "available_quantity": self.available_quantity,
            "entry_price": self.entry_price,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "notional_value": self.notional_value,
            "pnl_percent": self.pnl_percent,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        return cls(
            position_id=data["position_id"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            side=PositionSide(data.get("side", "flat")),
            status=PositionStatus(data.get("status", "open")),
            quantity=data.get("quantity", 0.0),
            available_quantity=data.get("available_quantity", 0.0),
            entry_price=data.get("entry_price", 0.0),
            average_price=data.get("average_price", 0.0),
            current_price=data.get("current_price", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            leverage=data.get("leverage", 1),
            margin=data.get("margin", 0.0),
            liquidation_price=data.get("liquidation_price", 0.0),
            strategy_id=data.get("strategy_id", ""),
            account_id=data.get("account_id", ""),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            metadata=data.get("metadata", {}),
        )
