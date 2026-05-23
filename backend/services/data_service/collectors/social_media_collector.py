"""
Social Media Collector - 社交媒体数据采集
支持：Twitter/X, Reddit, Telegram + 弹性能力
"""

import asyncio
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from infrastructure.config import get_datasource_config_manager
from infrastructure.llm.client import LLMServiceClient
from infrastructure.logging import get_logger
from .base_collector import BaseCollector, CollectorResult
from infrastructure.resilience import CircuitBreakerConfig, RetryConfig

logger = get_logger("collectors.social")


@dataclass
class SocialPost:
    """社交媒体帖子"""
    id: str
    platform: str
    author: str
    author_handle: str
    content: str
    url: str
    published: int
    timestamp: datetime = field(default_factory=datetime.now)
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    sentiment_confidence: float = 0.0
    mentioned_symbols: List[str] = field(default_factory=list)
    is_important: bool = False


class TwitterCollector:
    """Twitter/X 采集器"""

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.bearer_token = api_key
        self.llm_client = LLMServiceClient()

    async def collect_tweets(self, handles: List[str]) -> List[SocialPost]:
        posts = []

        for handle in handles:
            try:
                tweets = await self._fetch_user_tweets(handle)
                posts.extend(tweets)
            except Exception as e:
                logger.error(f"Error fetching tweets from {handle}: {e}")

        return posts

    async def _fetch_user_tweets(self, handle: str) -> List[SocialPost]:
        if not self.bearer_token:
            return self._get_mock_tweets(handle)

        try:
            import httpx

            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            user_id = await self._get_user_id(handle, headers)

            if not user_id:
                return []

            url = f"https://api.twitter.com/2/users/{user_id}/tweets"
            params = {"max_results": 10, "tweet.fields": "created_at,public_metrics"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_tweets(data, handle)
        except Exception as e:
            logger.warning(f"Twitter API error: {e}")

        return []

    async def _get_user_id(self, handle: str, headers: Dict) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.twitter.com/2/users/by/username/{handle.replace('@', '')}",
                    headers=headers
                )

                if response.status_code == 200:
                    return response.json().get("data", {}).get("id")
        except Exception:
            pass
        return None

    def _parse_tweets(self, data: Dict, handle: str) -> List[SocialPost]:
        posts = []
        tweets = data.get("data", [])

        for tweet in tweets:
            metrics = tweet.get("public_metrics", {})
            posts.append(SocialPost(
                id=tweet.get("id", ""),
                platform="twitter",
                author=handle,
                author_handle=handle,
                content=tweet.get("text", ""),
                url=f"https://twitter.com/{handle.replace('@', '')}/status/{tweet.get('id')}",
                published=int(datetime.now().timestamp()),
                likes=metrics.get("like_count", 0),
                retweets=metrics.get("retweet_count", 0),
                replies=metrics.get("reply_count", 0)
            ))

        return posts

    def _get_mock_tweets(self, handle: str) -> List[SocialPost]:
        mock_tweets = {
            "@cz_binance": [
                {"id": "1", "content": "BTC is looking strong. Accumulation phase continues.", "likes": 5000, "retweets": 1000},
                {"id": "2", "content": "Stay safe out there. DYOR before investing.", "likes": 3000, "retweets": 500}
            ],
            "@saylor": [
                {"id": "1", "content": "Bitcoin is the apex predator of digital assets.", "likes": 8000, "retweets": 2000}
            ]
        }

        tweets = mock_tweets.get(handle, [])
        return [
            SocialPost(
                id=t["id"],
                platform="twitter",
                author=handle,
                author_handle=handle,
                content=t["content"],
                url=f"https://twitter.com/{handle.replace('@', '')}/status/{t['id']}",
                published=int(time.time()),
                likes=t.get("likes", 0),
                retweets=t.get("retweets", 0)
            )
            for t in tweets
        ]


class RedditCollector:
    """Reddit 采集器"""

    SUBREDDITS = {
        "bitcoin": ["Bitcoin", "BTC", "cryptocurrency"],
        "ethereum": ["Ethereum", "ETH"],
        "satoshi": ["CryptoCurrency", " SatoshiStreetBets"]
    }

    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.llm_client = LLMServiceClient()

    async def collect_posts(self, subreddits: List[str] = None) -> List[SocialPost]:
        await self._get_access_token()

        if not self.access_token:
            return self._get_mock_posts()

        posts = []
        target_subreddits = subreddits or list(self.SUBREDDITS.keys())

        for subreddit in target_subreddits:
            try:
                posts.extend(await self._fetch_subreddit_posts(subreddit))
            except Exception as e:
                logger.error(f"Error fetching r/{subreddit}: {e}")

        return posts

    async def _get_access_token(self):
        if not self.client_id or not self.client_secret:
            return

        try:
            import base64
            async with httpx.AsyncClient(timeout=10.0) as client:
                auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
                response = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    headers={"Authorization": f"Basic {auth}"},
                    data={"grant_type": "client_credentials"}
                )

                if response.status_code == 200:
                    self.access_token = response.json().get("access_token")
        except Exception as e:
            logger.warning(f"Reddit auth error: {e}")

    async def _fetch_subreddit_posts(self, subreddit: str) -> List[SocialPost]:
        try:
            import httpx

            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"https://oauth.reddit.com/r/{subreddit}/hot"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params={"limit": 10})

                if response.status_code == 200:
                    return self._parse_reddit_posts(response.json(), subreddit)
        except Exception as e:
            logger.warning(f"Reddit fetch error: {e}")

        return []

    def _parse_reddit_posts(self, data: Dict, subreddit: str) -> List[SocialPost]:
        posts = []
        children = data.get("data", {}).get("children", [])

        for post in children:
            post_data = post.get("data", {})
            posts.append(SocialPost(
                id=post_data.get("id", ""),
                platform="reddit",
                author=post_data.get("author", ""),
                author_handle=f"r/{subreddit}",
                content=post_data.get("title", "") + " " + post_data.get("selftext", ""),
                url=f"https://reddit.com{post_data.get('permalink', '')}",
                published=int(post_data.get("created_utc", 0)),
                likes=post_data.get("score", 0),
                comments=post_data.get("num_comments", 0)
            ))

        return posts

    def _get_mock_posts(self) -> List[SocialPost]:
        return [
            SocialPost(
                id="mock1",
                platform="reddit",
                author="CryptoTrader",
                author_handle="r/Bitcoin",
                content="Bitcoin showing strong momentum. Bull flag pattern forming on daily.",
                url="https://reddit.com/r/Bitcoin/comments/mock",
                published=int(time.time()),
                likes=500,
                sentiment="bullish"
            )
        ]


