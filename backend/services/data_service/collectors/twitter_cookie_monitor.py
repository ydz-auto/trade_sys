"""
Twitter Cookie Monitor - Cookie API 采集器

职责（业务逻辑）：
- Cookie 认证管理
- Twitter GraphQL API 调用
- 推文解析和标准化
- 账号时间线监控

架构：
- 主链路：Cookie API（轻量、快速、云服务器友好）
- Fallback：Playwright（稳定、重、需要 GUI）

运行时编排由 runtime/ingestion_runtime 负责
"""

import asyncio
import hashlib
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

import httpx

from shared.contracts import StandardEvent, Source, EventType, Sentiment
from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker,
    RetryPolicy,
    RetryConfig,
)

logger = get_logger("collectors.twitter_cookie")


class TwitterAuthMethod(Enum):
    """认证方式"""
    COOKIE = "cookie"
    BEARER_TOKEN = "bearer_token"
    PLAYWRIGHT = "playwright"


@dataclass
class TwitterCookieConfig:
    """Twitter Cookie 配置"""
    auth_token: str = ""
    ct0: str = ""
    bearer_token: str = ""
    
    poll_interval: int = 60
    max_accounts: int = 50
    max_tweets_per_poll: int = 20
    
    enable_playwright_fallback: bool = True
    playwright_headless: bool = True
    
    def __post_init__(self):
        self.auth_token = self.auth_token or os.getenv("TWITTER_AUTH_TOKEN", "")
        self.ct0 = self.ct0 or os.getenv("TWITTER_CT0", "")
        self.bearer_token = self.bearer_token or os.getenv("TWITTER_BEARER_TOKEN", "")
    
    @property
    def has_cookie_auth(self) -> bool:
        return bool(self.auth_token and self.ct0)
    
    @property
    def has_bearer_auth(self) -> bool:
        return bool(self.bearer_token)


@dataclass
class TwitterUser:
    """Twitter 用户"""
    id: str
    username: str
    display_name: str = ""
    followers_count: int = 0
    verified: bool = False


@dataclass
class TweetResult:
    """推文结果"""
    id: str
    text: str
    author: TwitterUser
    created_at: int
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    quotes: int = 0
    url: str = ""
    hashtags: List[str] = field(default_factory=list)
    cashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    is_retweet: bool = False
    is_quote: bool = False
    quoted_tweet_id: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)
    
    def to_standard_event(self) -> StandardEvent:
        """转换为标准事件"""
        symbols = list(set(self.cashtags))
        
        return StandardEvent(
            source=Source.TWITTER.value,
            event_type=EventType.TWEET.value,
            timestamp=self.created_at,
            title=f"@{self.author.username}: {self.text[:80]}...",
            content=self.text,
            sentiment=Sentiment.NEUTRAL.value,
            importance=self._calculate_importance(),
            symbols=symbols,
            tags=["twitter", "tweet"] + (["retweet"] if self.is_retweet else []),
            url=self.url,
            metadata={
                "tweet_id": self.id,
                "author_id": self.author.id,
                "author_username": self.author.username,
                "author_display_name": self.author.display_name,
                "author_verified": self.author.verified,
                "author_followers": self.author.followers_count,
                "likes": self.likes,
                "retweets": self.retweets,
                "replies": self.replies,
                "views": self.views,
                "quotes": self.quotes,
                "hashtags": self.hashtags,
                "mentions": self.mentions,
                "is_retweet": self.is_retweet,
                "is_quote": self.is_quote,
                "media_urls": self.media_urls,
            }
        )
    
    def _calculate_importance(self) -> float:
        """计算重要性"""
        base = 0.5
        
        if self.likes > 10000 or self.retweets > 2000:
            base = 0.8
        elif self.likes > 1000 or self.retweets > 200:
            base = 0.65
        
        if self.author.verified:
            base = min(base + 0.1, 0.95)
        
        if self.author.followers_count > 1000000:
            base = min(base + 0.1, 0.95)
        
        return min(base, 1.0)


