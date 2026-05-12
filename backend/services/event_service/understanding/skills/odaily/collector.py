"""
Odaily Skill Collector - 加密情报采集器（世界解释器）
模拟 Odaily Skill 的结构化情报输出

⚠️ 重要：这是 event_service/understanding 层的一部分
不是数据采集层，而是世界理解层

模块：
1. 今日必关注（M1）
2. 加密市场分析（M2）
3. 明日关键事件（M3）
4. 巨鲸/预测市场异动（M4）
5. API 原始数据（M5）

作为 "World Interpreter"：
✅ 非常适合：
- 新闻摘要
- 市场事件抽取
- Sentiment 分析
- Narrative 识别
- 热点检测
- 事件标签
- Entity extraction

⚠️ 慎用：
- 直接交易信号（hallucination）
- 仓位管理（不稳定）
- Execution（风险极高）
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)

logger = get_logger("event_service.understanding.odaily")


class EventImportance(Enum):
    """事件重要性"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MarketRegime(Enum):
    """市场状态"""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class CryptoEvent:
    """加密事件"""
    id: str
    title: str
    description: str
    importance: EventImportance
    affected_symbols: List[str]
    sentiment: str
    source: str
    timestamp: int
    url: Optional[str] = None


@dataclass
class WhaleActivity:
    """巨鲸活动"""
    wallet_address: str
    activity_type: str
    symbol: str
    amount: float
    value_usd: float
    exchange: Optional[str] = None
    timestamp: int = 0


@dataclass
class PredictionMarket:
    """预测市场"""
    question: str
    market_url: str
    yes_probability: float
    volume_24h: float
    category: str
    timestamp: int


@dataclass
class MarketAnalysis:
    """市场分析"""
    regime: MarketRegime
    btc_trend: str
    eth_trend: str
    altcoin_trend: str
    fear_greed_index: int
    dominant_narrative: str
    key_levels: Dict[str, Dict]
    timestamp: int


@dataclass
class TomorrowEvent:
    """明日关键事件"""
    event_name: str
    event_time: str
    timezone: str
    importance: EventImportance
    expected_impact: str
    symbols_affected: List[str]


@dataclass
class DailyIntelligence:
    """每日情报报告"""
    date: str
    must_watch: List[CryptoEvent]
    market_analysis: MarketAnalysis
    tomorrow_events: List[TomorrowEvent]
    whale_alerts: List[WhaleActivity]
    raw_data: Dict
    generated_at: int
    regime_context: Dict = field(default_factory=dict)


