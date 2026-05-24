"""
Portfolio Projection - 持仓状态持久化层

职责：
1. 管理持仓的持久化状态
2. 计算和跟踪 PnL
3. 提供持仓历史和回溯能力
4. 与 Execution 分离，支持 Replay

架构：
    Execution Service
         ↓
    Fill Events
         ↓
    Portfolio Projection (独立状态机)
         ↓
    Redis (当前状态) + ClickHouse (历史)
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Position:
    """
    持仓信息

    这是 Portfolio 的核心状态
    """
    symbol: str
    side: PositionSide

    size: float

    entry_price: float
    current_price: float

    leverage: int = 1

    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    realized_pnl: float = 0.0

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def notional_value(self) -> float:
        return abs(self.size) * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        if self.side == PositionSide.FLAT:
            return 0.0

        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - self.current_price) * self.size

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def pnl_percentage(self) -> float:
        if self.entry_price == 0 or self.size == 0:
            return 0.0

        entry_value = self.entry_price * abs(self.size)
        if entry_value == 0:
            return 0.0

        return self.unrealized_pnl / entry_value * 100

    @property
    def is_profitable(self) -> bool:
        return self.total_pnl > 0

    @property
    def age_hours(self) -> float:
        return (datetime.utcnow() - self.opened_at).total_seconds() / 3600

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "size": self.size,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "leverage": self.leverage,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "pnl_percentage": self.pnl_percentage,
            "notional_value": self.notional_value,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "metadata": self.metadata,
        }


@dataclass
class PositionSnapshot:
    """持仓快照 - 用于历史记录"""
    timestamp: datetime
    positions: Dict[str, Position]

    total_unrealized_pnl: float
    total_realized_pnl: float
    total_pnl: float

    @classmethod
    def from_positions(cls, positions: Dict[str, Position]) -> "PositionSnapshot":
        return cls(
            timestamp=datetime.utcnow(),
            positions={k: v for k, v in positions.items()},
            total_unrealized_pnl=sum(p.unrealized_pnl for p in positions.values()),
            total_realized_pnl=sum(p.realized_pnl for p in positions.values()),
            total_pnl=sum(p.total_pnl for p in positions.values()),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "total_pnl": self.total_pnl,
        }


class PortfolioProjection:
    """
    Portfolio Projection

    持仓状态持久化层
    从 ExecutionService 拆分出来
    """

    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.snapshots: List[PositionSnapshot] = []

        self.redis: Optional[Any] = None

        self._stats = {
            "fills_processed": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "snapshots_taken": 0,
        }

    async def initialize(self) -> None:
        """初始化"""
        try:
            from infrastructure.persistence.cache.redis_client import init_redis
            self.redis = await init_redis()
            await self._load_positions()
            logger.info("PortfolioProjection initialized")
        except Exception as e:
            logger.warning(f"PortfolioProjection init failed: {e}")
            self.redis = None

    async def _load_positions(self) -> None:
        """从 Redis 加载持仓"""
        if not self.redis:
            return

        try:
            key = "portfolio:positions"
            data = await self.redis.get_json(key)
            if data:
                self.positions = {
                    symbol: self._deserialize_position(symbol, pdata)
                    for symbol, pdata in data.items()
                }
                logger.info(f"Loaded {len(self.positions)} positions from Redis")
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")

    async def _save_positions(self) -> None:
        """保存持仓到 Redis"""
        if not self.redis:
            return

        try:
            key = "portfolio:positions"
            data = {
                symbol: p.to_dict()
                for symbol, p in self.positions.items()
            }
            await self.redis.set_json(key, data)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def _deserialize_position(self, symbol: str, data: Dict[str, Any]) -> Position:
        """反序列化持仓"""
        return Position(
            symbol=symbol,
            side=PositionSide(data.get("side", "flat")),
            size=data.get("size", 0),
            entry_price=data.get("entry_price", 0),
            current_price=data.get("current_price", 0),
            leverage=data.get("leverage", 1),
            realized_pnl=data.get("realized_pnl", 0),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            metadata=data.get("metadata", {}),
        )

    async def process_fill(self, fill_event: Dict[str, Any]) -> Optional[Position]:
        """
        处理成交事件

        Args:
            fill_event: 成交事件

        Returns:
            更新后的持仓（如果有）
        """
        self._stats["fills_processed"] += 1

        symbol = fill_event.get("symbol", "")
        side = fill_event.get("side", "buy")
        quantity = fill_event.get("quantity", 0)
        price = fill_event.get("price", 0)
        realized_pnl = fill_event.get("realized_pnl", 0)

        if not symbol or not price:
            return None

        position = self.positions.get(symbol)

        if not position:
            if quantity == 0:
                return None

            position = Position(
                symbol=symbol,
                side=PositionSide.LONG if side == "buy" else PositionSide.SHORT,
                size=quantity,
                entry_price=price,
                current_price=price,
                realized_pnl=realized_pnl if realized_pnl else 0,
            )
            self.positions[symbol] = position
            self._stats["positions_opened"] += 1

            logger.info(f"Position opened: {symbol} {position.side.value} {quantity}")

        else:
            position.updated_at = datetime.utcnow()

            if side == "buy":
                if position.side == PositionSide.SHORT:
                    close_qty = min(abs(position.size), quantity)
                    position.size += close_qty
                    quantity -= close_qty

                    position.realized_pnl += close_qty * (position.entry_price - price)

                    if abs(position.size) < 0.0001:
                        position.side = PositionSide.FLAT
                        position.size = 0
                        self._stats["positions_closed"] += 1
                        logger.info(f"Position closed: {symbol}")
                    elif position.size > 0:
                        position.side = PositionSide.LONG

                if quantity > 0 and position.side == PositionSide.LONG:
                    total_cost = position.entry_price * position.size + price * quantity
                    position.size += quantity
                    position.entry_price = total_cost / position.size

            elif side == "sell":
                if position.side == PositionSide.LONG:
                    close_qty = min(abs(position.size), quantity)
                    position.size -= close_qty
                    quantity -= close_qty

                    position.realized_pnl += close_qty * (price - position.entry_price)

                    if abs(position.size) < 0.0001:
                        position.side = PositionSide.FLAT
                        position.size = 0
                        self._stats["positions_closed"] += 1
                        logger.info(f"Position closed: {symbol}")
                    elif position.size < 0:
                        position.side = PositionSide.SHORT

                if quantity > 0 and position.side == PositionSide.SHORT:
                    total_cost = abs(position.entry_price * position.size) + price * quantity
                    position.size -= quantity
                    position.entry_price = total_cost / abs(position.size)

            if realized_pnl:
                position.realized_pnl += realized_pnl

        position.current_price = price
        position.updated_at = datetime.utcnow()

        await self._save_positions()

        return position

    async def update_price(self, symbol: str, price: float) -> Optional[Position]:
        """
        更新持仓价格

        Args:
            symbol: 品种
            price: 当前价格

        Returns:
            更新后的持仓
        """
        position = self.positions.get(symbol)
        if not position:
            return None

        position.current_price = price
        position.updated_at = datetime.utcnow()

        await self._save_positions()

        return position

    async def close_position(
        self,
        symbol: str,
        reason: str = "manual"
    ) -> Optional[Position]:
        """
        平仓

        Args:
            symbol: 品种
            reason: 平仓原因

        Returns:
            平仓前的持仓
        """
        position = self.positions.get(symbol)
        if not position:
            return None

        closed_position = Position(
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price,
            current_price=position.current_price,
            realized_pnl=position.realized_pnl,
            opened_at=position.opened_at,
            metadata={**position.metadata, "close_reason": reason},
        )

        self.positions.pop(symbol)
        self._stats["positions_closed"] += 1

        await self._save_positions()

        logger.info(f"Position closed: {symbol} - PnL: {closed_position.total_pnl:.2f}")

        return closed_position

    async def take_snapshot(self) -> PositionSnapshot:
        """
        拍摄持仓快照

        用于历史记录和回溯
        """
        snapshot = PositionSnapshot.from_positions(self.positions)
        self.snapshots.append(snapshot)

        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]

        self._stats["snapshots_taken"] += 1

        if self.redis:
            try:
                import json
                await self.redis.lpush(
                    "portfolio:snapshots",
                    json.dumps(snapshot.to_dict())
                )
                await self.redis.client.ltrim("portfolio:snapshots", 0, 999)
            except Exception as e:
                logger.error(f"Failed to save snapshot: {e}")

        return snapshot

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        return self.positions.copy()

    def get_active_positions(self) -> List[Position]:
        """获取活跃持仓（非 Flat）"""
        return [p for p in self.positions.values() if p.side != PositionSide.FLAT]

    def get_pnl_summary(self) -> Dict[str, Any]:
        """获取 PnL 摘要"""
        active_positions = self.get_active_positions()

        return {
            "total_unrealized_pnl": sum(p.unrealized_pnl for p in active_positions),
            "total_realized_pnl": sum(p.realized_pnl for p in self.positions.values()),
            "total_pnl": sum(p.total_pnl for p in active_positions),
            "active_positions": len(active_positions),
            "long_count": sum(1 for p in active_positions if p.side == PositionSide.LONG),
            "short_count": sum(1 for p in active_positions if p.side == PositionSide.SHORT),
            "profitable_count": sum(1 for p in active_positions if p.is_profitable),
            "losing_count": sum(1 for p in active_positions if not p.is_profitable),
        }

    def get_position_history(self, symbol: str) -> List[PositionSnapshot]:
        """获取持仓历史"""
        return [
            s for s in self.snapshots
            if symbol in s.positions
        ]

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "current_positions": len(self.positions),
            "active_positions": len(self.get_active_positions()),
        }


_portfolio_projection: Optional[PortfolioProjection] = None


def get_portfolio_projection() -> PortfolioProjection:
    """获取 PortfolioProjection 单例"""
    global _portfolio_projection
    if _portfolio_projection is None:
        _portfolio_projection = PortfolioProjection()
    return _portfolio_projection
