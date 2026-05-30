import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from domain.execution.models.order import Order, OrderStatus
from infrastructure.persistence.database.postgresql import PostgresManager, get_postgres_manager

logger = logging.getLogger("infrastructure.persistence.repository.execution.postgres_order")


class PostgresOrderRepository:
    def __init__(self, postgres: Optional[PostgresManager] = None):
        self.postgres = postgres or get_postgres_manager()
        self._table = "execution_orders"

    async def save(self, order: Order) -> Order:
        metadata_json = json.dumps(order.metadata or {})

        sql = f"""
            INSERT INTO {self._table} (
                order_id, client_order_id, exchange_order_id,
                symbol, exchange, market_type,
                side, order_type, quantity, price, stop_price,
                status, filled_quantity, avg_fill_price,
                leverage, reduce_only, time_in_force,
                error_message, metadata,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13, $14,
                $15, $16, $17,
                $18, $19,
                $20, $21
            ) ON CONFLICT (order_id) DO UPDATE SET
                client_order_id = EXCLUDED.client_order_id,
                exchange_order_id = EXCLUDED.exchange_order_id,
                status = EXCLUDED.status,
                filled_quantity = EXCLUDED.filled_quantity,
                avg_fill_price = EXCLUDED.avg_fill_price,
                error_message = EXCLUDED.error_message,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
        """

        await self.postgres.execute(
            sql,
            order.order_id,
            order.client_order_id,
            order.exchange_order_id,
            order.symbol,
            order.exchange.value if hasattr(order.exchange, "value") else order.exchange,
            order.market_type.value if hasattr(order.market_type, "value") else order.market_type,
            order.side.value if hasattr(order.side, "value") else order.side,
            order.order_type.value if hasattr(order.order_type, "value") else order.order_type,
            float(order.quantity) if order.quantity else None,
            float(order.price) if order.price else None,
            float(order.stop_price) if order.stop_price else None,
            order.status.value if hasattr(order.status, "value") else order.status,
            float(order.filled_quantity) if order.filled_quantity else None,
            float(order.avg_fill_price) if order.avg_fill_price else None,
            order.leverage,
            order.reduce_only,
            order.time_in_force.value if hasattr(order.time_in_force, "value") else order.time_in_force,
            order.error_message,
            metadata_json,
            order.created_at,
            datetime.utcnow(),
        )

        logger.debug(f"Saved order to Postgres: {order.order_id}")
        return order

    async def get(self, order_id: str) -> Optional[Order]:
        sql = f"SELECT * FROM {self._table} WHERE order_id = $1"
        row = await self.postgres.fetchrow(sql, order_id)
        return self._row_to_order(row) if row else None

    async def get_by_exchange_order_id(self, exchange_order_id: str, exchange: str) -> Optional[Order]:
        sql = f"""
            SELECT * FROM {self._table}
            WHERE exchange_order_id = $1 AND exchange = $2
        """
        row = await self.postgres.fetchrow(sql, exchange_order_id, exchange)
        return self._row_to_order(row) if row else None

    async def list_by_symbol(self, symbol: str, exchange: Optional[str] = None, limit: int = 100) -> List[Order]:
        if exchange:
            sql = f"""
                SELECT * FROM {self._table}
                WHERE symbol = $1 AND exchange = $2
                ORDER BY created_at DESC LIMIT $3
            """
            rows = await self.postgres.fetch(sql, symbol, exchange, limit)
        else:
            sql = f"""
                SELECT * FROM {self._table}
                WHERE symbol = $1
                ORDER BY created_at DESC LIMIT $2
            """
            rows = await self.postgres.fetch(sql, symbol, limit)

        return [self._row_to_order(row) for row in rows]

    async def list_by_status(self, status: OrderStatus, limit: int = 100) -> List[Order]:
        status_val = status.value if hasattr(status, "value") else status
        sql = f"""
            SELECT * FROM {self._table}
            WHERE status = $1
            ORDER BY created_at DESC LIMIT $2
        """
        rows = await self.postgres.fetch(sql, status_val, limit)
        return [self._row_to_order(row) for row in rows]

    async def list_recent(self, limit: int = 100) -> List[Order]:
        sql = f"""
            SELECT * FROM {self._table}
            ORDER BY created_at DESC LIMIT $1
        """
        rows = await self.postgres.fetch(sql, limit)
        return [self._row_to_order(row) for row in rows]

    async def delete(self, order_id: str) -> bool:
        sql = f"UPDATE {self._table} SET status = 'archived' WHERE order_id = $1"
        result = await self.postgres.execute(sql, order_id)
        return "UPDATE" in result

    async def count_all(self) -> int:
        sql = f"SELECT COUNT(*) FROM {self._table}"
        return await self.postgres.fetchval(sql) or 0

    def _row_to_order(self, row: Any) -> Order:
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return Order(
            order_id=row.get("order_id"),
            client_order_id=row.get("client_order_id"),
            exchange_order_id=row.get("exchange_order_id"),
            symbol=row.get("symbol"),
            exchange=row.get("exchange"),
            market_type=row.get("market_type"),
            side=row.get("side"),
            order_type=row.get("order_type"),
            quantity=row.get("quantity"),
            price=row.get("price"),
            stop_price=row.get("stop_price"),
            status=row.get("status"),
            filled_quantity=row.get("filled_quantity"),
            avg_fill_price=row.get("avg_fill_price"),
            leverage=row.get("leverage"),
            reduce_only=row.get("reduce_only"),
            time_in_force=row.get("time_in_force"),
            error_message=row.get("error_message"),
            metadata=metadata,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
