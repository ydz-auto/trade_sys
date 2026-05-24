from abc import ABC, abstractmethod
from typing import List

from domain.execution.models import Position, Exchange, MarketType


class PositionReader(ABC):

    @abstractmethod
    async def get_all(self) -> List[Position]:
        ...

    @abstractmethod
    async def get_total_position_value(self) -> float:
        ...

    @abstractmethod
    async def get_position_count(self) -> int:
        ...

    @abstractmethod
    async def has_position(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> bool:
        ...
