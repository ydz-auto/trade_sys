"""
Base Exchange Adapter

交易所适配器基类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    Position,
    Exchange,
)


class BaseExchangeAdapter(ABC):
    """交易所适配器基类"""

    def __init__(self, exchange: Exchange):
        self.exchange = exchange
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """连接交易所"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def create_order(self, request: OrderRequest) -> OrderResult:
        """创建订单"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """查询订单"""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """获取持仓"""
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """获取余额"""
        pass

    async def get_market_price(self, symbol: str) -> Optional[float]:
        """获取市场价格"""
        return None

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆（仅合约）"""
        return True

    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
