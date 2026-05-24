"""
Twitter/X Collector - Twitter/X 采集器
支持账号订阅、关键词监控、熔断和降级机制
"""
import asyncio
import hashlib
import os
import re
from typing import List, Dict, Optional, Set, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

import httpx

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig
from infrastructure.utilities.resilience.fallback import FallbackChain, create_default_chain

logger = get_logger("collectors.twitter")


class AlertPriority(Enum):
    """告警优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TwitterAccount:
    """Twitter 账号配置"""
    username: str
    display_name: str = ""
    enabled: bool = True
    priority: int = 1
    keywords: List[str] = field(default_factory=list)
    alert_priority: AlertPriority = AlertPriority.MEDIUM
    user_id: Optional[str] = None


@dataclass
class TwitterPost:
    """Twitter 帖子"""
    id: str
    text: str
    url: str
    author_username: str
    author_display_name: str
    created_at: int
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quoted: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    mentioned_usernames: List[str] = field(default_factory=list)


@dataclass
class AlertRule:
    """告警规则"""
    id: str
    name: str
    keywords: List[str]
    exclude_keywords: List[str] = field(default_factory=list)
    priority: AlertPriority = AlertPriority.MEDIUM
    enabled: bool = True


class TwitterCollector:
    """Twitter/X 采集器"""
    
    def __init__(self, bearer_token: Optional[str] = None):
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")
        self.base_url = "https://api.twitter.com/2"
        self.accounts: Dict[str, TwitterAccount] = {}
        self.alert_rules: Dict[str, AlertRule] = {}
        self.seen_posts: Set[str] = set()
        self.max_seen_posts = 5000
        self.callbacks: List[Callable] = []
        
        self.circuit_breaker = get_circuit_breaker(
            "twitter",
            CircuitBreakerConfig(
                name="twitter",
                failure_threshold=5,
                recovery_timeout=120.0
            )
        )
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=10.0
        ))
        
        self._init_default_accounts()
    
    def _init_default_accounts(self):
        """初始化默认账号"""
        default_accounts = [
            {"username": "elonmusk", "display_name": "Elon Musk", "priority": 1},
            {"username": "cz_binance", "display_name": "CZ 币安", "priority": 1},
            {"username": "Cointelegraph", "display_name": "Cointelegraph", "priority": 2},
            {"username": "coindesk", "display_name": "CoinDesk", "priority": 2},
            {"username": "TheBlock__", "display_name": "The Block", "priority": 2},
            {"username": "BitcoinMagazine", "display_name": "Bitcoin Magazine", "priority": 2},
            {"username": "VitalikButerin", "display_name": "Vitalik Buterin", "priority": 1},
            {"username": "SBF_FTX", "display_name": "SBF", "priority": 2},
            {"username": "justinsuntron", "display_name": "Justin Sun", "priority": 2},
        ]
        
        for acc in default_accounts:
            self.add_account(
                username=acc["username"],
                display_name=acc["display_name"],
                priority=acc["priority"]
            )
        
        self.add_alert_rule(
            id="critical_keywords",
            name="Critical Keywords",
            keywords=[
                "SEC", "regulation", "ban", "hack", "exploit",
                "crash", "collapsed", "bankruptcy", "liquidation"
            ],
            priority=AlertPriority.CRITICAL
        )
        
        self.add_alert_rule(
            id="market_impact",
            name="Market Impact",
            keywords=[
                "Bitcoin", "BTC", "Ethereum", "ETH", "ETF", "adoption",
                "institutional", "BlackRock", "Fidelity"
            ],
            priority=AlertPriority.HIGH
        )
    
    def add_account(
        self,
        username: str,
        display_name: str = "",
        enabled: bool = True,
        priority: int = 1,
        keywords: List[str] = None
    ):
        """添加账号"""
        username = username.lstrip("@").lower()
        self.accounts[username] = TwitterAccount(
            username=username,
            display_name=display_name or username,
            enabled=enabled,
            priority=priority,
            keywords=keywords or []
        )
        logger.info(f"Added Twitter account: @{username}")
    
    def remove_account(self, username: str):
        """移除账号"""
        username = username.lstrip("@").lower()
        if username in self.accounts:
            del self.accounts[username]
            logger.info(f"Removed Twitter account: @{username}")
    
    def add_alert_rule(
        self,
        id: str,
        name: str,
        keywords: List[str],
        exclude_keywords: List[str] = None,
        priority: AlertPriority = AlertPriority.MEDIUM
    ):
        """添加告警规则"""
        self.alert_rules[id] = AlertRule(
            id=id,
            name=name,
            keywords=[k.lower() for k in keywords],
            exclude_keywords=[k.lower() for k in (exclude_keywords or [])],
            priority=priority
        )
        logger.info(f"Added alert rule: {name}")
    
    def remove_alert_rule(self, id: str):
        """移除告警规则"""
        if id in self.alert_rules:
            del self.alert_rules[id]
            logger.info(f"Removed alert rule: {id}")
    
    def register_callback(self, callback: Callable):
        """注册回调"""
        self.callbacks.append(callback)
    
    async def fetch_account_timeline(
        self,
        username: str,
        max_results: int = 20
    ) -> List[TwitterPost]:
        """获取账号时间线"""
        if not self.bearer_token:
            return await self._fallback_scrape(username, max_results)
        
        async def _fetch():
            return await self._fetch_timeline_api(username, max_results)
        
        fallback_chain = create_default_chain(
            primary_name=f"twitter_{username}",
            static_value=[]
        )
        
        try:
            result = await self.circuit_breaker.execute(
                lambda: self.retry_policy.execute(_fetch)
            )
            return result
        except Exception as e:
            logger.warning(f"API failed for @{username}, trying fallback: {e}")
            return await fallback_chain.execute(lambda: self._fallback_scrape(username, max_results))
    
    async def _fetch_timeline_api(
        self,
        username: str,
        max_results: int
    ) -> List[TwitterPost]:
        """通过 API 获取时间线"""
        posts = []
        
        user_id = await self._get_user_id(username)
        if not user_id:
            return []
        
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,referenced_tweets,entities",
            "expansions": "author_id"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}/tweets",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            for tweet in data.get("data", []):
                post = self._parse_tweet(tweet, username)
                if post:
                    posts.append(post)
        
        logger.info(f"Fetched {len(posts)} posts from @{username}")
        return posts
    
    async def _get_user_id(self, username: str) -> Optional[str]:
        """获取用户 ID"""
        account = self.accounts.get(username)
        if account and account.user_id:
            return account.user_id
        
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/users/by/username/{username}",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            user_id = data.get("data", {}).get("id")
            
            if account and user_id:
                account.user_id = user_id
            
            return user_id
    
    def _parse_tweet(self, tweet: Dict, username: str) -> Optional[TwitterPost]:
        """解析推文"""
        try:
            tweet_id = tweet.get("id", "")
            if tweet_id in self.seen_posts:
                return None
            
            text = tweet.get("text", "")
            created_at = self._parse_date(tweet.get("created_at", ""))
            
            metrics = tweet.get("public_metrics", {})
            
            hashtags = []
            if entities := tweet.get("entities", {}):
                for tag in entities.get("hashtags", []):
                    if tag_text := tag.get("tag"):
                        hashtags.append(tag_text)
            
            mentions = []
            if entities := tweet.get("entities", {}):
                for mention in entities.get("mentions", []):
                    if username := mention.get("username"):
                        mentions.append(username)
            
            post = TwitterPost(
                id=tweet_id,
                text=text,
                url=f"https://twitter.com/{username}/status/{tweet_id}",
                author_username=username,
                author_display_name=self.accounts.get(username, TwitterAccount(username=username, display_name=username)).display_name,
                created_at=created_at,
                likes=metrics.get("like_count", 0),
                retweets=metrics.get("retweet_count", 0),
                replies=metrics.get("reply_count", 0),
                hashtags=hashtags,
                mentioned_usernames=mentions
            )
            
            self._mark_seen(tweet_id)
            return post
        except Exception as e:
            logger.warning(f"Failed to parse tweet: {e}")
            return None
    
    async def _fallback_scrape(
        self,
        username: str,
        max_results: int
    ) -> List[TwitterPost]:
        """备选抓取方式"""
        posts = []
        
        try:
            from bs4 import BeautifulSoup
            
            url = f"https://twitter.com/{username}"
            
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            ) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    tweet_elems = soup.select('article[data-testid="tweet"]')
                    
                    for i, elem in enumerate(tweet_elems[:max_results]):
                        post = self._parse_scraped_tweet(elem, username)
                        if post:
                            posts.append(post)
        except ImportError:
            logger.warning("BeautifulSoup not available for scraping")
        except Exception as e:
            logger.warning(f"Scraping failed for @{username}: {e}")
        
        return posts
    
    def _parse_scraped_tweet(self, elem, username: str) -> Optional[TwitterPost]:
        """解析抓取的推文"""
        try:
            text_elem = elem.select_one('[data-testid="tweetText"]')
            if not text_elem:
                return None
            
            text = text_elem.get_text(strip=True)
            post_id = hashlib.md5(text.encode()).hexdigest()[:16]
            
            if post_id in self.seen_posts:
                return None
            
            self._mark_seen(post_id)
            
            return TwitterPost(
                id=post_id,
                text=text,
                url=f"https://twitter.com/{username}",
                author_username=username,
                author_display_name=self.accounts.get(username, TwitterAccount(username=username, display_name=username)).display_name,
                created_at=int(datetime.now().timestamp())
            )
        except Exception:
            return None
    
    def _mark_seen(self, post_id: str):
        """标记为已见"""
        self.seen_posts.add(post_id)
        if len(self.seen_posts) > self.max_seen_posts:
            self.seen_posts = set(list(self.seen_posts)[-self.max_seen_posts:])
    
    def _parse_date(self, date_str: str) -> int:
        """解析日期"""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except Exception:
            return int(datetime.now().timestamp())
    
    async def collect_all(self) -> List[TwitterPost]:
        """采集所有账号"""
        all_posts = []
        tasks = []
        
        sorted_accounts = sorted(
            [a for a in self.accounts.values() if a.enabled],
            key=lambda a: a.priority
        )
        
        for account in sorted_accounts:
            tasks.append(self.fetch_account_timeline(account.username, 15))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for posts in results:
            if isinstance(posts, list):
                all_posts.extend(posts)
        
        all_posts = sorted(all_posts, key=lambda p: p.created_at, reverse=True)
        
        for post in all_posts:
            self._check_alerts(post)
        
        logger.info(f"Collected {len(all_posts)} posts from {len(sorted_accounts)} accounts")
        return all_posts
    
    def _check_alerts(self, post: TwitterPost):
        """检查告警"""
        text = post.text.lower()
        
        matched_rules = []
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue
            
            has_keyword = any(k in text for k in rule.keywords)
            has_exclude = any(k in text for k in rule.exclude_keywords)
            
            if has_keyword and not has_exclude:
                matched_rules.append(rule)
        
        if matched_rules:
            highest_priority = max(matched_rules, key=lambda r: r.priority.value)
            self._trigger_alert(post, highest_priority)
    
    def _trigger_alert(self, post: TwitterPost, rule: AlertRule):
        """触发告警"""
        logger.warning(f"ALERT [{rule.priority.value}] @{post.author_username}: {post.text[:100]}")
        
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(post, rule))
                else:
                    callback(post, rule)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_monitoring_status(self) -> Dict:
        """获取监控状态"""
        return {
            "accounts": [
                {
                    "username": a.username,
                    "display_name": a.display_name,
                    "enabled": a.enabled,
                    "priority": a.priority
                }
                for a in self.accounts.values()
            ],
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "keywords": r.keywords,
                    "priority": r.priority.value,
                    "enabled": r.enabled
                }
                for r in self.alert_rules.values()
            ],
            "circuit": self.circuit_breaker.get_stats(),
            "seen_posts": len(self.seen_posts)
        }
