"""
Data Storage - 数据存储到 ClickHouse
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger
logger = get_logger("data_service.storage")

from infrastructure.database import get_clickhouse_manager


class DataStorage:
    """数据存储器"""

    def __init__(self):
        self._manager = None
        self._initialized = False

    async def initialize(self):
        """初始化数据库表"""
        if self._initialized:
            return

        try:
            self._manager = get_clickhouse_manager()
            await self._manager.init_tables()
            self._initialized = True
            logger.info("Data storage initialized")

        except Exception as e:
            logger.warning(f"ClickHouse not available, storage disabled: {e}")
            self._initialized = False

    async def store_price(self, symbol: str, exchange: str, data: Dict):
        """存储价格数据"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("prices", [{
                "id": int(time.time() * 1000000),
                "symbol": symbol,
                "exchange": exchange,
                "price": data.get("price", 0),
                "bid": data.get("bid", 0),
                "ask": data.get("ask", 0),
                "spread": data.get("spread", 0),
                "volume_24h": data.get("volume_24h", 0),
                "high_24h": data.get("high_24h", 0),
                "low_24h": data.get("low_24h", 0),
                "change_24h": data.get("change_24h", 0),
                "timestamp": datetime.now()
            }])
        except Exception as e:
            logger.error(f"Failed to store price: {e}")

    async def store_news(self, news: Dict):
        """存储新闻"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("news", [{
                "id": news.get("id", ""),
                "title": news.get("title", "")[:500],
                "content": news.get("content", "")[:2000],
                "url": news.get("url", ""),
                "source": news.get("source", ""),
                "published": datetime.fromtimestamp(news.get("published", time.time())),
                "sentiment": news.get("sentiment", "neutral"),
                "sentiment_score": news.get("sentiment_score", 0),
                "sentiment_confidence": news.get("sentiment_confidence", 0),
                "event_type": news.get("event_type", "normal"),
                "black_swan_score": news.get("black_swan_score", 0),
                "urgency": news.get("urgency", "normal"),
                "affected_symbols": news.get("affected_symbols", [])
            }])

            if news.get("is_black_swan"):
                await self._manager.insert("news_black_swan", [{
                    "id": news.get("id", ""),
                    "title": news.get("title", "")[:500],
                    "content": news.get("content", "")[:2000],
                    "url": news.get("url", ""),
                    "source": news.get("source", ""),
                    "published": datetime.fromtimestamp(news.get("published", time.time())),
                    "sentiment": news.get("sentiment", "neutral"),
                    "black_swan_score": news.get("black_swan_score", 0),
                    "urgency": news.get("urgency", "normal"),
                    "affected_symbols": news.get("affected_symbols", [])
                }])

        except Exception as e:
            logger.error(f"Failed to store news: {e}")

    async def store_etf_flow(self, symbol: str, data: Dict):
        """存储ETF流量"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("etf_flows", [{
                "id": int(time.time() * 1000000),
                "symbol": symbol,
                "net_flow": data.get("net_flow", 0),
                "inflow": data.get("inflow", 0),
                "outflow": data.get("outflow", 0),
                "aum": data.get("aum", 0),
                "source": data.get("source", "aggregated"),
                "confidence": data.get("confidence", 1.0),
                "timestamp": datetime.now()
            }])

            for src, src_data in data.get("individual_flows", {}).items():
                await self._manager.insert("etf_flows_detail", [{
                    "symbol": symbol,
                    "source": src,
                    "net_flow": src_data.get("net_flow", 0),
                    "inflow": src_data.get("inflow", 0),
                    "outflow": src_data.get("outflow", 0),
                    "aum": src_data.get("aum", 0),
                    "confidence": src_data.get("confidence", 1.0),
                    "timestamp": datetime.now()
                }])

        except Exception as e:
            logger.error(f"Failed to store ETF flow: {e}")

    async def store_macro_data(self, asset: str, data: Dict):
        """存储宏观数据"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("macro_data", [{
                "id": int(time.time() * 1000000),
                "asset": asset,
                "price": data.get("price", 0),
                "change_1d": data.get("change_1d", 0),
                "change_7d": data.get("change_7d", 0),
                "volume": data.get("volume", 0),
                "source": data.get("source", "aggregated"),
                "timestamp": datetime.now()
            }])
        except Exception as e:
            logger.error(f"Failed to store macro data: {e}")

    async def store_social_post(self, post: Dict):
        """存储社交媒体帖子"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("social_posts", [{
                "id": post.get("id", ""),
                "platform": post.get("platform", ""),
                "author": post.get("author", ""),
                "author_handle": post.get("author_handle", ""),
                "content": post.get("content", "")[:500],
                "url": post.get("url", ""),
                "published": datetime.fromtimestamp(post.get("published", time.time())),
                "likes": post.get("likes", 0),
                "retweets": post.get("retweets", 0),
                "replies": post.get("replies", 0),
                "sentiment": post.get("sentiment", "neutral"),
                "sentiment_score": post.get("sentiment_score", 0),
                "mentioned_symbols": post.get("mentioned_symbols", []),
                "is_important": post.get("is_important", False)
            }])
        except Exception as e:
            logger.error(f"Failed to store social post: {e}")

    async def store_trader_opinion(self, opinion: Dict):
        """存储交易员观点"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("trader_opinions", [{
                "id": int(time.time() * 1000000),
                "trader_id": opinion.get("trader_id", ""),
                "trader_name": opinion.get("trader_name", ""),
                "platform": opinion.get("platform", ""),
                "content": opinion.get("content", "")[:500],
                "url": opinion.get("url", ""),
                "published": datetime.fromtimestamp(opinion.get("published", time.time())),
                "sentiment": opinion.get("sentiment", "neutral"),
                "sentiment_score": opinion.get("sentiment_score", 0),
                "mentioned_assets": opinion.get("mentioned_assets", []),
                "time_horizon": opinion.get("time_horizon", "medium"),
                "arguments": opinion.get("arguments", []),
                "influence_score": opinion.get("influence_score", 0),
                "credibility": opinion.get("credibility", 0)
            }])
        except Exception as e:
            logger.error(f"Failed to store trader opinion: {e}")

    async def store_crypto_stock(self, symbol: str, data: Dict):
        """存储加密股票"""
        if not self._initialized:
            await self.initialize()

        try:
            await self._manager.insert("crypto_stocks", [{
                "id": int(time.time() * 1000000),
                "symbol": symbol,
                "name": data.get("name", symbol),
                "price": data.get("price", 0),
                "change_1d": data.get("change_1d", 0),
                "change_7d": data.get("change_7d", 0),
                "volume": data.get("volume", 0),
                "market_cap": data.get("market_cap", 0),
                "source": data.get("source", ""),
                "timestamp": datetime.now()
            }])
        except Exception as e:
            logger.error(f"Failed to store crypto stock: {e}")


data_storage = DataStorage()