class SocialMediaCollector(BaseCollector):
    """社交媒体收集器（多平台统一）+ 弹性能力"""

    def __init__(self):
        self.latest_posts: List[SocialPost] = []
        self.twitter_collector: Optional[TwitterCollector] = None
        self.reddit_collector: Optional[RedditCollector] = None
        self.llm_client = LLMServiceClient()
        
        # 调用基类初始化
        super().__init__(
            name="SocialMediaCollector",
            circuit_config=CircuitBreakerConfig(
                name="social_circuit",
                failure_threshold=3,
                recovery_timeout=60.0
            ),
            retry_config=RetryConfig(
                max_attempts=2,
                initial_delay=1.0
            ),
            fallback_value=[]  # 降级时返回空列表
        )
        
        self._init_collectors()

    def _init_collectors(self):
        twitter_handles = ["@cz_binance", "@saylor", "@PeterBrandt", "@CathieWood"]

        try:
            self.twitter_collector = TwitterCollector()
            self.twitter_handles = twitter_handles
        except Exception as e:
            logger.warning(f"Twitter collector init error: {e}")

        try:
            self.reddit_collector = RedditCollector()
        except Exception as e:
            logger.warning(f"Reddit collector init error: {e}")

    async def collect(self) -> CollectorResult:
        """采集社交媒体数据（返回 CollectorResult）"""
        try:
            all_posts = []

            if self.twitter_collector:
                try:
                    twitter_posts = await self.twitter_collector.collect_tweets(self.twitter_handles)
                    all_posts.extend(twitter_posts)
                except Exception as e:
                    logger.error(f"Twitter collection error: {e}")

            if self.reddit_collector:
                try:
                    reddit_posts = await self.reddit_collector.collect_posts()
                    all_posts.extend(reddit_posts)
                except Exception as e:
                    logger.error(f"Reddit collection error: {e}")

            analyzed = await self._analyze_sentiment(all_posts)
            self.latest_posts = sorted(analyzed, key=lambda x: x.published, reverse=True)[:100]

            return CollectorResult(
                success=True,
                data=self.latest_posts,
                source="SocialMediaCollector",
                confidence=0.8
            )
        except Exception as e:
            logger.error(f"Social media collection failed: {e}")
            return CollectorResult(
                success=False,
                error=str(e),
                source="SocialMediaCollector"
            )

    async def _analyze_sentiment(self, posts: List[SocialPost]) -> List[SocialPost]:
        for post in posts:
            try:
                result = await self.llm_client.sentiment_analysis(post.content)

                post.sentiment = result.get("sentiment", "neutral")
                post.sentiment_score = result.get("score", 0.0)
                post.sentiment_confidence = result.get("confidence", 0.5)
                post.is_important = abs(post.sentiment_score) > 0.5
            except Exception as e:
                logger.warning(f"Sentiment analysis error: {e}")

        return posts

    def get_posts_by_platform(self, platform: str) -> List[Dict]:
        return [self._to_dict(p) for p in self.latest_posts if p.platform == platform]

    def get_posts_by_sentiment(self, sentiment: str) -> List[Dict]:
        return [self._to_dict(p) for p in self.latest_posts if p.sentiment == sentiment]

    def get_important_posts(self) -> List[Dict]:
        return [self._to_dict(p) for p in self.latest_posts if p.is_important]

    def _to_dict(self, post: SocialPost) -> Dict:
        return {
            "id": post.id,
            "platform": post.platform,
            "author": post.author,
            "author_handle": post.author_handle,
            "content": post.content,
            "url": post.url,
            "published": post.published,
            "timestamp": post.timestamp.isoformat(),
            "likes": post.likes,
            "retweets": post.retweets,
            "replies": post.replies,
            "sentiment": post.sentiment,
            "sentiment_score": post.sentiment_score,
            "sentiment_confidence": post.sentiment_confidence,
            "mentioned_symbols": post.mentioned_symbols,
            "is_important": post.is_important
        }
