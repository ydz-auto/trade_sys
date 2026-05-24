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

    def __init__(self, exchange: Exchange):
        self.exchange = exchange
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def create_order(self, request: OrderRequest) -> OrderResult:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        pass

    async def get_market_price(self, symbol: str) -> Optional[float]:
        return None

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        return True

    def is_connected(self) -> bool:
        return self._connected
