"""
Understanding Hub - 理解中心
整合所有理解组件，提供统一的理解接口

职责：
- 整合 Parser、Classifier、Extractor、Engine
- 提供情报报告生成
- 管理 Odaily Skill 和其他 Skill
- 生成交易上下文
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig
)

from ..engine.engine import UnderstandingEngine, MarketContext, EnrichedContent, get_understanding_engine
from ..skills.odaily.collector import (
    OdailySkillCollector,
    DailyIntelligence,
    CryptoEvent,
    WhaleActivity,
    TomorrowEvent,
    get_odaily_collector
)

logger = get_logger("event_service.hub")


@dataclass
class EnrichedNews:
    """增强后的新闻"""
    id: str
    title: str
    summary: str
    sentiment: str
    sentiment_score: float
    affected_symbols: List[str]
    importance: str
    regime_relevance: float
    event_type: str
    narratives: List[str]
    actionability: float
    raw_data: Dict


@dataclass
class IntelligenceReport:
    """情报报告"""
    timestamp: int
    market_context: MarketContext
    enriched_news: List[EnrichedNews]
    event_signals: List[Dict]
    whale_activity: List[Dict]
    tomorrow_events: List[Dict]
    regime_changes: List[str]
    risk_alerts: List[str]


class UnderstandingHub:
    """理解中心

    作为 Semantic Intelligence Layer，整合所有理解组件

    数据流：
    Raw Data Layer (RSS/API/Crawl)
        ↓
    Semantic Intelligence Layer
        ↓
    Enriched Events
        ↓
    Factor Engine
    """

    def __init__(self):
        self.engine: Optional[UnderstandingEngine] = None
        self.odaily: Optional[OdailySkillCollector] = None

        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="understanding_hub_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))

        self._components: Dict[str, Any] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300

        logger.info("UnderstandingHub initialized")

    async def initialize(self):
        """初始化"""
        self.engine = await get_understanding_engine()
        self.odaily = get_odaily_collector()

    def register_component(self, name: str, component: Any):
        """注册组件"""
        self._components[name] = component
        logger.info(f"Registered component: {name}")

    async def get_intelligence_report(self) -> IntelligenceReport:
        """获取完整情报报告"""
        now = int(datetime.now().timestamp())

        try:
            context_task = self._get_market_context()
            news_task = self._get_enriched_news()
            signals_task = self._get_event_signals()

            context, news, signals = await context_task, news_task, signals_task

            return IntelligenceReport(
                timestamp=now,
                market_context=context,
                enriched_news=news,
                event_signals=signals.get("events", []),
                whale_activity=signals.get("whales", []),
                tomorrow_events=signals.get("tomorrow", []),
                regime_changes=signals.get("regime_changes", []),
                risk_alerts=signals.get("risk_alerts", [])
            )

        except Exception as e:
            logger.error(f"Failed to generate intelligence report: {e}")
            return self._create_empty_report(now)

    async def _get_market_context(self) -> MarketContext:
        """获取市场上下文"""
        if self.engine and self.engine._current_context:
            return self.engine._current_context

        if self.odaily:
            try:
                regime_context = await self.odaily.get_regime_context()
                analysis = await self.odaily.get_market_analysis()

                from ..classifier.classifier import RegimeLabel, RiskLevel

                regime_map = {
                    "bull": RegimeLabel.BULL,
                    "bear": RegimeLabel.BEAR,
                    "neutral": RegimeLabel.NEUTRAL,
                    "volatile": RegimeLabel.VOLATILE
                }

                risk_map = {
                    "low": RiskLevel.LOW,
                    "medium": RiskLevel.MEDIUM,
                    "high": RiskLevel.HIGH,
                    "critical": RiskLevel.CRITICAL
                }

                return MarketContext(
                    regime=regime_map.get(
                        regime_context.get("current_regime", "unknown"),
                        RegimeLabel.UNKNOWN
                    ),
                    regime_confidence=regime_context.get("regime_confidence", 0.5),
                    narratives=regime_context.get("narratives", []),
                    risk_level=risk_map.get(
                        regime_context.get("risk_level", "medium"),
                        RiskLevel.MEDIUM
                    ),
                    fear_greed_index=analysis.fear_greed_index if analysis else 50,
                    dominant_sentiment=regime_context.get("current_regime", "neutral"),
                    key_events=[],
                    recommended_exposure=regime_context.get("recommended_exposure", {})
                )
            except Exception as e:
                logger.warning(f"Failed to get Odaily context: {e}")

        return self._create_default_context()

    async def _get_enriched_news(self) -> List[EnrichedNews]:
        """获取增强后的新闻"""
        if not self.odaily:
            return []

        try:
            events = await self.odaily.get_must_watch_events()

            return [
                EnrichedNews(
                    id=e.id,
                    title=e.title,
                    summary=e.description[:200],
                    sentiment=e.sentiment,
                    sentiment_score=0.7 if e.sentiment == "bullish" else 0.3,
                    affected_symbols=e.affected_symbols,
                    importance=e.importance.value,
                    regime_relevance=0.7,
                    event_type="market_event",
                    narratives=self._extract_narratives(e.title),
                    actionability=0.7 if e.importance.value in ["critical", "high"] else 0.5,
                    raw_data={}
                )
                for e in events[:10]
            ]

        except Exception as e:
            logger.error(f"Failed to enrich news: {e}")
            return []

    async def _get_event_signals(self) -> Dict:
        """获取事件信号"""
        signals = {
            "events": [],
            "whales": [],
            "tomorrow": [],
            "regime_changes": [],
            "risk_alerts": []
        }

        if not self.odaily:
            return signals

        try:
            whales = await self.odaily.get_whale_alerts()
            signals["whales"] = [
                {
                    "symbol": w.symbol,
                    "type": w.activity_type,
                    "value_usd": w.value_usd,
                    "exchange": w.exchange
                }
                for w in whales if w.value_usd > 1000000
            ]

            tomorrow = await self.odaily.get_tomorrow_events()
            signals["tomorrow"] = [
                {
                    "event": e.event_name,
                    "time": e.event_time,
                    "impact": e.expected_impact,
                    "symbols": e.symbols_affected,
                    "importance": e.importance.value
                }
                for e in tomorrow
            ]

            events = await self.odaily.get_event_signals()
            signals["events"] = events

            signals["risk_alerts"] = self._detect_risk_alerts(events, whales)

        except Exception as e:
            logger.warning(f"Failed to get event signals: {e}")

        return signals

    def _extract_narratives(self, text: str) -> List[str]:
        """提取叙事"""
        narratives = []
        text_lower = text.lower()

        narrative_keywords = {
            "ETF": ["etf", "approval", "sec"],
            "DeFi": ["defi", "lending", "dex"],
            "NFT": ["nft", "opensea"],
            "Institutional": ["institutional", "bank", "fund"],
            "Regulation": ["regulation", "sec", "ban"]
        }

        for narrative, keywords in narrative_keywords.items():
            if any(kw in text_lower for kw in keywords):
                narratives.append(narrative)

        return narratives

    def _detect_risk_alerts(self, events: List[Dict], whales: List[WhaleActivity]) -> List[str]:
        """检测风险告警"""
        alerts = []

        critical_events = [e for e in events if e.get("importance") == "critical"]
        if critical_events:
            alerts.append(f"发现 {len(critical_events)} 个关键事件需要关注")

        large_sells = [w for w in whales if w.activity_type == "sell" and w.value_usd > 50000000]
        if large_sells:
            alerts.append(f"检测到大额卖出信号: {len(large_sells)} 笔 >$50M")

        return alerts

    async def generate_trading_context(self) -> Dict:
        """生成交易上下文（用于 LLM 决策）"""
        report = await self.get_intelligence_report()

        return {
            "timestamp": datetime.now().isoformat(),
            "market_regime": report.market_context.regime.value,
            "regime_confidence": report.market_context.regime_confidence,
            "risk_level": report.market_context.risk_level.value,
            "fear_greed": report.market_context.fear_greed_index,
            "dominant_narratives": report.market_context.narratives,
            "recommended_exposure": report.market_context.recommended_exposure,

            "top_events": [
                {
                    "title": e.title,
                    "sentiment": e.sentiment,
                    "symbols": e.affected_symbols,
                    "importance": e.importance
                }
                for e in report.enriched_news[:5]
            ],

            "whale_alerts": report.whale_activity[:5],
            "tomorrow_events": report.tomorrow_events[:3],
            "risk_alerts": report.risk_alerts,

            "actionable_insights": self._generate_insights(report)
        }

    def _generate_insights(self, report: IntelligenceReport) -> List[str]:
        """生成可操作的洞察"""
        insights = []

        if report.market_context.regime.value == "bull":
            insights.append("当前处于牛市，建议逢低买入")
        elif report.market_context.regime.value == "bear":
            insights.append("当前处于熊市，建议观望或做空")

        narratives = report.market_context.narratives
        if "ETF" in narratives:
            insights.append("ETF 叙事持续，关注获批预期")
        if "Institutional" in narratives:
            insights.append("机构叙事，关注大资金动向")

        if len(report.whale_activity) > 3:
            insights.append("近期巨鲸活动频繁，关注方向")

        return insights

    def _create_empty_report(self, now: int) -> IntelligenceReport:
        """创建空报告"""
        from ..classifier.classifier import RegimeLabel, RiskLevel

        return IntelligenceReport(
            timestamp=now,
            market_context=self._create_default_context(),
            enriched_news=[],
            event_signals=[],
            whale_activity=[],
            tomorrow_events=[],
            regime_changes=[],
            risk_alerts=["情报获取失败"]
        )

    def _create_default_context(self) -> MarketContext:
        """创建默认上下文"""
        from ..classifier.classifier import RegimeLabel, RiskLevel

        return MarketContext(
            regime=RegimeLabel.NEUTRAL,
            regime_confidence=0.5,
            narratives=["观察中"],
            risk_level=RiskLevel.MEDIUM,
            fear_greed_index=50,
            dominant_sentiment="neutral",
            key_events=[],
            recommended_exposure={}
        )


_hub: Optional[UnderstandingHub] = None


async def get_understanding_hub() -> UnderstandingHub:
    """获取理解中心"""
    global _hub
    if _hub is None:
        _hub = UnderstandingHub()
        await _hub.initialize()
    return _hub
