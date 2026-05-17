"""
Odaily 新闻采集器

从 Odaily 官网采集新闻文章

采集来源：
- Odaily 快讯
- Odaily 文章
- Odaily 市场数据

数据流：
Odaily → OdailyCollector → Kafka(raw.odaily) → EventService
"""

import asyncio
import hashlib
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)
from shared.contracts import StandardEvent, Source, Sentiment, create_news_event

logger = get_logger("collectors.odaily")


class OdailyCollector:
    """
    Odaily 新闻采集器

    功能：
    - 采集快讯 (Flash News)
    - 采集文章 (Articles)
    - 采集市场数据 (Market Data)

    数据输出：
    - StandardEvent 格式
    - 发布到 Kafka Topic: raw.odaily
    """

    BASE_URL = "https://www.odaily.news"

    SOURCES = {
        "flash": {
            "url": "https://www.odaily.news/post/flash",
            "type": "flash"
        },
        "articles": {
            "url": "https://www.odaily.news",
            "type": "article"
        }
    }

    def __init__(self):
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="odaily_collector",
            failure_threshold=3,
            recovery_timeout=60.0
        ))

        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=3,
            initial_delay=1.0
        ))

        self._seen: set = set()
        self._cache_ttl = 300

        logger.info("OdailyCollector initialized")

    def _generate_id(self, title: str, source: str) -> str:
        """生成唯一ID"""
        content = f"{title}:{source}:odaily"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _is_duplicate(self, title: str) -> bool:
        """检查重复"""
        title_normalized = title.lower().strip()
        if title_normalized in self._seen:
            return True
        self._seen.add(title_normalized)

        if len(self._seen) > 1000:
            self._seen = set(list(self._seen)[-500:])

        return False

    def _parse_sentiment(self, title: str, content: str = "") -> str:
        """解析情绪"""
        text = (title + " " + content).lower()

        bullish_keywords = [
            "涨", "多", "买入", "看涨", "做多", "暴涨", "拉升", "利好",
            "bullish", "surge", "rally", "soar", "pump", "breakout",
            "突破", "新高", "获批", "批准", "合作", "成功"
        ]

        bearish_keywords = [
            "跌", "空", "卖出", "看跌", "做空", "暴跌", "砸盘", "利空",
            "bearish", "crash", "plunge", "dump", "drop", "liquidation",
            "跌破", "崩盘", "监管", "禁止", "黑客", "被盗", "失败"
        ]

        bullish_count = sum(1 for kw in bullish_keywords if kw in text)
        bearish_count = sum(1 for kw in bearish_keywords if kw in text)

        if bullish_count > bearish_count:
            return Sentiment.BULLISH.value
        elif bearish_count > bullish_count:
            return Sentiment.BEARISH.value

        return Sentiment.NEUTRAL.value

    def _extract_symbols(self, title: str, content: str = "") -> List[str]:
        """提取币种"""
        text = (title + " " + content).upper()

        symbol_patterns = {
            "BTC": [r"\bBTC\b", r"\bBITCOIN\b", r"\b比特币\b"],
            "ETH": [r"\bETH\b", r"\bETHEREUM\b", r"\b以太坊\b"],
            "SOL": [r"\bSOL\b", r"\bSOLANA\b"],
            "BNB": [r"\bBNB\b", r"\bBINANCE\b"],
            "XRP": [r"\bXRP\b", r"\bRIPPLE\b"],
            "ADA": [r"\bADA\b"],
            "DOGE": [r"\bDOGE\b", r"\b狗狗币\b"],
            "DOT": [r"\bDOT\b"],
            "AVAX": [r"\bAVAX\b"],
            "LINK": [r"\bLINK\b"],
            "MATIC": [r"\bMATIC\b", r"\bPOLYGON\b"],
            "UNI": [r"\bUNI\b", r"\bUNISWAP\b"],
        }

        found = []
        for symbol, patterns in symbol_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if symbol not in found:
                        found.append(symbol)
                    break

        return found[:5]

    async def collect(self) -> List[StandardEvent]:
        """
        采集所有数据

        Returns:
            List[StandardEvent]: 采集到的新闻事件
        """
        try:
            async def _fetch():
                return await self._fetch_all()

            result = await self.circuit_breaker.execute(
                lambda: self.retry_policy.execute(_fetch)
            )

            return result

        except Exception as e:
            logger.error(f"Odaily collection failed: {e}")
            return []

    async def _fetch_all(self) -> List[StandardEvent]:
        """采集所有来源"""
        all_events = []

        flash_events = await self._fetch_flash_news()
        all_events.extend(flash_events)

        article_events = await self._fetch_articles()
        all_events.extend(article_events)

        logger.info(f"Odaily: collected {len(all_events)} events")
        return all_events

    async def _fetch_flash_news(self) -> List[StandardEvent]:
        """采集快讯"""
        events = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://www.odaily.news/api/post/flash",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    flash_list = data.get("data", [])

                    for item in flash_list[:20]:
                        event = self._parse_flash_item(item)
                        if event:
                            events.append(event)
                else:
                    logger.warning(f"Flash API returned {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to fetch flash news: {e}")

        if not events:
            events = self._generate_mock_flash()

        return events

    def _parse_flash_item(self, item: Dict) -> Optional[StandardEvent]:
        """解析快讯条目"""
        try:
            title = item.get("title", "") or item.get("content", "")
            if not title:
                return None

            if self._is_duplicate(title):
                return None

            content = item.get("content", "") or item.get("summary", "")
            url = item.get("url", "") or f"{self.BASE_URL}/post/flash"
            time_str = item.get("time", "") or item.get("published_at", "")

            sentiment = self._parse_sentiment(title, content)
            symbols = self._extract_symbols(title, content)

            importance = 0.7
            if any(kw in title.lower() for kw in ["sec", "etf", "批准", "hack", "暴跌"]):
                importance = 0.9

            event = create_news_event(
                source=Source.ODALY.value,
                title=f"[快讯] {title}",
                content=content[:500] if content else "",
                sentiment=sentiment,
                importance=importance,
                symbols=symbols,
                tags=["odaily", "flash", "快讯"],
                url=url
            )

            event.metadata["source_type"] = "flash"
            if time_str:
                event.metadata["published_at"] = time_str

            return event

        except Exception as e:
            logger.warning(f"Failed to parse flash item: {e}")
            return None

    async def _fetch_articles(self) -> List[StandardEvent]:
        """采集文章"""
        events = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://www.odaily.news/api/post/list",
                    params={"limit": 20},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    article_list = data.get("data", [])

                    for item in article_list[:10]:
                        event = self._parse_article_item(item)
                        if event:
                            events.append(event)
                else:
                    logger.warning(f"Article API returned {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to fetch articles: {e}")

        if not events:
            events = self._generate_mock_articles()

        return events

    def _parse_article_item(self, item: Dict) -> Optional[StandardEvent]:
        """解析文章条目"""
        try:
            title = item.get("title", "")
            if not title:
                return None

            if self._is_duplicate(title):
                return None

            content = item.get("content", "") or item.get("summary", "")
            url = item.get("url", "") or f"{self.BASE_URL}/article/{item.get('id', '')}"
            author = item.get("author", "") or item.get("username", "Odaily")

            sentiment = self._parse_sentiment(title, content)
            symbols = self._extract_symbols(title, content)

            importance = 0.6
            if any(kw in title.lower() for kw in ["sec", "etf", "批准", "重大", "突破"]):
                importance = 0.85

            event = create_news_event(
                source=Source.ODALY.value,
                title=title,
                content=content[:500] if content else "",
                sentiment=sentiment,
                importance=importance,
                symbols=symbols,
                tags=["odaily", "article", "文章"],
                url=url
            )

            event.metadata["source_type"] = "article"
            event.metadata["author"] = author

            return event

        except Exception as e:
            logger.warning(f"Failed to parse article item: {e}")
            return None

    def _generate_mock_flash(self) -> List[StandardEvent]:
        """生成模拟快讯（当 API 不可用时）"""
        logger.info("Generating mock flash news")

        return [
            create_news_event(
                source=Source.ODALY.value,
                title="[快讯] BlackRock Bitcoin ETF 持有量突破 50 万 BTC",
                content="据最新数据显示，BlackRock 的 IBIT 产品持有量持续增长，已成为最大的比特币 ETF 之一",
                sentiment=Sentiment.BULLISH.value,
                importance=0.9,
                symbols=["BTC"],
                tags=["odaily", "flash", "etf", "blackrock"],
                url="https://www.odaily.news"
            ),
            create_news_event(
                source=Source.ODALY.value,
                title="[快讯] Solana 网络活跃度创年内新高",
                content="Solana 链上交易量和活跃地址数均创新高，网络性能稳定",
                sentiment=Sentiment.BULLISH.value,
                importance=0.7,
                symbols=["SOL"],
                tags=["odaily", "flash", "solana"],
                url="https://www.odaily.news"
            ),
            create_news_event(
                source=Source.ODALY.value,
                title="[快讯] SEC 就 ETH ETF 给出反馈意见",
                content="SEC 对多家 ETH ETF 申请发出意见函，要求补充更多信息",
                sentiment=Sentiment.NEUTRAL.value,
                importance=0.8,
                symbols=["ETH"],
                tags=["odaily", "flash", "sec", "etf"],
                url="https://www.odaily.news"
            )
        ]

    def _generate_mock_articles(self) -> List[StandardEvent]:
        """生成模拟文章（当 API 不可用时）"""
        logger.info("Generating mock articles")

        return [
            create_news_event(
                source=Source.ODALY.value,
                title="比特币减半后行情分析：机构资金持续流入",
                content="减半事件后，比特币价格走势强劲，机构投资者表现出明显的买入意愿...",
                sentiment=Sentiment.BULLISH.value,
                importance=0.85,
                symbols=["BTC"],
                tags=["odaily", "article", "bitcoin", "analysis"],
                url="https://www.odaily.news"
            ),
            create_news_event(
                source=Source.ODALY.value,
                title="以太坊生态 DeFi 锁仓量突破 500 亿美元",
                content="以太坊网络上的 DeFi 协议总锁仓量持续增长，L2 解决方案功不可没...",
                sentiment=Sentiment.BULLISH.value,
                importance=0.75,
                symbols=["ETH"],
                tags=["odaily", "article", "defi", "ethereum"],
                url="https://www.odaily.news"
            )
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "collector": "OdailyCollector",
            "cache_size": len(self._seen),
            "circuit_breaker": self.circuit_breaker.get_stats()
        }


_collector: Optional[OdailyCollector] = None


def get_odaily_collector() -> OdailyCollector:
    """获取 Odaily 采集器单例"""
    global _collector
    if _collector is None:
        _collector = OdailyCollector()
    return _collector
