"""
Fee Model - 手续费模型

计算交易手续费:
1. 交易手续费
2. 资金费率
3. 隐形成本
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("replay.fee_model")


class FeeType(str, Enum):
    MAKER = "maker"
    TAKER = "taker"


class Exchange(str, Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    GENERIC = "generic"


@dataclass
class FeeResult:
    trading_fee: float
    fee_rate: float
    fee_type: FeeType
    
    notional: float
    
    funding_fee: float
    funding_rate: float
    
    total_fee: float
    total_fee_pct: float


@dataclass
class FeeModel:
    maker_fee: float = 0.0002
    taker_fee: float = 0.0005
    
    funding_interval_hours: float = 8.0
    
    exchange_fees: Dict[str, tuple] = None
    
    def __post_init__(self):
        if self.exchange_fees is None:
            self.exchange_fees = {
                Exchange.BINANCE: (0.0002, 0.0005),
                Exchange.BYBIT: (0.0001, 0.0006),
                Exchange.OKX: (0.0002, 0.0005),
                Exchange.GENERIC: (0.0002, 0.0005),
            }
    
    def calculate(
        self,
        size: float,
        price: float,
        side: str,
        is_maker: bool,
        position_size: float = 0.0,
        funding_rate: float = 0.0,
        holding_hours: float = 0.0,
        exchange: Exchange = Exchange.GENERIC,
    ) -> FeeResult:
        maker, taker = self.exchange_fees.get(exchange, (self.maker_fee, self.taker_fee))
        
        notional = size * price
        
        if is_maker:
            fee_rate = maker
            fee_type = FeeType.MAKER
        else:
            fee_rate = taker
            fee_type = FeeType.TAKER
        
        trading_fee = notional * fee_rate
        
        funding_fee = 0.0
        if position_size != 0 and funding_rate != 0 and holding_hours > 0:
            funding_periods = holding_hours / self.funding_interval_hours
            funding_fee = abs(position_size) * price * funding_rate * funding_periods
        
        total_fee = trading_fee + abs(funding_fee)
        total_fee_pct = total_fee / notional if notional > 0 else 0.0
        
        return FeeResult(
            trading_fee=trading_fee,
            fee_rate=fee_rate,
            fee_type=fee_type,
            notional=notional,
            funding_fee=funding_fee,
            funding_rate=funding_rate,
            total_fee=total_fee,
            total_fee_pct=total_fee_pct,
        )
    
    def estimate_total_cost(
        self,
        entry_size: float,
        entry_price: float,
        exit_size: float,
        exit_price: float,
        leverage: float,
        funding_rate: float = 0.0,
        holding_hours: float = 0.0,
    ) -> Dict[str, float]:
        entry_fee = self.calculate(
            entry_size, entry_price, "buy", False
        )
        
        exit_fee = self.calculate(
            exit_size, exit_price, "sell", False
        )
        
        position_value = entry_size * entry_price
        funding_cost = position_value * abs(funding_rate) * (holding_hours / self.funding_interval_hours)
        
        total_fees = entry_fee.total_fee + exit_fee.total_fee + funding_cost
        
        gross_pnl = (exit_price - entry_price) * entry_size
        net_pnl = gross_pnl - total_fees
        
        return {
            "entry_fee": entry_fee.total_fee,
            "exit_fee": exit_fee.total_fee,
            "funding_cost": funding_cost,
            "total_fees": total_fees,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "fee_drag_pct": total_fees / position_value if position_value > 0 else 0.0,
        }


def calculate_fees(
    size: float,
    price: float,
    side: str,
    is_maker: bool,
    position_size: float = 0.0,
    funding_rate: float = 0.0,
    holding_hours: float = 0.0,
    exchange: Exchange = Exchange.GENERIC,
    model: Optional[FeeModel] = None,
) -> FeeResult:
    model = model or FeeModel()
    return model.calculate(
        size, price, side, is_maker,
        position_size, funding_rate,
        holding_hours, exchange
    )
