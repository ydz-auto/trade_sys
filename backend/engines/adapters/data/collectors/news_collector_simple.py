"""
增强版新闻采集器 - 支持无 LLM 模式（使用关键词匹配）
"""

import asyncio
import re
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
import feedparser
import httpx
from bs4 import BeautifulSoup

from infrastructure.logging import get_logger

logger = get_logger("collectors.news")

SENTIMENT_KEYWORDS = {
    "bullish": [
        "surge", "rally", "soar", "jump", "gain", "rise", "high", "breakout",
        "bull", "bullish", "buy", "accumulate", "upgrade", "adoption",
        "ETF", "approval", "institutional", "inflow", "positive",
        "上涨", "暴涨", "突破", "利好", "买入", "增持"
    ],
    "bearish": [
        "crash", "plunge", "dump", "drop", "fall", "decline", "low", "breakdown",
        "bear", "bearish", "sell", "downgrade", "hack", "exploit", "regulation",
        "ban", "outflow", "negative", "FUD",
        "下跌", "暴跌", "跌破", "利空", "卖出", "减持"
    ]
}

EVENT_KEYWORDS = {
    "FLOW_ETF_INFLOW": ["inflow", "ETF inflow", "资金流入", "etf净流入"],
    "FLOW_ETF_OUTFLOW": ["outflow", "ETF outflow", "资金流出", "etf净流出"],
    "POLICY_ETF_APPROVAL": ["etf", "approval", "批准", "ETF审批"],
    "PROTOCOL_HACK": ["hack", "exploit", "攻击", "漏洞"],
    "RISK_STABLECOIN_DEPEG": ["depeg", "脱锚", "稳定币风险"],
    "POLICY_REGULATION_POSITIVE": ["regulation", "positive", "监管利好", "SEC"],
    "POLICY_REGULATION_NEGATIVE": ["ban", "regulation", "negative", "监管利空", "SEC"],
}

class NewsItem:
    def __init__(self, title: str, content: str = "", source: str = "", url: str = ""):
        self.id = hashlib.md5(title.encode()).hexdigest()[:8]
        self.title = title
        self.content = content
        self.source = source
        self.url = url
        self.published = int(datetime.now().timestamp())
        self.sentiment = "neutral"
        self.sentiment_score = 0.5
        self.sentiment_confidence = 0.3
        self.event_type = "normal"
        self.affected_symbols = []
        self.black_swan_score = 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "published": self.published,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "event_type": self.event_type,
            "affected_symbols": self.affected_symbols,
        }

class Deduplicator:
    """带时间窗口的去重器 - 24小时内的新闻不重复"""
    
    def __init__(self, expire_hours: int = 24):
        self.expire_hours = expire_hours
        self.seen: Dict[str, float] = {}  # title_hash -> timestamp
    
    def _clean_expired(self):
        """清理过期条目"""
        now = datetime.now().timestamp()
        expired_keys = [
            key for key, ts in self.seen.items()
            if now - ts > self.expire_hours * 3600
        ]
        for key in expired_keys:
            del self.seen[key]
    
    def is_duplicate(self, title: str) -> bool:
        """检查是否重复，自动清理过期"""
        self._clean_expired()
        
        title_lower = title.lower().strip()
        title_hash = hashlib.md5(title_lower.encode()).hexdigest()
        
        if title_hash in self.seen:
            # 更新时间戳，延长生命周期
            self.seen[title_hash] = datetime.now().timestamp()
            return True
        
        self.seen[title_hash] = datetime.now().timestamp()
        return False

class BlackSwanDetector:
    def detect(self, title: str, content: str = "") -> Dict:
        text = (title + " " + content).lower()
        black_swan_keywords = [
            "crash", "collapse", "bankruptcy", "fraud", "hack",
            "massive", "catastrophic", "devastating",
            "暴跌", "崩盘", "破产", "欺诈"
        ]
        score = sum(1 for kw in black_swan_keywords if kw in text) * 0.2
        return {"black_swan_score": min(score, 1.0)}