class TwitterGraphQLClient:
    """Twitter GraphQL API 客户端
    
    使用 Cookie 认证访问 Twitter 内部 GraphQL API
    """
    
    GRAPHQL_ENDPOINTS = {
        "UserTweets": "https://twitter.com/i/api/graphql/HKOHbkE8pYVW7S7DI5qrWg/UserTweets",
        "UserByScreenName": "https://twitter.com/i/api/graphql/k5Xaiwc7QmCd6xT6bGkXIA/UserByScreenName",
        "TweetDetail": "https://twitter.com/i/api/graphql/0hWvDhmW8YQ-Sn3CmzC7jg/TweetResultByRestId",
        "HomeTimeline": "https://twitter.com/i/api/graphql/Hjt3dDwJLwGFlW9T4f1Ttw/HomeTimeline",
        "HomeLatestTimeline": "https://twitter.com/i/api/graphql/4GptXUf7p8Q9lZ3mW1xKqA/HomeLatestTimeline",
    }
    
    QUERY_IDS = {
        "UserTweets": "HKOHbkE8pYVW7S7DI5qrWg",
        "UserByScreenName": "k5Xaiwc7QmCd6xT6bGkXIA",
        "TweetDetail": "0hWvDhmW8YQ-Sn3CmzC7jg",
        "HomeTimeline": "Hjt3dDwJLwGFlW9T4f1Ttw",
        "HomeLatestTimeline": "4GptXUf7p8Q9lZ3mW1xKqA",
    }
    
    def __init__(self, config: TwitterCookieConfig):
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        
        self.circuit_breaker = get_circuit_breaker(
            "twitter_graphql",
            CircuitBreakerConfig(
                name="twitter_graphql",
                failure_threshold=5,
                recovery_timeout=120.0,
            )
        )
        
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=30.0,
        ))
        
        self._user_id_cache: Dict[str, str] = {}
        
        self.stats = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "rate_limited": 0,
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self.client is None:
            headers = self._build_headers()
            
            self.client = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
            )
        
        return self.client
    
    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://twitter.com",
            "Referer": "https://twitter.com/",
            "X-Twitter-Auth-Type": "OAuth2Session",
            "X-Twitter-Active-User": "yes",
            "X-Twitter-Client-Language": "en",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        
        if self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"
        
        if self.config.has_cookie_auth:
            headers["Cookie"] = f"auth_token={self.config.auth_token}; ct0={self.config.ct0}"
            headers["X-Csrf-Token"] = self.config.ct0
        
        return headers
    
    async def get_user_by_screen_name(self, username: str) -> Optional[TwitterUser]:
        """通过用户名获取用户信息"""
        if username in self._user_id_cache:
            cached_id = self._user_id_cache[username]
            return TwitterUser(
                id=cached_id,
                username=username,
            )
        
        client = await self._get_client()
        
        variables = {
            "screen_name": username,
            "withSafetyModeUserFields": True,
        }
        
        features = {
            "hidden_profile_likes_enabled": True,
            "hidden_profile_subscriptions_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        }
        
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features),
        }
        
        try:
            self.stats["requests"] += 1
            
            response = await self.circuit_breaker.execute(
                lambda: client.get(
                    self.GRAPHQL_ENDPOINTS["UserByScreenName"],
                    params=params,
                )
            )
            
            if response.status_code == 429:
                self.stats["rate_limited"] += 1
                logger.warning(f"Rate limited for @{username}")
                return None
            
            response.raise_for_status()
            
            data = response.json()
            user_data = data.get("data", {}).get("user", {}).get("result", {})
            
            if not user_data:
                return None
            
            legacy = user_data.get("legacy", {})
            
            user = TwitterUser(
                id=user_data.get("rest_id", ""),
                username=legacy.get("screen_name", username),
                display_name=legacy.get("name", ""),
                followers_count=legacy.get("followers_count", 0),
                verified=legacy.get("verified", False) or user_data.get("is_blue_verified", False),
            )
            
            self._user_id_cache[username] = user.id
            self.stats["successes"] += 1
            
            return user
            
        except Exception as e:
            self.stats["failures"] += 1
            logger.error(f"Failed to get user @{username}: {e}")
            return None
    
    async def get_user_tweets(
        self,
        user_id: str,
        username: str = "",
        count: int = 20,
    ) -> List[TweetResult]:
        """获取用户推文"""
        client = await self._get_client()
        
        variables = {
            "userId": user_id,
            "count": count,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": True,
            "withVoice": True,
            "withV2Timeline": True,
        }
        
        features = {
            "rweb_tipjar_consumption_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "rweb_video_timestamps_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        }
        
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features),
        }
        
        try:
            self.stats["requests"] += 1
            
            response = await self.circuit_breaker.execute(
                lambda: client.get(
                    self.GRAPHQL_ENDPOINTS["UserTweets"],
                    params=params,
                )
            )
            
            if response.status_code == 429:
                self.stats["rate_limited"] += 1
                logger.warning(f"Rate limited for user {user_id}")
                return []
            
            if response.status_code == 403:
                logger.error(f"Access forbidden for user {user_id} - cookies may be expired")
                return []
            
            response.raise_for_status()
            
            data = response.json()
            tweets = self._parse_timeline_response(data, username)
            
            self.stats["successes"] += 1
            
            return tweets
            
        except Exception as e:
            self.stats["failures"] += 1
            logger.error(f"Failed to get tweets for user {user_id}: {e}")
            return []
    
    def _parse_timeline_response(
        self,
        data: Dict,
        username: str = "",
    ) -> List[TweetResult]:
        """解析时间线响应"""
        tweets = []
        
        try:
            instructions = (
                data.get("data", {})
                .get("user", {})
                .get("result", {})
                .get("timeline_v2", {})
                .get("timeline", {})
                .get("instructions", [])
            )
            
            for instruction in instructions:
                if instruction.get("type") != "TimelineAddEntries":
                    continue
                
                entries = instruction.get("entries", [])
                
                for entry in entries:
                    entry_id = entry.get("entryId", "")
                    
                    if not entry_id.startswith("tweet-"):
                        continue
                    
                    tweet_content = (
                        entry.get("content", {})
                        .get("itemContent", {})
                        .get("tweet_results", {})
                        .get("result", {})
                    )
                    
                    if not tweet_content:
                        continue
                    
                    tweet = self._parse_tweet(tweet_content, username)
                    if tweet:
                        tweets.append(tweet)
        
        except Exception as e:
            logger.error(f"Failed to parse timeline: {e}")
        
        return tweets
    
    def _parse_tweet(
        self,
        tweet_data: Dict,
        username: str = "",
    ) -> Optional[TweetResult]:
        """解析单条推文"""
        try:
            legacy = tweet_data.get("legacy", {})
            
            tweet_id = tweet_data.get("rest_id", "") or legacy.get("id_str", "")
            if not tweet_id:
                return None
            
            text = legacy.get("full_text", "") or legacy.get("text", "")
            
            user_data = tweet_data.get("core", {}).get("user_results", {}).get("result", {})
            user_legacy = user_data.get("legacy", {})
            
            author = TwitterUser(
                id=user_data.get("rest_id", ""),
                username=user_legacy.get("screen_name", username),
                display_name=user_legacy.get("name", ""),
                followers_count=user_legacy.get("followers_count", 0),
                verified=user_legacy.get("verified", False) or user_data.get("is_blue_verified", False),
            )
            
            created_at_str = legacy.get("created_at", "")
            created_at = self._parse_twitter_date(created_at_str)
            
            metrics = legacy.get("public_metrics", {}) or {}
            
            hashtags = [h.get("text", "") for h in legacy.get("entities", {}).get("hashtags", [])]
            cashtags = [c.get("text", "") for c in legacy.get("entities", {}).get("symbols", [])]
            mentions = [m.get("screen_name", "") for m in legacy.get("entities", {}).get("user_mentions", [])]
            
            media_urls = []
            if "extended_entities" in legacy:
                for media in legacy["extended_entities"].get("media", []):
                    if media.get("type") == "photo":
                        media_urls.append(media.get("media_url_https", ""))
            
            is_retweet = "retweeted_status_result" in legacy
            is_quote = "quoted_status_result" in legacy
            
            quoted_tweet_id = None
            if is_quote:
                quoted_data = legacy.get("quoted_status_result", {}).get("result", {})
                quoted_tweet_id = quoted_data.get("rest_id", "")
            
            return TweetResult(
                id=tweet_id,
                text=text,
                author=author,
                created_at=created_at,
                likes=metrics.get("like_count", 0) or legacy.get("favorite_count", 0),
                retweets=metrics.get("retweet_count", 0) or legacy.get("retweet_count", 0),
                replies=metrics.get("reply_count", 0) or legacy.get("reply_count", 0),
                views=tweet_data.get("views", {}).get("count", 0) if isinstance(tweet_data.get("views"), dict) else 0,
                quotes=metrics.get("quote_count", 0) or legacy.get("quote_count", 0),
                url=f"https://twitter.com/{author.username}/status/{tweet_id}",
                hashtags=hashtags,
                cashtags=cashtags,
                mentions=mentions,
                is_retweet=is_retweet,
                is_quote=is_quote,
                quoted_tweet_id=quoted_tweet_id,
                media_urls=media_urls,
            )
            
        except Exception as e:
            logger.error(f"Failed to parse tweet: {e}")
            return None
    
    def _parse_twitter_date(self, date_str: str) -> int:
        """解析 Twitter 日期格式"""
        if not date_str:
            return int(datetime.now().timestamp())
        
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return int(dt.timestamp())
        except Exception:
            return int(datetime.now().timestamp())
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "user_cache_size": len(self._user_id_cache),
        }


