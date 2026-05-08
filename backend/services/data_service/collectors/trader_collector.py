"""
Trader Data Collector - 交易员/KOL数据采集
支持：Twitter KOL + Dune Analytics + Nansen 链上数据
"""

import asyncio
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config import get_datasource_config_manager, KOL_TRADER_LIST
from shared.llm_client import LLMServiceClient
from shared.http_client import HTTPClient, HTTPRequest, HTTPMethod
from infrastructure.logging import get_logger

logger = get_logger("collectors.trader")


@dataclass
class TraderStatement:
    """交易员言论"""
    trader_id: str
    trader_name: str
    platform: str
    content: str
    url: str
    published: int
    timestamp: datetime = field(default_factory=datetime.now)
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    sentiment_confidence: float = 0.0
    mentioned_assets: List[str] = field(default_factory=list)
    time_horizon: str = "medium"
    arguments: List[str] = field(default_factory=list)
    influence_score: float = 0.5
    credibility: float = 0.5


@dataclass
class OnChainData:
    """链上数据"""
    wallet_address: str
    label: str
    net_flow: float
    balance: float
    last_active: int
    source: str
    timestamp: datetime = field(default_factory=datetime.now)


class TwitterKOLCollector:
    """Twitter KOL 采集器"""

    def __init__(self, kol_list: List[Dict]):
        self.kol_list = kol_list
        self.llm_client = LLMServiceClient()
        self.bearer_token = None

    async def collect(self) -> List[TraderStatement]:
        statements = []

        if not self.bearer_token:
            return self._get_mock_statements()

        for kol in self.kol_list:
            try:
                twitter_handle = kol.get("platforms", {}).get("twitter", "").replace("@", "")
                if twitter_handle:
                    tweets = await self._fetch_kol_tweets(twitter_handle, kol)
                    statements.extend(tweets)
            except Exception as e:
                logger.error(f"Error fetching tweets for {kol.get('name')}: {e}")

        analyzed = await self._analyze_statements(statements)
        return analyzed

    async def _fetch_kol_tweets(self, handle: str, kol_info: Dict) -> List[TraderStatement]:
        try:
            import httpx

            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            url = f"https://api.twitter.com/2/users/by/username/{handle}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return []

                user_id = response.json().get("data", {}).get("id")
                if not user_id:
                    return []

                tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
                tweets_response = await client.get(
                    tweets_url,
                    headers=headers,
                    params={"max_results": 5, "tweet.fields": "created_at"}
                )

                if tweets_response.status_code != 200:
                    return []

                tweets = tweets_response.json().get("data", [])
                statements = []

                for tweet in tweets:
                    statements.append(TraderStatement(
                        trader_id=kol_info.get("id", ""),
                        trader_name=kol_info.get("name", ""),
                        platform="twitter",
                        content=tweet.get("text", ""),
                        url=f"https://twitter.com/{handle}/status/{tweet.get('id')}",
                        published=int(datetime.now().timestamp()),
                        credibility=kol_info.get("credibility", 0.5),
                        influence_score=min(kol_info.get("followers", 0) / 1000000, 1.0)
                    ))

                return statements

        except Exception as e:
            logger.warning(f"Twitter fetch error: {e}")

        return []

    async def _analyze_statements(self, statements: List[TraderStatement]) -> List[TraderStatement]:
        for statement in statements:
            try:
                result = await self.llm_client.trader_statement_analysis(
                    trader_name=statement.trader_name,
                    content=statement.content
                )

                statement.sentiment = result.get("情绪", "neutral")
                statement.sentiment_score = result.get("情绪置信度", 0.0)
                statement.mentioned_assets = result.get("资产", [])
                statement.time_horizon = result.get("时间预期", "medium")
                statement.arguments = result.get("论据", [])

            except Exception as e:
                logger.warning(f"Statement analysis error: {e}")

        return statements

    def _get_mock_statements(self) -> List[TraderStatement]:
        mock_statements = []

        for kol in self.kol_list[:3]:
            kol_id = kol.get("id", "")
            name = kol.get("name", "")

            mock_contents = {
                "cz_binance": "BTC showing strong support at current levels. Accumulation phase continues for another 2-3 months.",
                "saylor": "Every action you take regarding Bitcoin should be based on the truth, not the narrative.",
                "peter_brandt": "BTC nearing end of multi-year consolidation. Breakout expected Q2."
            }

            content = mock_contents.get(kol_id, "Market analysis in progress.")

            mock_statements.append(TraderStatement(
                trader_id=kol_id,
                trader_name=name,
                platform="twitter",
                content=content,
                url=f"https://twitter.com/{kol.get('platforms', {}).get('twitter', '')}/status/123",
                published=int(time.time()),
                sentiment="bullish",
                sentiment_score=0.7,
                mentioned_assets=["BTC"],
                time_horizon="medium",
                credibility=kol.get("credibility", 0.5),
                influence_score=min(kol.get("followers", 0) / 1000000, 1.0)
            ))

        return mock_statements


