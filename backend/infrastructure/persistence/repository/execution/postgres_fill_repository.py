import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from infrastructure.persistence.database.postgresql import PostgresManager, get_postgres_manager

logger = logging.getLogger("infrastructure.persistence.repository.execution.postgres_fill")


class PostgresFillRepository:
    def __init__(self, postgres: Optional[PostgresManager] = None):
        self.postgres = postgres or get_postgres_manager()
        self._table = "execution_fills"

    async def save(
        self,
        fill_id: str,
        order_id: str,
        symbol: str,
        exchange: str,
        market_type: str,
        side: str,
        quantity: float,
        price: float,
        fee: Optional[float] = None,
        fee_currency: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        metadata_json = json.dumps(metadata or {})

        sql = f"""
            INSERT INTO {self._table} (
                fill_id, order_id,
                symbol, exchange, market_type,
                side, quantity, price,
                fee, fee_currency,
                metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (fill_id) DO NOTHING
        """

        await self.postgres.execute(
            sql,
            fill_id,
            order_id,
            symbol,
            exchange,
            market_type,
            side,
            float(quantity),
            float(price),
            float(fee) if fee else None,
            fee_currency,
            metadata_json,
            datetime.utcnow(),
        )

        logger.debug(f"Saved fill to Postgres: {fill_id}")

    async def get_by_order(self, order_id: str) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT * FROM {self._table}
            WHERE order_id = $1
            ORDER BY created_at ASC
        """
        rows = await self.postgres.fetch(sql, order_id)
        return [self._row_to_fill(row) for row in rows]

    async def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT * FROM {self._table}
            ORDER BY created_at DESC LIMIT $1
        """
        rows = await self.postgres.fetch(sql, limit)
        return [self._row_to_fill(row) for row in rows]

    def _row_to_fill(self, row: Any) -> Dict[str, Any]:
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return {
            "fill_id": row.get("fill_id"),
            "order_id": row.get("order_id"),
            "symbol": row.get("symbol"),
            "exchange": row.get("exchange"),
            "market_type": row.get("market_type"),
            "side": row.get("side"),
            "quantity": row.get("quantity"),
            "price": row.get("price"),
            "fee": row.get("fee"),
            "fee_currency": row.get("fee_currency"),
            "metadata": metadata,
            "created_at": row.get("created_at"),
        }
