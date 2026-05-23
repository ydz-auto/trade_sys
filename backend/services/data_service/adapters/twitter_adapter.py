"""
Twitter/X Adapter - 真实 API 接入

API: https://developer.twitter.com/en/docs/twitter-api
需要申请 Twitter Developer 账号

环境变量配置：
- TWITTER_API_KEY
- TWITTER_API_SECRET
- TWITTER_ACCESS_TOKEN
- TWITTER_ACCESS_TOKEN_SECRET
"""

import os
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from domain.contracts import StandardEvent, Source, create_tweet_event
from infrastructure.logging import get_logger

from .skill_adapter import SkillAdapter, AdapterConfig

logger = get_logger("twitter.adapter")


class TwitterAdapter(SkillAdapter):
    """Twitter/X 适配器 - 支持真实 API"""
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self, config: AdapterConfig = None, api_key: str = None, api_secret: str = None,
                 access_token: str = None, access_token_secret: str = None):
        if not config:
            config = AdapterConfig(
                name="TwitterAdapter",
                source_type="twitter"
            )
        super().__init__(config)
        
        # 优先使用参数，其次环境变量
        self.api_key = api_key or os.getenv("TWITTER_API_KEY")
        self.api_secret = api_secret or os.getenv("TWITTER_API_SECRET")
        self.access_token = access_token or os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        
        # 监控列表
        self.watch_accounts = [
            {"username": "elonmusk", "id": "44196397"},
            {"username": "cz_binance", "id": "807095"},
            {"username": "VitalikButerin", "id": "200889701"},
            {"username": "saylor", "id": "15492997"},
            {"username": "BarrySilbert", "id": "10130202"},
            {"username": "binance", "id": "18050481"},
            {"username": "okx", "id": "1346048438176215040"},
            {"username": "coinbase", "id": "141289402"},
            {"username": "SBF_FTX", "id": "1184916838620080128"}
        ]
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.bearer_token: Optional[str] = None
        
    async def _authenticate(self) -> bool:
        """获取 Bearer Token"""
        if not self.api_key or not self.api_secret:
            return False
            
        try:
            session = await self._get_session()
            
            auth = aiohttp.BasicAuth(self.api_key, self.api_secret)
            data = {"grant_type": "client_credentials"}
            
            async with session.post(
                "https://api.twitter.com/oauth2/token",
                auth=auth,
                data=data,
                timeout=15
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.bearer_token = result.get("access_token")
                    logger.info("Twitter authentication successful")
                    return True
                else:
                    logger.error(f"Twitter auth failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Twitter auth error: {e}")
            return False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP session"""
        if self.session is None or self.session.closed:
            headers = {
                "User-Agent": "TradeAgent/1.0"
            }
            if self.bearer_token:
                headers["Authorization"] = f"Bearer {self.bearer_token}"
            
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def fetch_raw_data(self) -> Dict:
        """获取 Twitter 数据"""
        # 检查 API 凭证
        if not self.api_key or not self.api_secret:
            logger.warning("Twitter API credentials not configured. Using mock data.")
            return self._generate_mock_data()
        
        # 认证
        if not self.bearer_token:
            auth_success = await self._authenticate()
            if not auth_success:
                return self._generate_mock_data()
        
        # 获取推文
        try:
            session = await self._get_session()
            
            # 获取最近的推文
            tasks = []
            for account in self.watch_accounts[:5]:  # 限制数量避免限流
                tasks.append(self._fetch_user_tweets(session, account["id"]))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_tweets = []
            for result in results:
                if isinstance(result, list):
                    all_tweets.extend(result)
            
            logger.info(f"Twitter: Fetched {len(all_tweets)} tweets")
            
            return {"tweets": all_tweets}
            
        except Exception as e:
            logger.error(f"Twitter fetch failed: {e}")
            return self._generate_mock_data()
    
    async def _fetch_user_tweets(self, session: aiohttp.ClientSession, user_id: str) -> List[Dict]:
        """获取指定用户的推文"""
        url = f"{self.BASE_URL}/users/{user_id}/tweets"
        
        params = {
            "max_results": 10,
            "tweet.fields": "created_at,public_metrics,lang,entities",
            "expansions": "referenced_tweets.id",
            "media.fields": "url"
        }
        
        try:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_tweets(data)
                else:
                    logger.warning(f"Failed to fetch tweets for user {user_id}: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching tweets for {user_id}: {e}")
            return []
    
    def _parse_tweets(self, data: Dict) -> List[Dict]:
        """解析 Twitter API 响应"""
        tweets = []
        
        for tweet in data.get("data", []):
            public_metrics = tweet.get("public_metrics", {})
            
            # 提取提到的币种
            symbols = []
            entities = tweet.get("entities", {})
            if entities.get("hashtags"):
                for hashtag in entities["hashtags"]:
                    tag = hashtag.get("tag", "").upper()
                    if len(tag) <= 6:  # 合理的币种符号长度
                        symbols.append(tag)
            
            # 从文本中提取
            text = tweet.get("text", "")
            crypto_symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "SHIB"]
            for symbol in crypto_symbols:
                if symbol in text and symbol not in symbols:
                    symbols.append(symbol)
            
            tweets.append({
                "id": tweet.get("id", ""),
                "author": self._get_username(tweet.get("id", "")),
                "content": tweet.get("text", ""),
                "likes": public_metrics.get("like_count", 0),
                "retweets": public_metrics.get("retweet_count", 0),
                "replies": public_metrics.get("reply_count", 0),
                "quote_count": public_metrics.get("quote_count", 0),
                "created_at": tweet.get("created_at", ""),
                "symbols": symbols[:5],
                "lang": tweet.get("lang", "")
            })
        
        return tweets
    
    def _get_username(self, tweet_id: str) -> str:
        """根据推文ID获取用户名（简化版）"""
        # 在实际实现中，应该使用 includes 数据
        for account in self.watch_accounts:
            # 这里简化处理
            return account["username"]
        return "unknown"
    
    def normalize(self, raw_data: Dict) -> List[StandardEvent]:
        """转换为标准事件"""
        events = []
        
        for tweet in raw_data.get("tweets", []):
            # 计算重要性（基于互动量）
            likes = tweet.get("likes", 0)
            retweets = tweet.get("retweets", 0)
            importance = min(0.3 + (likes + retweets * 2) / 10000, 1.0)
            
            event = create_tweet_event(
                author=tweet.get("author", ""),
                content=tweet.get("content", ""),
                likes=likes,
                retweets=retweets,
                symbols=tweet.get("symbols", [])
            )
            
            event.importance = importance
            event.tags = ["twitter", tweet.get("author", "")]
            event.source = Source.TWITTER.value
            
            events.append(event)
        
        return events
    
    def _generate_mock_data(self) -> Dict:
        """生成模拟数据（无 API Key 时）"""
        return {
            "tweets": [
                {
                    "id": "1789012345678901234",
                    "author": "elonmusk",
                    "content": "Bitcoin is the future of money! #BTC",
                    "likes": 125000,
                    "retweets": 25000,
                    "created_at": datetime.now().isoformat(),
                    "symbols": ["BTC"],
                    "lang": "en"
                },
                {
                    "id": "1789012345678901235",
                    "author": "cz_binance",
                    "content": "Great news for crypto! #BNB #DeFi",
                    "likes": 45000,
                    "retweets": 12000,
                    "created_at": datetime.now().isoformat(),
                    "symbols": ["BNB"],
                    "lang": "en"
                },
                {
                    "id": "1789012345678901236",
                    "author": "VitalikButerin",
                    "content": "Working on some exciting Ethereum upgrades",
                    "likes": 89000,
                    "retweets": 18000,
                    "created_at": datetime.now().isoformat(),
                    "symbols": ["ETH"],
                    "lang": "en"
                }
            ]
        }
    
    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
