"""
Trade Model - 成交数据模型
统一从 shared.contracts 导入
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

from domain.contracts import Exchange, Trade as ContractTrade


class Trade(ContractTrade):
    """成交数据 - 继承自 contracts"""
    pass


@dataclass
class TradeBatch:
    """成交批次（用于批量处理）"""
    exchange: str
    symbol: str
    trades: List[Trade]
    start_time: int
    end_time: int

    def get_volume(self) -> float:
        return sum(t.quantity for t in self.trades)

    def get_quote_volume(self) -> float:
        return sum(t.quote_quantity for t in self.trades)

    def get_trade_count(self) -> int:
        return len(self.trades)

    def get_buy_volume(self) -> float:
        return sum(t.quantity for t in self.trades if not t.is_buyer_maker)

    def get_sell_volume(self) -> float:
        return sum(t.quantity for t in self.trades if t.is_buyer_maker)

    def get_vwap(self) -> float:
        total_quote = self.get_quote_volume()
        total_qty = self.get_volume()
        if total_qty == 0:
            return 0.0
        return total_quote / total_qty

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "trades": [t.to_dict() for t in self.trades],
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
