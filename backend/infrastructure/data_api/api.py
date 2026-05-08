"""
Data API - 数据接口
提供 REST/WebSocket 数据查询接口
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from infrastructure.logging import get_logger
logger = get_logger("data_api")


class PriceResponse(BaseModel):
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    exchange: str
    timestamp: datetime


class ETFResponse(BaseModel):
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    aum: float
    sources: List[str]
    confidence: float
    timestamp: datetime


class NewsResponse(BaseModel):
    id: str
    title: str
    content: str
    source: str
    sentiment: str
    sentiment_score: float
    event_type: str
    black_swan_score: float
    urgency: str
    affected_symbols: List[str]
    is_black_swan: bool
    published: int
    timestamp: datetime


class MacroResponse(BaseModel):
    asset: str
    name: str
    price: float
    change_1d: float
    change_7d: float
    unit: str
    sources: List[str]
    timestamp: datetime


class TraderOpinionResponse(BaseModel):
    trader_id: str
    trader_name: str
    platform: str
    content: str
    sentiment: str
    sentiment_score: float
    mentioned_assets: List[str]
    time_horizon: str
    influence_score: float
    published: int
    timestamp: datetime


class AggregateSentimentResponse(BaseModel):
    sentiment: str
    score: float
    count: int
    bullish_count: int
    bearish_count: int
    timestamp: datetime


class DataAPI:
    """数据API"""

    def __init__(self):
        self.exchange_collector = None
        self.etf_collector = None
        self.news_collector = None
        self.macro_collector = None
        self.trader_collector = None
        self.crypto_stock_collector = None

    async def get_price(self, symbol: str, exchange: str = "binance") -> Optional[PriceResponse]:
        """获取单个交易对价格"""
        if not self.exchange_collector:
            from services.data_service.collectors import ExchangeCollector
            self.exchange_collector = ExchangeCollector(
                symbols=[symbol],
                exchanges=["binance", "okx", "coinbase"]
            )

        price_data = await self.exchange_collector.get_price_for_trading(symbol, exchange)

        if price_data:
            return PriceResponse(
                symbol=symbol,
                price=price_data.price,
                change_24h=price_data.change_24h,
                volume_24h=price_data.volume_24h,
                exchange=exchange,
                timestamp=price_data.timestamp
            )
        return None

    async def get_all_prices(self, symbols: List[str] = None) -> List[PriceResponse]:
        """获取所有交易对价格"""
        if not self.exchange_collector:
            from services.data_service.collectors import ExchangeCollector
            self.exchange_collector = ExchangeCollector(
                symbols=symbols or ["BTC", "ETH", "SOL", "DOGE"],
                exchanges=["binance", "okx"]
            )

        await self.exchange_collector.collect()

        results = []
        for symbol in self.exchange_collector.symbols:
            multi_prices = self.exchange_collector.get_latest_prices(symbol)
            if multi_prices and "binance" in multi_prices.prices:
                p = multi_prices.prices["binance"]
                results.append(PriceResponse(
                    symbol=symbol,
                    price=p.price,
                    change_24h=p.change_24h,
                    volume_24h=p.volume_24h,
                    exchange="binance",
                    timestamp=p.timestamp
                ))

        return results

    async def get_etf_flow(self, symbol: str = "BTC") -> Optional[ETFResponse]:
        """获取ETF资金流"""
        if not self.etf_collector:
            from services.data_service.collectors import ETFCollector
            self.etf_collector = ETFCollector()

        result = self.etf_collector.get_latest_flow(symbol)

        if result:
            return ETFResponse(
                symbol=symbol,
                net_flow=result.net_flow,
                inflow=result.inflow,
                outflow=result.outflow,
                aum=result.aum,
                sources=result.sources_used,
                confidence=result.confidence,
                timestamp=result.timestamp
            )
        return None

    async def get_latest_news(
        self,
        limit: int = 20,
        sentiment: str = None,
        include_black_swan: bool = True
    ) -> List[NewsResponse]:
        """获取最新新闻"""
        if not self.news_collector:
            from services.data_service.collectors import NewsCollector
            self.news_collector = NewsCollector()

        await self.news_collector.collect()

        if sentiment:
            news_list = self.news_collector.get_news_by_sentiment(sentiment)
        else:
            news_list = self.news_collector.get_latest_news(
                limit=limit,
                include_black_swan=include_black_swan
            )

        return [NewsResponse(**item) for item in news_list]

    async def get_black_swan_news(self) -> List[NewsResponse]:
        """获取黑天鹅新闻"""
        if not self.news_collector:
            from services.data_service.collectors import NewsCollector
            self.news_collector = NewsCollector()

        await self.news_collector.collect()

        news_list = self.news_collector.get_black_swan_news()
        return [NewsResponse(**item) for item in news_list]

    async def get_macro_data(self, asset: str = None) -> List[MacroResponse]:
        """获取宏观数据"""
        if not self.macro_collector:
            from services.data_service.collectors import MacroCollector
            self.macro_collector = MacroCollector()

        await self.macro_collector.collect()

        results = []
        data = self.macro_collector.get_latest_data(asset)

        if isinstance(data, dict):
            for asset_name, result in data.items():
                info = self.macro_collector.get_asset_info(asset_name)
                results.append(MacroResponse(
                    asset=asset_name,
                    name=info.get("name", asset_name),
                    price=result.price,
                    change_1d=result.change_1d,
                    change_7d=result.change_7d,
                    unit=info.get("unit", ""),
                    sources=result.sources_used,
                    timestamp=result.timestamp
                ))
        elif data:
            info = self.macro_collector.get_asset_info(data.asset)
            results.append(MacroResponse(
                asset=data.asset,
                name=info.get("name", data.asset),
                price=data.price,
                change_1d=data.change_1d,
                change_7d=data.change_7d,
                unit=info.get("unit", ""),
                sources=data.sources_used,
                timestamp=data.timestamp
            ))

        return results

    async def get_trader_opinions(
        self,
        asset: str = None,
        sentiment: str = None
    ) -> List[TraderOpinionResponse]:
        """获取交易员观点"""
        if not self.trader_collector:
            from services.data_service.collectors import TraderDataCollector
            self.trader_collector = TraderDataCollector()

        await self.trader_collector.collect()

        if asset:
            opinions = self.trader_collector.get_opinions_by_asset(asset)
        elif sentiment:
            if sentiment == "bullish":
                opinions = self.trader_collector.get_bullish_traders()
            elif sentiment == "bearish":
                opinions = self.trader_collector.get_bearish_traders()
            else:
                opinions = []
        else:
            opinions = [
                self._statement_to_response(s)
                for s in self.trader_collector.latest_statements
            ]
            return opinions

        return [TraderOpinionResponse(**op) for op in opinions]

    async def get_aggregate_sentiment(self) -> AggregateSentimentResponse:
        """获取聚合情绪"""
        if not self.trader_collector:
            from services.data_service.collectors import TraderDataCollector
            self.trader_collector = TraderDataCollector()

        await self.trader_collector.collect()

        sentiment = self.trader_collector.get_aggregate_sentiment()

        return AggregateSentimentResponse(
            sentiment=sentiment["sentiment"],
            score=sentiment["score"],
            count=sentiment["count"],
            bullish_count=sentiment["bullish_count"],
            bearish_count=sentiment["bearish_count"],
            timestamp=datetime.now()
        )

    async def get_crypto_stocks(self) -> List[Dict]:
        """获取加密相关股票"""
        if not self.crypto_stock_collector:
            from services.data_service.collectors import CryptoStockCollector
            self.crypto_stock_collector = CryptoStockCollector()

        await self.crypto_stock_collector.collect()

        stocks = self.crypto_stock_collector.get_all_stocks()

        return [
            {
                "symbol": symbol,
                "name": stock.name,
                "price": stock.price,
                "change_1d": stock.change_1d,
                "change_7d": stock.change_7d,
                "volume": stock.volume,
                "source": stock.source
            }
            for symbol, stock in stocks.items()
        ]

    def _statement_to_response(self, statement) -> TraderOpinionResponse:
        return TraderOpinionResponse(
            trader_id=statement.trader_id,
            trader_name=statement.trader_name,
            platform=statement.platform,
            content=statement.content,
            sentiment=statement.sentiment,
            sentiment_score=statement.sentiment_score,
            mentioned_assets=statement.mentioned_assets,
            time_horizon=statement.time_horizon,
            influence_score=statement.influence_score,
            published=statement.published,
            timestamp=statement.timestamp
        )


_data_api: Optional[DataAPI] = None


def get_data_api() -> DataAPI:
    global _data_api
    if _data_api is None:
        _data_api = DataAPI()
    return _data_api
