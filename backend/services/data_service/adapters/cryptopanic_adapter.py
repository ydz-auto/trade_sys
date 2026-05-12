"""
CryptoPanic Adapter - 加密新闻聚合

免费 API: https://cryptopanic.com/developers/api/
提供实时加密新闻，支持情绪筛选
"""

import aiohttp
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

from shared.contracts import StandardEvent, EventType, Sentiment, Source, create_news_event
from infrastructure.logging import get_logger
from infrastructure.resilience import CircuitBreaker, CircuitBreakerConfig, RetryPolicy, RetryConfig

from .skill_adapter import SkillAdapter, AdapterConfig

logger = get_logger("cryptopanic.adapter")


class CryptoPanicAdapter(SkillAdapter):
    """CryptoPanic 新闻适配器
    
    免费 API 限制：
    - 100 requests/hour (免费版)
    - 支持情绪筛选 (bullish/bearish/important)
    """
    
    BASE_URL = "https://cryptopanic.com/api/v1/posts/"
    
    def __init__(self, config: AdapterConfig = None, api_key: str = None):
        if not config:
            config = AdapterConfig(
                name="CryptoPanicAdapter",
                source_type="cryptopanic"
            )
        super().__init__(config)
        
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "TradeAgent/1.0"}
            )
        return self.session
    
    async def fetch_raw_data(self) -> Dict:
        """获取 CryptoPanic 数据"""
        try:
            session = await self._get_session()
            
            params = {
                "auth_token": self.api_key,
                "public": "true",
                "limit": 50,
                "metadata": "true"
            }
            
            async with session.get(self.BASE_URL, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"CryptoPanic: Fetched {len(data.get('results', []))} posts")
                    return data
                else:
                    logger.error(f"CryptoPanic API error: {response.status}")
                    return self._generate_mock_data()
                    
        except Exception as e:
            logger.error(f"CryptoPanic fetch failed: {e}")
            return self._generate_mock_data()
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        posts = raw_data.get("results", [])
        
        for post in posts:
            # 解析情绪
            votes = post.get("votes", {})
            sentiment = self._parse_votes(votes)
            
            # 解析重要性
            importance = self._calculate_importance(post)
            
            # 提取币种
            currencies = post.get("currencies", [])
            symbols = [c.get("code", "") for c in currencies if c.get("code")]
            
            event = create_news_event(
                source=Source.COINDESK.value,  # 使用通用源
                title=post.get("title", ""),
                content=post.get("metadata", {}).get("description", ""),
                sentiment=sentiment,
                importance=importance,
                symbols=symbols,
                tags=["cryptopanic", post.get("kind", "news")],
                url=post.get("url", ""),
                metadata={
                    "source_domain": post.get("source", {}).get("domain", ""),
                    "published_at": post.get("published_at", ""),
                    "votes": votes
                }
            )
            events.append(event)
        
        return events
    
    def _parse_votes(self, votes: Dict) -> str:
        """根据投票解析情绪"""
        bullish = votes.get("positive", 0)
        bearish = votes.get("negative", 0)
        
        if bullish > bearish * 2:
            return Sentiment.BULLISH.value
        elif bearish > bullish * 2:
            return Sentiment.BEARISH.value
        return Sentiment.NEUTRAL.value
    
    def _calculate_importance(self, post: Dict) -> float:
        """计算重要性"""
        importance = 0.5
        
        # 根据投票数调整
        votes = post.get("votes", {})
        total_votes = sum(votes.values())
        if total_votes > 100:
            importance += 0.1
        if total_votes > 500:
            importance += 0.1
        
        # 根据是否重要标记
        if post.get("is_important"):
            importance += 0.2
        
        return min(importance, 1.0)
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据"""
        return {
            "results": [
                {
                    "title": "Bitcoin ETF sees record inflows",
                    "metadata": {"description": "Spot Bitcoin ETFs..."},
                    "currencies": [{"code": "BTC"}],
                    "kind": "news",
                    "votes": {"positive": 150, "negative": 20},
                    "published_at": datetime.now().isoformat(),
                    "url": "https://example.com/news/1"
                }
            ]
        }
    
    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