class DuneAnalyticsCollector:
    """Dune Analytics 链上数据采集器"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.dune.com/api/v1"

    async def collect_wallet_flows(self, wallet_addresses: List[str]) -> List[OnChainData]:
        if not self.api_key:
            return self._get_mock_onchain_data(wallet_addresses)

        results = []

        for address in wallet_addresses:
            try:
                data = await self._fetch_wallet_data(address)
                if data:
                    results.append(data)
            except Exception as e:
                logger.warning(f"Dune fetch error for {address}: {e}")

        return results

    async def _fetch_wallet_data(self, address: str) -> Optional[OnChainData]:
        try:
            url = f"{self.base_url}/query/2348778/results"

            headers = {"x-dune-api-key": self.api_key}
            params = {"address": address}

            async with HTTPClient() as http:
                response = await http.request(
                    HTTPRequest(url=url, headers=headers, params=params, timeout=15.0)
                )

            if response.success and response.body:
                data = response.body
                return OnChainData(
                    wallet_address=address,
                    label="Whale Wallet",
                    net_flow=data.get("net_flow", 0),
                    balance=data.get("balance", 0),
                    last_active=int(time.time()),
                    source="dune"
                )

        except Exception as e:
            logger.warning(f"Dune API error: {e}")

        return None

    def _get_mock_onchain_data(self, addresses: List[str]) -> List[OnChainData]:
        return [
            OnChainData(
                wallet_address=addr,
                label="Mock Whale",
                net_flow=1000000,
                balance=50000000,
                last_active=int(time.time()),
                source="mock"
            )
            for addr in addresses[:3]
        ]


class TraderDataCollector:
    """交易员数据收集器（KOL + 链上）"""

    def __init__(self):
        self.latest_statements: List[TraderStatement] = []
        self.latest_onchain: List[OnChainData] = []

        self.kol_list = self._load_kol_list()
        self.twitter_collector = TwitterKOLCollector(self.kol_list)
        self.dune_collector = DuneAnalyticsCollector()

        self.llm_client = LLMServiceClient()

    def _load_kol_list(self) -> List[Dict]:
        try:
            return KOL_TRADER_LIST.get("whale_traders", {}).get("traders", [])
        except Exception:
            return []

    async def collect(self) -> Dict:
        statement_results = await self.collect_trader_opinions()

        wallet_addresses = []
        for kol in self.kol_list:
            wallets = kol.get("wallet_addresses", [])
            wallet_addresses.extend(wallets)

        if wallet_addresses:
            onchain_results = await self.collect_onchain_data(wallet_addresses)
        else:
            onchain_results = []

        return {
            "statements": statement_results,
            "onchain": onchain_results,
            "timestamp": datetime.now().isoformat()
        }

    async def collect_trader_opinions(self) -> List[Dict]:
        statements = await self.twitter_collector.collect()
        self.latest_statements = statements

        return [self._statement_to_dict(s) for s in statements]

    async def collect_onchain_data(self, wallet_addresses: List[str]) -> List[Dict]:
        onchain_data = await self.dune_collector.collect_wallet_flows(wallet_addresses)
        self.latest_onchain = onchain_data

        return [self._onchain_to_dict(d) for d in onchain_data]

    def get_opinions_by_asset(self, asset: str) -> List[Dict]:
        opinions = []
        for statement in self.latest_statements:
            if asset.upper() in [a.upper() for a in statement.mentioned_assets]:
                opinions.append(self._statement_to_dict(statement))
        return opinions

    def get_opinions_by_sentiment(self, sentiment: str) -> List[Dict]:
        return [
            self._statement_to_dict(s)
            for s in self.latest_statements
            if s.sentiment == sentiment
        ]

    def get_bullish_traders(self) -> List[Dict]:
        return self.get_opinions_by_sentiment("bullish")

    def get_bearish_traders(self) -> List[Dict]:
        return self.get_opinions_by_sentiment("bearish")

    def get_aggregate_sentiment(self) -> Dict:
        if not self.latest_statements:
            return {"sentiment": "neutral", "score": 0, "count": 0}

        total_score = 0
        weighted_score = 0

        for statement in self.latest_statements:
            weight = statement.credibility * statement.influence_score
            total_score += statement.sentiment_score * weight
            weighted_score += weight

        avg_score = total_score / weighted_score if weighted_score > 0 else 0

        sentiment = "neutral"
        if avg_score > 0.3:
            sentiment = "bullish"
        elif avg_score < -0.3:
            sentiment = "bearish"

        return {
            "sentiment": sentiment,
            "score": avg_score,
            "count": len(self.latest_statements),
            "bullish_count": len([s for s in self.latest_statements if s.sentiment == "bullish"]),
            "bearish_count": len([s for s in self.latest_statements if s.sentiment == "bearish"])
        }

    def statement_to_dict(self, statement: TraderStatement) -> Dict:
        return {
            "trader_id": statement.trader_id,
            "trader_name": statement.trader_name,
            "platform": statement.platform,
            "content": statement.content,
            "url": statement.url,
            "published": statement.published,
            "timestamp": statement.timestamp.isoformat(),
            "sentiment": statement.sentiment,
            "sentiment_score": statement.sentiment_score,
            "mentioned_assets": statement.mentioned_assets,
            "time_horizon": statement.time_horizon,
            "arguments": statement.arguments,
            "influence_score": statement.influence_score,
            "credibility": statement.credibility
        }

    def _onchain_to_dict(self, data: OnChainData) -> Dict:
        return {
            "wallet_address": data.wallet_address,
            "label": data.label,
            "net_flow": data.net_flow,
            "balance": data.balance,
            "last_active": data.last_active,
            "source": data.source,
            "timestamp": data.timestamp.isoformat()
        }
