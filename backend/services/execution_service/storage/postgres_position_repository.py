"""
PostgreSQL Position Repository

持仓 PostgreSQL 持久化层
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from domain.execution.models.position import Position
from infrastructure.database.postgresql import PostgresManager, get_postgres_manager

logger = logging.getLogger(__name__)


class PostgresPositionRepository:
    def __init__(self, postgres: Optional[PostgresManager] = None):
        self.postgres = postgres or get_postgres_manager()
        self._table = "execution_positions"

    async def save(self, position: Position) -> Position:
        """保存持仓（插入或更新）"""
        metadata_json = json.dumps(position.metadata or {})

        sql = f"""
            INSERT INTO {self._table} (
                symbol, exchange, market_type,
                quantity, avg_entry_price, current_price,
                unrealized_pnl, realized_pnl,
                leverage, margin, liquidation_price, position_id,
                metadata,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6,
                $7, $8,
                $9, $10, $11, $12,
                $13,
                $14, $15
            ) ON CONFLICT (symbol, exchange, market_type) DO UPDATE SET
                quantity = EXCLUDED.quantity,
                avg_entry_price = EXCLUDED.avg_entry_price,
                current_price = EXCLUDED.current_price,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                realized_pnl = EXCLUDED.realized_pnl,
                leverage = EXCLUDED.leverage,
                margin = EXCLUDED.margin,
                liquidation_price = EXCLUDED.liquidation_price,
                position_id = EXCLUDED.position_id,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
        """

        await self.postgres.execute(
            sql,
            position.symbol,
            position.exchange.value if hasattr(position.exchange, "value") else position.exchange,
            position.market_type.value if hasattr(position.market_type, "value") else position.market_type,
            float(position.quantity) if position.quantity else 0,
            float(position.avg_entry_price) if position.avg_entry_price else 0,
            float(position.current_price) if position.current_price else None,
            float(position.unrealized_pnl) if position.unrealized_pnl else None,
            float(position.realized_pnl) if position.realized_pnl else None,
            position.leverage,
            float(position.margin) if position.margin else None,
            float(position.liquidation_price) if position.liquidation_price else None,
            position.position_id,
            metadata_json,
            position.created_at or datetime.utcnow(),
            datetime.utcnow(),
        )

        logger.debug(f"Saved position to Postgres: {position.symbol}")
        return position

    async def get(self, symbol: str, exchange: str, market_type: str = "spot") -> Optional[Position]:
        """获取持仓"""
        sql = f"""
            SELECT * FROM {self._table}
            WHERE symbol = $1 AND exchange = $2 AND market_type = $3
        """
        row = await self.postgres.fetchrow(sql, symbol, exchange, market_type)
        return self._row_to_position(row) if row else None

    async def list_all(self, exchange: Optional[str] = None) -> List[Position]:
        """获取所有持仓"""
        if exchange:
            sql = f"""
                SELECT * FROM {self._table}
                WHERE exchange = $1
                ORDER BY updated_at DESC
            """
            rows = await self.postgres.fetch(sql, exchange)
        else:
            sql = f"""
                SELECT * FROM {self._table}
                ORDER BY updated_at DESC
            """
            rows = await self.postgres.fetch(sql)

        return [self._row_to_position(row) for row in rows]

    async def list_active(self, exchange: Optional[str] = None) -> List[Position]:
        """获取活跃持仓（quantity != 0）"""
        if exchange:
            sql = f"""
                SELECT * FROM {self._table}
                WHERE exchange = $1 AND quantity != 0
                ORDER BY updated_at DESC
            """
            rows = await self.postgres.fetch(sql, exchange)
        else:
            sql = f"""
                SELECT * FROM {self._table}
                WHERE quantity != 0
                ORDER BY updated_at DESC
            """
            rows = await self.postgres.fetch(sql)

        return [self._row_to_position(row) for row in rows]

    async def delete(self, symbol: str, exchange: str, market_type: str = "spot") -> bool:
        """删除持仓（实际是 quantity 置零）"""
        sql = f"""
            UPDATE {self._table}
            SET quantity = 0, updated_at = $1
            WHERE symbol = $2 AND exchange = $3 AND market_type = $4
        """
        result = await self.postgres.execute(sql, datetime.utcnow(), symbol, exchange, market_type)
        return "UPDATE" in result

    async def clear_all(self, exchange: Optional[str] = None) -> int:
        """清空所有持仓（quantity 置零）"""
        if exchange:
            sql = f"""
                UPDATE {self._table}
                SET quantity = 0, updated_at = $1
                WHERE exchange = $2
            """
            await self.postgres.execute(sql, datetime.utcnow(), exchange)
        else:
            sql = f"""
                UPDATE {self._table}
                SET quantity = 0, updated_at = $1
            """
            await self.postgres.execute(sql, datetime.utcnow())

        return 0

    def _row_to_position(self, row: Any) -> Position:
        """将数据库行转换为 Position 对象"""
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return Position(
            symbol=row.get("symbol"),
            exchange=row.get("exchange"),
            market_type=row.get("market_type"),
            quantity=row.get("quantity"),
            avg_entry_price=row.get("avg_entry_price"),
            current_price=row.get("current_price"),
            unrealized_pnl=row.get("unrealized_pnl"),
            realized_pnl=row.get("realized_pnl"),
            leverage=row.get("leverage"),
            margin=row.get("margin"),
            liquidation_price=row.get("liquidation_price"),
            position_id=row.get("position_id"),
            metadata=metadata,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
