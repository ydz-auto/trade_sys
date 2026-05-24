import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.logging import get_logger

try:
    import ccxt
except ImportError:
    ccxt = None

try:
    import httpx
except ImportError:
    httpx = None

logger = get_logger("engines.adapters.exchange")


@dataclass
class ExchangePrice:
    exchange: str
    symbol: str
    price: float
    bid: float
    ask: float
    spread: float
    spread_percent: float
    volume_24h: float
    high_24h: float
    low_24h: float
    change_24h: float
    timestamp: datetime
    latency_ms: int
    status: str = "ok"


@dataclass
class MultiExchangePrices:
    symbol: str
    prices: Dict[str, ExchangePrice] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def all_ok(self) -> bool:
        return all(p.status == "ok" for p in self.prices.values())

    @property
    def available_exchanges(self) -> List[str]:
        return [name for name, p in self.prices.items() if p.status == "ok"]

    @property
    def max_price_info(self) -> tuple:
        valid = [(n, p) for n, p in self.prices.items() if p.status == "ok"]
        return max(valid, key=lambda x: x[1].price) if valid else (None, None)

    @property
    def min_price_info(self) -> tuple:
        valid = [(n, p) for n, p in self.prices.items() if p.status == "ok"]
        return min(valid, key=lambda x: x[1].price) if valid else (None, None)

    def arbitrage_opportunity(self, threshold_percent: float = 0.005) -> Optional[Dict]:
        min_name, min_price = self.min_price_info
        max_name, max_price = self.max_price_info
        if min_name is None or max_name is None:
            return None
        diff = max_price.price - min_price.price
        diff_percent = diff / min_price.price * 100
        if diff_percent > threshold_percent:
            return {
                "buy_exchange": min_name,
                "sell_exchange": max_name,
                "buy_price": min_price.price,
                "sell_price": max_price.price,
                "diff": diff,
                "diff_percent": diff_percent
            }
        return None


