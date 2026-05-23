"""
TDP Adapter - 将 Collector 结果转换为 TDP 格式
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from infrastructure.logging import get_logger
logger = get_logger("data_service.tdp_adapter")

from infrastructure.tdp.formatter import TDPFormatter


@dataclass
class TDPPriceData:
    symbol: str
    exchange: str
    price: float
    bid: float
    ask: float
    spread: float
    volume_24h: float
    high_24h: float
    low_24h: float
    change_24h: float
    timestamp: float


@dataclass
class TDPNewsData:
    id: str
    title: str
    content: str
    url: str
    source: str
    published_at: float
    sentiment: str
    sentiment_score: float
    entities: List[str]
    topics: List[str]
    black_swan: bool
    timestamp: float


@dataclass
class TDPMacroData:
    asset: str
    price: float
    change_1d: float
    change_7d: float
    sources: List[str]
    timestamp: float


@dataclass
class TDPEtfData:
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    aum: float
    sources: List[str]
    timestamp: float


@dataclass
class TDPSocialData:
    platform: str
    author: str
    content: str
    url: str
    posted_at: float
    sentiment: str
    sentiment_score: float
    timestamp: float


@dataclass
class TDPTraderOpinion:
    trader: str
    asset: str
    opinion: str
    sentiment: str
    confidence: float
    posted_at: float
    sources: List[str]
    timestamp: float


class TDPAdapter:
    def __init__(self, source: str = "data_service"):
        self.source = source
        self._publisher = None

    def set_publisher(self, publisher):
        self._publisher = publisher

    async def publish_price(self, data: TDPPriceData) -> bool:
        try:
            packet = TDPFormatter.format_market_data(
                symbol=data.symbol,
                price=data.price,
                volume=data.volume_24h,
                exchange=data.exchange,
                high=data.high_24h,
                low=data.low_24h,
                bid=data.bid,
                ask=data.ask,
                timestamp=int(data.timestamp),
            )
            if self._publisher:
                await self._publisher.send("tradeagent.raw_data", packet, key=data.symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to publish price TDP: {e}")
            return False

    async def publish_news(self, data: TDPNewsData) -> bool:
        try:
            packet = TDPFormatter.format_news(
                title=data.title,
                content=data.content,
                url=data.url,
                source=data.source,
                sentiment=data.sentiment_score,
                timestamp=int(data.timestamp),
            )
            if self._publisher:
                await self._publisher.send("tradeagent.raw_data", packet, key=data.id)
            return True
        except Exception as e:
            logger.error(f"Failed to publish news TDP: {e}")
            return False

    async def publish_macro(self, data: TDPMacroData) -> bool:
        try:
            packet = TDPFormatter.format_macro_data(
                timestamp=int(data.timestamp),
            )
            if self._publisher:
                await self._publisher.send("tradeagent.raw_data", packet, key=data.asset)
            return True
        except Exception as e:
            logger.error(f"Failed to publish macro TDP: {e}")
            return False

    async def publish_etf(self, data: TDPEtfData) -> bool:
        try:
            packet = TDPFormatter.format_etf_flow(
                symbol=data.symbol,
                inflow=data.inflow,
                outflow=data.outflow,
                aum=data.aum,
                timestamp=int(data.timestamp),
            )
            if self._publisher:
                await self._publisher.send("tradeagent.raw_data", packet, key=data.symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to publish ETF TDP: {e}")
            return False

    async def publish_social(self, data: TDPSocialData) -> bool:
        try:
            packet = TDPFormatter.format_social(
                platform=data.platform,
                author=data.author,
                content=data.content,
                sentiment=data.sentiment_score,
                timestamp=int(data.timestamp),
            )
            if self._publisher:
                await self._publisher.send("tradeagent.raw_data", packet, key=data.author)
            return True
        except Exception as e:
            logger.error(f"Failed to publish social TDP: {e}")
            return False

    async def publish_trader_opinion(self, data: TDPTraderOpinion) -> bool:
        try:
            packet = TDPFormatter.format_news(
                title=f"[{data.trader}] {data.opinion}",
                content=f"Sentiment: {data.sentiment}, Confidence: {data.confidence}",
                url="",
                source=data.sources[0] if data.sources else "trader",
                sentiment=data.sentiment_score if data.sentiment_score else (1.0 if data.sentiment == "bullish" else -1.0 if data.sentiment == "bearish" else 0.0),
                timestamp=int(data.posted_at),
            )
            if self._publisher:
                await self._publisher.send("tradeagent.raw_data", packet, key=data.trader)
            return True
        except Exception as e:
            logger.error(f"Failed to publish trader opinion TDP: {e}")
            return False

    async def publish_batch(self, packets: List[Dict[str, Any]]) -> int:
        success_count = 0
        for packet_data in packets:
            try:
                if self._publisher:
                    await self._publisher.send("tradeagent.raw_data", packet_data, key=packet_data.get("key", ""))
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to publish batch packet: {e}")
        return success_count


_tdp_adapter: Optional[TDPAdapter] = None


def get_tdp_adapter() -> TDPAdapter:
    global _tdp_adapter
    if _tdp_adapter is None:
        _tdp_adapter = TDPAdapter()
    return _tdp_adapter