class OdailySkillCollector:
    """Odaily Skill 风格情报采集器（世界解释器）
    
    定位：
    - 不是数据源，而是世界理解器
    - 不是执行层，而是语义层
    - 提供 context，不是 signal
    
    适合：
    - 新闻语义层
    - 给 LLM 提供结构化的 crypto context
    - Event-driven signal
    - Regime/context feature
    - 配合 Twitter/Telegram 形成事件因子
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_mock: bool = True,
        integration_type: str = "mock",
        skill_name: str = "odaily-crypto",
        api_url: Optional[str] = None
    ):
        self.api_key = api_key
        self.integration_type = integration_type
        self.skill_name = skill_name
        self.api_url = api_url
        self.use_mock = use_mock or integration_type == "mock"

        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="odaily_skill_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))

        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=1.0
        ))

        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300

        logger.info(
            f"OdailySkillCollector initialized "
            f"(type={integration_type}, mock={self.use_mock})"
        )

    async def get_daily_intelligence(self) -> DailyIntelligence:
        """获取每日情报报告"""
        cache_key = "daily_intelligence"

        if self._is_cache_valid(cache_key):
            logger.info("Returning cached intelligence")
            return self._cache[cache_key]

        async def _fetch():
            if self.use_mock:
                return self._generate_mock_intelligence()
            else:
                return await self._fetch_from_api()

        try:
            result = await self.circuit_breaker.execute(
                lambda: self.retry_policy.execute(_fetch)
            )

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Failed to fetch intelligence: {e}")
            return self._generate_mock_intelligence()

    async def get_must_watch_events(self) -> List[CryptoEvent]:
        """M1: 今日必关注"""
        intelligence = await self.get_daily_intelligence()
        return intelligence.must_watch

    async def get_market_analysis(self) -> MarketAnalysis:
        """M2: 加密市场分析"""
        intelligence = await self.get_daily_intelligence()
        return intelligence.market_analysis

    async def get_tomorrow_events(self) -> List[TomorrowEvent]:
        """M3: 明日关键事件"""
        intelligence = await self.get_daily_intelligence()
        return intelligence.tomorrow_events

    async def get_whale_alerts(self) -> List[WhaleActivity]:
        """M4: 巨鲸/预测市场异动"""
        intelligence = await self.get_daily_intelligence()
        return intelligence.whale_alerts

    async def get_regime_context(self) -> Dict:
        """获取市场 Regime 上下文"""
        intelligence = await self.get_daily_intelligence()
        return intelligence.regime_context

    async def get_event_signals(self) -> List[Dict]:
        """从情报中提取事件信号"""
        intelligence = await self.get_daily_intelligence()

        signals = []

        for event in intelligence.must_watch:
            if event.importance in [EventImportance.CRITICAL, EventImportance.HIGH]:
                signals.append({
                    "type": "event",
                    "title": event.title,
                    "sentiment": event.sentiment,
                    "symbols": event.affected_symbols,
                    "importance": event.importance.value,
                    "source": event.source
                })

        for whale in intelligence.whale_alerts:
            if whale.value_usd > 1000000:
                signals.append({
                    "type": "whale",
                    "activity": whale.activity_type,
                    "symbol": whale.symbol,
                    "value_usd": whale.value_usd,
                    "wallet": whale.wallet_address[:10] + "..."
                })

        for pred in intelligence.raw_data.get("predictions", []):
            if pred.yes_probability > 0.8 or pred.yes_probability < 0.2:
                signals.append({
                    "type": "prediction",
                    "question": pred.question,
                    "probability": pred.yes_probability,
                    "category": pred.category
                })

        return signals

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False

        cached = self._cache[key]
        if not isinstance(cached, dict) or "_cached_at" not in cached:
            return True

        age = datetime.now().timestamp() - cached["_cached_at"]
        return age < self._cache_ttl

    def _generate_mock_intelligence(self) -> DailyIntelligence:
        """生成模拟情报（用于测试）"""
        now = int(datetime.now().timestamp())

        return DailyIntelligence(
            date=datetime.now().strftime("%Y-%m-%d"),
            must_watch=[
                CryptoEvent(
                    id="evt_001",
                    title="BTC 突破关键阻力位 $105,000",
                    description="比特币突破重要技术阻力位，可能开启新一轮上涨",
                    importance=EventImportance.HIGH,
                    affected_symbols=["BTC"],
                    sentiment="bullish",
                    source="technical_analysis",
                    timestamp=now
                ),
                CryptoEvent(
                    id="evt_002",
                    title="ETH 升级预期升温",
                    description="以太坊即将到来的升级引发市场关注",
                    importance=EventImportance.MEDIUM,
                    affected_symbols=["ETH"],
                    sentiment="bullish",
                    source="protocol_news",
                    timestamp=now
                ),
                CryptoEvent(
                    id="evt_003",
                    title="监管消息：SEC 或将批准更多 ETF",
                    description="市场传言 SEC 可能批准更多加密 ETF",
                    importance=EventImportance.HIGH,
                    affected_symbols=["BTC", "ETH"],
                    sentiment="bullish",
                    source="regulatory",
                    timestamp=now
                )
            ],
            market_analysis=MarketAnalysis(
                regime=MarketRegime.BULL,
                btc_trend="强势上涨",
                eth_trend="跟涨",
                altcoin_trend="轮动",
                fear_greed_index=72,
                dominant_narrative="ETF 获批预期 + 机构入场",
                key_levels={
                    "BTC": {"resistance": 110000, "support": 100000},
                    "ETH": {"resistance": 4000, "support": 3500}
                },
                timestamp=now
            ),
            tomorrow_events=[
                TomorrowEvent(
                    event_name="美国 CPI 数据发布",
                    event_time="20:30",
                    timezone="EST",
                    importance=EventImportance.CRITICAL,
                    expected_impact="影响美元指数和风险资产",
                    symbols_affected=["BTC", "ETH"]
                ),
                TomorrowEvent(
                    event_name="FOMC 会议纪要",
                    event_time="22:00",
                    timezone="EST",
                    importance=EventImportance.HIGH,
                    expected_impact="影响美联储降息预期",
                    symbols_affected=["BTC"]
                )
            ],
            whale_alerts=[
                WhaleActivity(
                    wallet_address="0x1234...abcd",
                    activity_type="buy",
                    symbol="BTC",
                    amount=500,
                    value_usd=52500000,
                    exchange="Binance",
                    timestamp=now
                ),
                WhaleActivity(
                    wallet_address="0x5678...efgh",
                    activity_type="sell",
                    symbol="ETH",
                    amount=10000,
                    value_usd=35000000,
                    exchange="Coinbase",
                    timestamp=now
                )
            ],
            raw_data={
                "predictions": [
                    PredictionMarket(
                        question="BTC 会在本周突破 $110,000 吗？",
                        market_url="polymarket.com/b",
                        yes_probability=0.65,
                        volume_24h=500000,
                        category="crypto",
                        timestamp=now
                    )
                ],
                "social_metrics": {
                    "bitcoin_twitter_sentiment": 0.72,
                    "ethereum_twitter_sentiment": 0.68
                }
            },
            generated_at=now,
            regime_context={
                "current_regime": MarketRegime.BULL.value,
                "regime_confidence": 0.75,
                "narratives": ["ETF 叙事", "机构入场", "减半效应"],
                "risk_level": "medium",
                "recommended_exposure": {
                    "BTC": "overweight",
                    "ETH": "neutral",
                    "ALT": "selective"
                }
            }
        )

    async def _fetch_from_api(self) -> DailyIntelligence:
        """从真实 API 获取情报"""
        if self.integration_type == "clawhub":
            return await self._call_clawhub_skill()
        elif self.integration_type == "http":
            return await self._call_http_api()
        else:
            return self._generate_mock_intelligence()

    async def _call_clawhub_skill(self) -> DailyIntelligence:
        """调用 ClawHub Skill"""
        try:
            import subprocess

            result = await asyncio.to_thread(
                subprocess.run,
                ["clawhub", "run", self.skill_name, "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                return self._parse_clawhub_output(data)

        except Exception as e:
            logger.warning(f"Failed to call clawhub skill: {e}")

        return self._generate_mock_intelligence()

    async def _call_http_api(self) -> DailyIntelligence:
        """调用 HTTP API"""
        try:
            from shared.http_client import get_http_client
            client = get_http_client()

            api_url = self.api_url or "https://api.odaily.com/skill/daily"

            response = await client.get(
                api_url,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_api_output(data)

        except Exception as e:
            logger.warning(f"Failed to call HTTP API: {e}")

        return self._generate_mock_intelligence()

    def _parse_clawhub_output(self, data: Dict) -> DailyIntelligence:
        """解析 ClawHub 输出"""
        now = int(datetime.now().timestamp())

        return DailyIntelligence(
            date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
            must_watch=self._parse_events(data.get("must_watch", [])),
            market_analysis=self._parse_analysis(data.get("market_analysis", {})),
            tomorrow_events=self._parse_tomorrow(data.get("tomorrow_events", [])),
            whale_alerts=self._parse_whales(data.get("whale_alerts", [])),
            raw_data=data.get("raw_data", {}),
            generated_at=now,
            regime_context=data.get("regime_context", {})
        )

    def _parse_api_output(self, data: Dict) -> DailyIntelligence:
        """解析 API 输出"""
        return self._parse_clawhub_output(data)

    def _parse_events(self, events: List) -> List[CryptoEvent]:
        """解析事件列表"""
        result = []
        for e in events:
            try:
                result.append(CryptoEvent(
                    id=e.get("id", ""),
                    title=e.get("title", ""),
                    description=e.get("description", ""),
                    importance=EventImportance(e.get("importance", "medium")),
                    affected_symbols=e.get("affected_symbols", []),
                    sentiment=e.get("sentiment", "neutral"),
                    source=e.get("source", "api"),
                    timestamp=e.get("timestamp", int(datetime.now().timestamp())),
                    url=e.get("url")
                ))
            except Exception:
                pass
        return result

    def _parse_analysis(self, data: Dict) -> MarketAnalysis:
        """解析市场分析"""
        now = int(datetime.now().timestamp())

        return MarketAnalysis(
            regime=MarketRegime(data.get("regime", "unknown")),
            btc_trend=data.get("btc_trend", ""),
            eth_trend=data.get("eth_trend", ""),
            altcoin_trend=data.get("altcoin_trend", ""),
            fear_greed_index=data.get("fear_greed_index", 50),
            dominant_narrative=data.get("dominant_narrative", ""),
            key_levels=data.get("key_levels", {}),
            timestamp=now
        )

    def _parse_tomorrow(self, events: List) -> List[TomorrowEvent]:
        """解析明日事件"""
        result = []
        for e in events:
            try:
                result.append(TomorrowEvent(
                    event_name=e.get("event_name", ""),
                    event_time=e.get("event_time", ""),
                    timezone=e.get("timezone", "EST"),
                    importance=EventImportance(e.get("importance", "medium")),
                    expected_impact=e.get("expected_impact", ""),
                    symbols_affected=e.get("symbols_affected", [])
                ))
            except Exception:
                pass
        return result

    def _parse_whales(self, whales: List) -> List[WhaleActivity]:
        """解析巨鲸活动"""
        result = []
        for w in whales:
            try:
                result.append(WhaleActivity(
                    wallet_address=w.get("wallet_address", ""),
                    activity_type=w.get("activity_type", "unknown"),
                    symbol=w.get("symbol", ""),
                    amount=w.get("amount", 0),
                    value_usd=w.get("value_usd", 0),
                    exchange=w.get("exchange"),
                    timestamp=w.get("timestamp", int(datetime.now().timestamp()))
                ))
            except Exception:
                pass
        return result


_collector: Optional[OdailySkillCollector] = None


def get_odaily_collector(api_key: str = None) -> OdailySkillCollector:
    """获取 Odaily Skill 采集器"""
    global _collector
    if _collector is None:
        _collector = OdailySkillCollector(api_key=api_key)
    return _collector