class NewsCollector:
    """增强版新闻采集器 - 支持无 LLM 模式"""

    def __init__(self):
        self.latest_news: List[NewsItem] = []
        self.deduplicator = Deduplicator()
        self.black_swan_detector = BlackSwanDetector()
        self.sources = self._init_sources()

    def _init_sources(self) -> Dict[str, str]:
        return {
            "cointelegraph": "https://cointelegraph.com/rss",
            "cryptonews": "https://cryptonews.com/news/feed/",
            "decrypt": "https://decrypt.co/feed",
            "theblock": "https://www.theblock.co/rss.xml",
            "bitcoinist": "https://bitcoinist.com/feed/",
        }

    async def collect(self) -> List[NewsItem]:
        """采集所有来源的新闻"""
        all_news = []

        # 1. RSS 源采集
        for source_name, url in self.sources.items():
            try:
                news = await self._fetch_rss(source_name, url)
                all_news.extend(news)
                logger.info(f"[{source_name}] Fetched {len(news)} news")
            except Exception as e:
                logger.warning(f"[{source_name}] Error: {e}")

        # 2. 去重
        deduplicated = self._deduplicate(all_news)
        logger.info(f"After dedup: {len(deduplicated)} news")

        # 3. 情绪分析（无 LLM 模式）
        analyzed = self._analyze_sentiment_simple(deduplicated)

        # 4. 黑天鹅检测
        self._detect_black_swan(analyzed)

        # 5. 排序
        self.latest_news = sorted(
            analyzed,
            key=lambda x: (x.published, x.black_swan_score),
            reverse=True
        )[:50]

        logger.info(f"Total collected: {len(self.latest_news)} news")
        return self.latest_news

    async def _fetch_rss(self, source_name: str, url: str) -> List[NewsItem]:
        """获取 RSS 源"""
        if "api" in source_name:
            return await self._fetch_api(source_name, url)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                feed = feedparser.parse(response.text)
                news_items = []

                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    content = entry.get("summary", "")[:200]
                    link = entry.get("link", "")

                    if title:
                        item = NewsItem(
                            title=title.strip(),
                            content=BeautifulSoup(content, "html.parser").get_text(),
                            source=source_name,
                            url=link
                        )
                        news_items.append(item)

                return news_items
        except Exception as e:
            logger.error(f"[{source_name}] RSS fetch error: {e}")
            return []

    async def _fetch_api(self, source_name: str, url: str) -> List[NewsItem]:
        """获取 API 源"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                news_items = []
                if "results" in data:
                    for item in data["results"][:10]:
                        title = item.get("title", "")
                        if title:
                            news_items.append(NewsItem(
                                title=title,
                                content=item.get("meta", {}).get("description", "")[:200],
                                source=source_name,
                                url=item.get("url", "")
                            ))
                return news_items
        except Exception as e:
            logger.error(f"[{source_name}] API fetch error: {e}")
            return []

    def _deduplicate(self, news: List[NewsItem]) -> List[NewsItem]:
        """去重"""
        unique_news = []
        for item in news:
            if not self.deduplicator.is_duplicate(item.title):
                unique_news.append(item)
        return unique_news

    def _analyze_sentiment_simple(self, news: List[NewsItem]) -> List[NewsItem]:
        """基于关键词的简单情绪分析（无 LLM）"""
        for item in news:
            text = (item.title + " " + item.content).lower()

            # 计算情绪分数
            bullish_count = sum(1 for kw in SENTIMENT_KEYWORDS["bullish"] if kw.lower() in text)
            bearish_count = sum(1 for kw in SENTIMENT_KEYWORDS["bearish"] if kw.lower() in text)

            total = bullish_count + bearish_count
            if total > 0:
                item.sentiment_score = bullish_count / total
                item.sentiment = "bullish" if bullish_count > bearish_count else "bearish"
                item.sentiment_confidence = min(total * 0.2, 0.9)

            # 检测事件类型
            for event_type, keywords in EVENT_KEYWORDS.items():
                if any(kw.lower() in text for kw in keywords):
                    item.event_type = event_type
                    break

            # 检测交易品种
            symbols = self._extract_symbols(item.title)
            if symbols:
                item.affected_symbols = symbols

        return news

    def _extract_symbols(self, text: str) -> List[str]:
        """提取交易品种"""
        symbols = []
        text_upper = text.upper()

        crypto_map = {
            "BTC": ["BTC", "BITCOIN", "比特币"],
            "ETH": ["ETH", "ETHEREUM", "以太坊"],
            "SOL": ["SOL", "SOLANA"],
            "XRP": ["XRP", "RIPPLE"],
            "ADA": ["ADA", "CARDANO"],
            "DOGE": ["DOGE", "DOGECOIN", "狗狗币"],
            "BNB": ["BNB", "BINANCE"],
            "AVAX": ["AVAX", "AVALANCHE"],
        }

        for symbol, keywords in crypto_map.items():
            if any(kw.upper() in text_upper for kw in keywords):
                symbols.append(symbol)

        return symbols[:3]

    def _detect_black_swan(self, news: List[NewsItem]):
        """检测黑天鹅事件"""
        for item in news:
            detection = self.black_swan_detector.detect(item.title, item.content)
            item.black_swan_score = detection["black_swan_score"]
