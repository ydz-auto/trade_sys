"""
Position Model

持仓模型
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import math

from domain.execution.models.enums import Exchange, MarketType


# Binance USDT 合约维持保证金率（按持仓档位）
# 持仓档位越小，维持保证金率越低
MAINTENANCE_MARGIN_RATE = 0.004  # 默认 0.4%


@dataclass
class Position:
    """持仓"""
    symbol: str
    exchange: Exchange
    quantity: float
    average_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)

    market_type: MarketType = MarketType.SPOT
    leverage: int = 1
    margin: float = 0.0
    liquidation_price: float = 0.0
    entry_time: Optional[datetime] = None
    
    # 新增：爆仓相关计算
    maintenance_margin_rate: float = MAINTENANCE_MARGIN_RATE  # 维持保证金率

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "updated_at": self.updated_at.isoformat(),
            "market_type": self.market_type.value,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            # 新增：爆仓相关
            "liquidation_distance_pct": self.liquidation_distance_pct,
            "margin_ratio": self.margin_ratio,
            "risk_level": self.risk_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        return cls(
            symbol=data["symbol"],
            exchange=Exchange(data["exchange"]),
            quantity=data["quantity"],
            average_price=data["average_price"],
            current_price=data.get("current_price", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            market_type=MarketType(data.get("market_type", "spot")),
            leverage=data.get("leverage", 1),
            margin=data.get("margin", 0.0),
            liquidation_price=data.get("liquidation_price", 0.0),
            entry_time=datetime.fromisoformat(data["entry_time"]) if data.get("entry_time") else None,
            maintenance_margin_rate=data.get("maintenance_margin_rate", MAINTENANCE_MARGIN_RATE),
        )

    def update_price(self, current_price: float) -> None:
        """更新当前价格和未实现盈亏"""
        self.current_price = current_price
        if self.quantity != 0:
            self.unrealized_pnl = (current_price - self.average_price) * self.quantity
        self.updated_at = datetime.now()

    @property
    def position_value(self) -> float:
        """持仓价值（绝对值）"""
        return abs(self.quantity * self.average_price) if self.average_price else 0.0

    @property
    def liquidation_distance_pct(self) -> float:
        """爆仓距离百分比"""
        if self.liquidation_price <= 0 or self.current_price <= 0:
            return 0.0
        
        if self.is_long():
            # 多头：爆仓价在下方的距离
            distance = self.liquidation_price - self.current_price
        else:
            # 空头：爆仓价在上方的距离
            distance = self.current_price - self.liquidation_price
        
        return (distance / self.current_price) * 100 if distance > 0 else 0.0

    @property
    def margin_ratio(self) -> float:
        """保证金率 = 保证金 / 持仓价值"""
        if self.position_value <= 0:
            return 0.0
        return (self.margin / self.position_value) * 100

    @property
    def risk_level(self) -> str:
        """风险等级"""
        dist_pct = self.liquidation_distance_pct
        if dist_pct <= 0:
            return "CRITICAL"  # 未知/无爆仓价
        elif dist_pct < 5:
            return "DANGER"  # 危险
        elif dist_pct < 10:
            return "WARNING"  # 警告
        elif dist_pct < 20:
            return "CAUTION"  # 注意
        else:
            return "SAFE"  # 安全

    def calculate_liquidation_price(self, entry_price: float = None, leverage: int = None) -> float:
        """计算预估爆仓价格（USDT合约）
        
        多头爆仓价 = 入场价 * (1 - 1/杠杆 - 维持保证金率)
        空头爆仓价 = 入场价 * (1 + 1/杠杆 + 维持保证金率)
        """
        ep = entry_price if entry_price is not None else self.average_price
        lev = leverage if leverage is not None else self.leverage
        
        if ep <= 0 or lev <= 1:
            return 0.0
        
        mmr = self.maintenance_margin_rate
        if self.is_long():
            return ep * (1 - 1/lev - mmr)
        else:
            return ep * (1 + 1/lev + mmr)

    def is_long(self) -> bool:
        """是否多头"""
        return self.quantity > 0

    def is_short(self) -> bool:
        """是否空头"""
        return self.quantity < 0

    def is_flat(self) -> bool:
        """是否无持仓"""
        return abs(self.quantity) < 1e-8