class ExchangeAdapter:
    def __init__(self, symbols: List[str], exchanges: List[str]):
        self.symbols = symbols
        self.exchanges = exchanges
        self.exchange_instances: Dict[str, Any] = {}
        self.latest_prices: Dict[str, MultiExchangePrices] = {}
        self._init_exchanges()

    def _init_exchanges(self):
        if ccxt is None:
            logger.warning("CCXT not installed, will use CoinGecko backup")
            return
        exchange_configs = {
            "binance": {"id": "binance", "enableRateLimit": True},
            "okx": {"id": "okx", "enableRateLimit": True},
            "hyperliquid": {"id": "hyperliquid", "enableRateLimit": True},
            "coinbase": {"id": "coinbase", "enableRateLimit": True},
            "gate": {"id": "gate", "enableRateLimit": True},
            "bybit": {"id": "bybit", "enableRateLimit": True},
        }
        for exchange_name in self.exchanges:
            if exchange_name in exchange_configs:
                try:
                    exchange_class = getattr(ccxt, exchange_configs[exchange_name]["id"])
                    self.exchange_instances[exchange_name] = exchange_class()
                    logger.info(f"Initialized {exchange_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize {exchange_name}: {e}")

    async def collect(self) -> Dict[str, MultiExchangePrices]:
        results = {}
        for symbol in self.symbols:
            multi_prices = MultiExchangePrices(symbol=symbol)
            has_valid_price = False
            for exchange_name, exchange in self.exchange_instances.items():
                try:
                    price = await self._fetch_ticker(exchange, symbol, exchange_name)
                    if price:
                        multi_prices.prices[exchange_name] = price
                        has_valid_price = True
                except Exception as e:
                    logger.error(f"Error fetching {symbol} from {exchange_name}: {e}")
                    multi_prices.prices[exchange_name] = self._create_error_price(symbol, exchange_name)

            if not has_valid_price:
                logger.info(f"CCXT failed for {symbol}, trying CoinGecko")
                coingecko_price = await self._fetch_from_coingecko(symbol)
                if coingecko_price:
                    multi_prices.prices["coingecko"] = coingecko_price
                    has_valid_price = True

            if not has_valid_price:
                logger.warning(f"All sources failed for {symbol}, using mock data")
                multi_prices.prices["mock"] = self._create_mock_price(symbol)

            self.latest_prices[symbol] = multi_prices
            results[symbol] = multi_prices
        return results

    async def _fetch_from_coingecko(self, symbol: str) -> Optional[ExchangePrice]:
        if httpx is None:
            return None
        start_time = time.time()
        coin_id_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "DOGE": "dogecoin"
        }
        coin_id = coin_id_map.get(symbol)
        if not coin_id:
            return None
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true&include_market_cap=false"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                if coin_id in data:
                    price_data = data[coin_id]
                    price = float(price_data.get("usd", 0))
                    change_24h = float(price_data.get("usd_24h_change", 0)) / 100 * price
                    volume_24h = float(price_data.get("usd_24h_vol", 0))
                    latency_ms = int((time.time() - start_time) * 1000)
                    return ExchangePrice(
                        exchange="coingecko",
                        symbol=symbol,
                        price=price,
                        bid=price * 0.9998,
                        ask=price * 1.0002,
                        spread=price * 0.0004,
                        spread_percent=0.04,
                        volume_24h=volume_24h,
                        high_24h=price * 1.01,
                        low_24h=price * 0.99,
                        change_24h=change_24h,
                        timestamp=datetime.now(),
                        latency_ms=latency_ms,
                        status="ok"
                    )
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed for {symbol}: {e}")
        return None

    async def _fetch_ticker(self, exchange, symbol: str, exchange_name: str) -> Optional[ExchangePrice]:
        start_time = time.time()
        try:
            ticker = exchange.fetch_ticker(f"{symbol}/USDT")
            latency_ms = int((time.time() - start_time) * 1000)
            price = ticker.get("last", 0)
            bid = ticker.get("bid", 0) or price * 0.9998
            ask = ticker.get("ask", 0) or price * 1.0002
            spread = ask - bid
            spread_percent = (spread / ask * 100) if ask > 0 else 0
            return ExchangePrice(
                exchange=exchange_name,
                symbol=symbol,
                price=price,
                bid=bid,
                ask=ask,
                spread=spread,
                spread_percent=spread_percent,
                volume_24h=ticker.get("baseVolume", 0),
                high_24h=ticker.get("high", 0),
                low_24h=ticker.get("low", 0),
                change_24h=ticker.get("change", 0),
                timestamp=datetime.now(),
                latency_ms=latency_ms,
                status="ok"
            )
        except Exception as e:
            logger.error(f"Fetch ticker error: {e}")
            return None

    def _create_error_price(self, symbol: str, exchange_name: str) -> ExchangePrice:
        return ExchangePrice(
            exchange=exchange_name,
            symbol=symbol,
            price=0, bid=0, ask=0,
            spread=0, spread_percent=0,
            volume_24h=0, high_24h=0, low_24h=0, change_24h=0,
            timestamp=datetime.now(),
            latency_ms=0,
            status="error"
        )

    def _create_mock_price(self, symbol: str) -> ExchangePrice:
        mock_prices = {
            "BTC": 81205.50, "ETH": 3842.30, "SOL": 142.50, "DOGE": 0.1523
        }
        price = mock_prices.get(symbol, 100.0)
        return ExchangePrice(
            exchange="mock",
            symbol=symbol,
            price=price,
            bid=price * 0.9998,
            ask=price * 1.0002,
            spread=price * 0.0004,
            spread_percent=0.04,
            volume_24h=1000000,
            high_24h=price * 1.02,
            low_24h=price * 0.98,
            change_24h=price * 0.023,
            timestamp=datetime.now(),
            latency_ms=10,
            status="mock"
        )

    async def get_price_for_trading(self, symbol: str, exchange: str) -> Optional[ExchangePrice]:
        if symbol in self.latest_prices:
            prices = self.latest_prices[symbol]
            if exchange in prices.prices:
                return prices.prices[exchange]
        await self.collect()
        if symbol in self.latest_prices and exchange in self.latest_prices[symbol].prices:
            return self.latest_prices[symbol].prices[exchange]
        return None

    async def get_order_book(self, symbol: str, exchange_name: str = "binance", limit: int = 10) -> Optional[Dict]:
        if exchange_name not in self.exchange_instances:
            return None
        try:
            exchange = self.exchange_instances[exchange_name]
            order_book = exchange.fetch_order_book(f"{symbol}/USDT", limit)
            return order_book
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return None

    def get_latest_prices(self, symbol: str) -> Optional[MultiExchangePrices]:
        return self.latest_prices.get(symbol)

    def check_arbitrage(self, symbol: str, threshold_percent: float = 0.005) -> Optional[Dict]:
        prices = self.latest_prices.get(symbol)
        if prices:
            return prices.arbitrage_opportunity(threshold_percent)
        return None


class ExchangeWebSocketAdapter:
    def __init__(self, exchange: str, symbols: List[str]):
        self.exchange_name = exchange
        self.symbols = symbols
        self.ws = None
        self._running = False
        self._price_callbacks: List[callable] = []

    async def connect(self):
        if ccxt is None:
            logger.warning("CCXT not available")
            return
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            exchange = exchange_class()
            if hasattr(exchange, 'watch_ticker'):
                self._running = True
                asyncio.create_task(self._watch_tickers(exchange))
                logger.info(f"WebSocket connected for {self.exchange_name}")
            else:
                logger.warning(f"{self.exchange_name} does not support watch_ticker")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")

    async def _watch_tickers(self, exchange):
        while self._running:
            try:
                for symbol in self.symbols:
                    ticker = await exchange.watch_ticker(f"{symbol}/USDT")
                    await self._on_ticker(ticker)
            except Exception as e:
                logger.error(f"Watch ticker error: {e}")
                await asyncio.sleep(5)

    async def _on_ticker(self, ticker: Dict):
        price_data = {
            "symbol": ticker.get("symbol", "").replace("/USDT", ""),
            "price": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "volume": ticker.get("baseVolume"),
            "timestamp": ticker.get("timestamp")
        }
        for callback in self._price_callbacks:
            try:
                await callback(self.exchange_name, price_data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def on_price_update(self, callback: callable):
        self._price_callbacks.append(callback)

    async def disconnect(self):
        self._running = False
        if self.ws:
            await self.ws.close()
        logger.info(f"WebSocket disconnected for {self.exchange_name}")