class TwitterCookieMonitor:
    """Twitter Cookie 监控器
    
    业务逻辑：
    - 账号时间线监控
    - 新推文检测
    - 事件生成
    
    运行时编排由 runtime/ 负责
    """
    
    def __init__(self, config: TwitterCookieConfig = None):
        self.config = config or TwitterCookieConfig()
        self.graphql_client = TwitterGraphQLClient(self.config)
        
        self.accounts: Dict[str, TwitterUser] = {}
        self.last_tweet_ids: Dict[str, str] = {}
        self.seen_tweet_ids: Set[str] = set()
        self.max_seen = 10000
        
        self.callbacks: List[Callable] = []
        self.is_running = False
        
        self.stats = {
            "polls": 0,
            "tweets_found": 0,
            "new_tweets": 0,
            "errors": 0,
        }
    
    def add_account(self, username: str, priority: int = 1):
        """添加监控账号"""
        username = username.lstrip("@").lower()
        self.accounts[username] = TwitterUser(
            id="",
            username=username,
        )
        logger.info(f"Added Twitter account to monitor: @{username}")
    
    def remove_account(self, username: str):
        """移除监控账号"""
        username = username.lstrip("@").lower()
        if username in self.accounts:
            del self.accounts[username]
            if username in self.last_tweet_ids:
                del self.last_tweet_ids[username]
    
    def register_callback(self, callback: Callable):
        """注册回调"""
        self.callbacks.append(callback)
    
    async def initialize(self):
        """初始化 - 获取所有账号的 user_id"""
        if not self.config.has_cookie_auth:
            logger.warning("No cookie auth configured, Twitter Cookie Monitor will not work")
            return False
        
        logger.info(f"Initializing Twitter Cookie Monitor for {len(self.accounts)} accounts...")
        
        for username in list(self.accounts.keys()):
            user = await self.graphql_client.get_user_by_screen_name(username)
            if user:
                self.accounts[username] = user
                logger.info(f"Resolved @{username} -> user_id: {user.id}")
            else:
                logger.warning(f"Failed to resolve @{username}")
        
        return True
    
    async def poll(self) -> List[TweetResult]:
        """轮询所有账号"""
        if not self.config.has_cookie_auth:
            logger.warning("No cookie auth, skipping poll")
            return []
        
        self.stats["polls"] += 1
        all_new_tweets = []
        
        for username, user in self.accounts.items():
            if not user.id:
                continue
            
            try:
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                tweets = await self.graphql_client.get_user_tweets(
                    user.id,
                    username=username,
                    count=self.config.max_tweets_per_poll,
                )
                
                self.stats["tweets_found"] += len(tweets)
                
                for tweet in tweets:
                    if tweet.id in self.seen_tweet_ids:
                        continue
                    
                    self.seen_tweet_ids.add(tweet.id)
                    
                    last_id = self.last_tweet_ids.get(username)
                    if last_id and tweet.id > last_id:
                        all_new_tweets.append(tweet)
                        self.stats["new_tweets"] += 1
                
                if tweets:
                    self.last_tweet_ids[username] = max(t.id for t in tweets)
                
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error polling @{username}: {e}")
        
        if len(self.seen_tweet_ids) > self.max_seen:
            self.seen_tweet_ids = set(list(self.seen_tweet_ids)[-self.max_seen:])
        
        for tweet in all_new_tweets:
            await self._notify_callbacks(tweet)
        
        return all_new_tweets
    
    async def _notify_callbacks(self, tweet: TweetResult):
        """通知回调"""
        event = tweet.to_standard_event()
        
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    async def close(self):
        """关闭"""
        await self.graphql_client.close()
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "accounts": len(self.accounts),
            "seen_tweets": len(self.seen_tweet_ids),
            "graphql": self.graphql_client.get_stats(),
        }


_twitter_cookie_monitor: Optional[TwitterCookieMonitor] = None


def get_twitter_cookie_monitor(config: TwitterCookieConfig = None) -> TwitterCookieMonitor:
    """获取 Twitter Cookie Monitor 单例"""
    global _twitter_cookie_monitor
    if _twitter_cookie_monitor is None:
        _twitter_cookie_monitor = TwitterCookieMonitor(config)
    return _twitter_cookie_monitor
