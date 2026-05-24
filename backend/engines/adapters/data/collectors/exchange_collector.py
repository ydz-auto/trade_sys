from typing import Dict, List, Optional, Any
from datetime import datetime

from infrastructure.logging import get_logger
from .base_collector import BaseCollector, CollectorResult, SourceConfig
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreakerConfig
from infrastructure.utilities.resilience.retry import RetryConfig
from engines.adapters.exchange.multi_exchange import (
    ExchangePrice,
    MultiExchangePrices,
    ExchangeAdapter,
    ExchangeWebSocketAdapter,
)

logger = get_logger("collectors.exchange")


class ExchangeCollector(BaseCollector):
    def __init__(self, symbols: List[str], exchanges: List[str]):
        self.symbols = symbols
        self.exchanges = exchanges
        self._adapter = ExchangeAdapter(symbols, exchanges)
        self.latest_prices: Dict[str, MultiExchangePrices] = self._adapter.latest_prices
        self.exchange_instances: Dict[str, Any] = self._adapter.exchange_instances
        self.ws_connections: Dict[str, Any] = {}

        super().__init__(
            name="ExchangeCollector",
            circuit_config=CircuitBreakerConfig(
                name="exchange_circuit",
                failure_threshold=5,
                recovery_timeout=60.0
            ),
            retry_config=RetryConfig(
                max_attempts=2,
                initial_delay=1.0
            ),
            fallback_value={}
        )

    async def collect(self) -> CollectorResult:
        try:
            results = await self._adapter.collect()
            self.latest_prices = self._adapter.latest_prices
            return CollectorResult(
                success=bool(results),
                data=results,
                source="ExchangeCollector",
                confidence=0.9
            )
        except Exception as e:
            logger.error(f"Exchange collection failed: {e}")
            return CollectorResult(
                success=False,
                error=str(e),
                source="ExchangeCollector"
            )

    async def get_price_for_trading(self, symbol: str, exchange: str) -> Optional[ExchangePrice]:
        return await self._adapter.get_price_for_trading(symbol, exchange)

    async def get_order_book(self, symbol: str, exchange_name: str = "binance", limit: int = 10) -> Optional[Dict]:
        return await self._adapter.get_order_book(symbol, exchange_name, limit)

    def get_latest_prices(self, symbol: str) -> Optional[MultiExchangePrices]:
        return self._adapter.get_latest_prices(symbol)

    def check_arbitrage(self, symbol: str, threshold_percent: float = 0.005) -> Optional[Dict]:
        return self._adapter.check_arbitrage(symbol, threshold_percent)


class ExchangeWebSocketCollector:
    def __init__(self, exchange: str, symbols: List[str]):
        self._adapter = ExchangeWebSocketAdapter(exchange, symbols)
        self.exchange_name = exchange
        self.symbols = symbols

    async def connect(self):
        await self._adapter.connect()

    def on_price_update(self, callback):
        self._adapter.on_price_update(callback)

    async def disconnect(self):
        await self._adapter.disconnect()
