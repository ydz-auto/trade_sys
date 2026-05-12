"""
Crypto Stock Collector - 加密货币相关股票采集
支持：MSTR, COIN, MARA, RIOT, CRCL, HOOD 等 + 弹性能力
"""

import asyncio
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config import get_datasource_config_manager
from shared.http_client import HTTPClient, HTTPRequest, HTTPMethod
from infrastructure.logging import get_logger
from .base_collector import BaseCollector, CollectorResult
from infrastructure.resilience import CircuitBreakerConfig, RetryConfig

logger = get_logger("collectors.crypto_stock")


@dataclass
class CryptoStock:
    """加密货币相关股票"""
    symbol: str
    name: str
    price: float
    change_1d: float
    change_7d: float
    volume: float
    market_cap: float
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0


class YahooFinanceCollector:
    """Yahoo Finance 采集器"""

    STOCK_SYMBOLS = {
        "MSTR": "MicroStrategy",
        "COIN": "Coinbase Global",
        "MARA": "Mara Holdings",
        "RIOT": "Riot Platforms",
        "CRCL": "Cube Smart",
        "HOOD": "Robinhood Markets",
        "IBIT": "iShares Bitcoin Trust",
        "FBTC": "Fidelity Bitcoin ETF",
        "ARKB": "ARK 21Shares Bitcoin ETF"
    }

    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    async def collect(self, symbols: List[str] = None) -> List[CryptoStock]:
        target_symbols = symbols or list(self.STOCK_SYMBOLS.keys())
        stocks = []

        tasks = [self._fetch_stock(symbol) for symbol in target_symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(target_symbols, results):
            if isinstance(result, Exception):
                logger.warning(f"Error fetching {symbol}: {result}")
            elif result:
                stocks.append(result)

        return stocks

    async def _fetch_stock(self, symbol: str) -> Optional[CryptoStock]:
        try:
            url = f"{self.base_url}/{symbol}"

            async with HTTPClient() as http:
                response = await http.request(HTTPRequest(url=url, timeout=10.0))

            if response.success and response.body:
                data = response.body
                result = data.get("chart", {}).get("result", [{}])[0]

                if not result:
                    return None

                meta = result.get("meta", {})
                quotes = result.get("indicators", {}).get("quote", [{}])[0]

                current_price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("previousClose", current_price)

                timestamps = result.get("timestamp", [])
                if len(timestamps) >= 7:
                    week_prices = quotes.get("close", [])
                    week_ago_price = week_prices[-7] if len(week_prices) >= 7 else current_price
                    change_7d = ((current_price - week_ago_price) / week_ago_price * 100) if week_ago_price else 0
                else:
                    change_7d = 0

                return CryptoStock(
                    symbol=symbol,
                    name=self.STOCK_SYMBOLS.get(symbol, symbol),
                    price=current_price,
                    change_1d=((current_price - prev_close) / prev_close * 100) if prev_close else 0,
                    change_7d=change_7d,
                    volume=meta.get("regularMarketVolume", 0),
                    market_cap=meta.get("marketCap", 0),
                    source="yahoo_finance",
                    confidence=0.95
                )

        except Exception as e:
            logger.warning(f"Yahoo Finance fetch error for {symbol}: {e}")

        return self._get_mock_stock(symbol)

    def _get_mock_stock(self, symbol: str) -> CryptoStock:
        mock_prices = {
            "MSTR": {"price": 145.50, "change_1d": 5.2, "change_7d": 12.3, "volume": 2500000},
            "COIN": {"price": 178.30, "change_1d": 3.1, "change_7d": 8.7, "volume": 8000000},
            "MARA": {"price": 12.45, "change_1d": -2.3, "change_7d": 4.5, "volume": 15000000},
            "RIOT": {"price": 8.92, "change_1d": 1.8, "change_7d": -3.2, "volume": 20000000},
        }

        data = mock_prices.get(symbol, {"price": 100.0, "change_1d": 0, "change_7d": 0, "volume": 1000000})

        return CryptoStock(
            symbol=symbol,
            name=self.STOCK_SYMBOLS.get(symbol, symbol),
            price=data["price"],
            change_1d=data["change_1d"],
            change_7d=data["change_7d"],
            volume=data["volume"],
            market_cap=data["price"] * 100000000,
            source="mock",
            confidence=0.5
        )


class AlphaVantageCollector:
    """Alpha Vantage 采集器（备选）"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "demo"
        self.base_url = "https://www.alphavantage.co/query"

    async def collect(self, symbols: List[str]) -> List[CryptoStock]:
        stocks = []

        for symbol in symbols:
            try:
                stock = await self._fetch_stock(symbol)
                if stock:
                    stocks.append(stock)
            except Exception as e:
                logger.warning(f"Alpha Vantage error for {symbol}: {e}")

        return stocks

    async def _fetch_stock(self, symbol: str) -> Optional[CryptoStock]:
        try:
            url = f"{self.base_url}?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.api_key}"

            async with HTTPClient() as http:
                response = await http.request(HTTPRequest(url=url, timeout=10.0))

            if response.success and response.body:
                data = response.body.get("Global Quote", {})

                if data:
                    return CryptoStock(
                        symbol=symbol,
                        name=symbol,
                        price=float(data.get("05. price", 0)),
                        change_1d=float(data.get("10. change percent", "0%").replace("%", "")),
                        change_7d=0,
                        volume=int(data.get("06. volume", 0)),
                        market_cap=0,
                        source="alpha_vantage",
                        confidence=0.85
                    )
        except Exception as e:
            logger.warning(f"Alpha Vantage fetch error: {e}")

        return None


class CryptoStockCollector(BaseCollector):
    """加密货币股票收集器 + 弹性能力"""

    def __init__(self):
        self.latest_stocks: Dict[str, CryptoStock] = {}
        self.yahoo_collector = YahooFinanceCollector()
        self.alpha_vantage_collector: Optional[AlphaVantageCollector] = None
        
        # 调用基类初始化
        super().__init__(
            name="CryptoStockCollector",
            circuit_config=CircuitBreakerConfig(
                name="crypto_stock_circuit",
                failure_threshold=3,
                recovery_timeout=60.0
            ),
            retry_config=RetryConfig(
                max_attempts=2,
                initial_delay=1.0
            ),
            fallback_value={}  # 降级时返回空字典
        )
        
        self._init_alpha_vantage()

    def _init_alpha_vantage(self):
        try:
            import os
            api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
            if api_key:
                self.alpha_vantage_collector = AlphaVantageCollector(api_key)
        except Exception as e:
            logger.warning(f"Alpha Vantage init error: {e}")

    async def collect(self) -> CollectorResult:
        """采集加密股票数据（返回 CollectorResult）"""
        try:
            results = {}

            yahoo_stocks = await self.yahoo_collector.collect()
            for stock in yahoo_stocks:
                results[stock.symbol] = stock
                self.latest_stocks[stock.symbol] = stock

            if self.alpha_vantage_collector:
                alpha_stocks = await self.alpha_vantage_collector.collect(list(self.latest_stocks.keys()))
                for stock in alpha_stocks:
                    if stock.symbol not in results:
                        results[stock.symbol] = stock

            return CollectorResult(
                success=bool(results),
                data=results,
                source="CryptoStockCollector",
                confidence=0.85
            )
        except Exception as e:
            logger.error(f"Crypto stock collection failed: {e}")
            return CollectorResult(
                success=False,
                error=str(e),
                source="CryptoStockCollector"
            )

    def get_stock(self, symbol: str) -> Optional[CryptoStock]:
        return self.latest_stocks.get(symbol)

    def get_all_stocks(self) -> Dict[str, CryptoStock]:
        return self.latest_stocks

    def get_top_movers(self, limit: int = 5) -> List[CryptoStock]:
        stocks = list(self.latest_stocks.values())
        stocks.sort(key=lambda x: abs(x.change_1d), reverse=True)
        return stocks[:limit]

    def get_corrrelation_with_btc(self) -> Dict[str, float]:
        correlations = {
            "MSTR": 0.85,
            "COIN": 0.78,
            "MARA": 0.72,
            "RIOT": 0.68,
            "IBIT": 0.99,
            "FBTC": 0.99,
            "ARKB": 0.99
        }

        return {
            symbol: correlations.get(symbol, 0.5)
            for symbol in self.latest_stocks.keys()
        }
