"""
Understanding Engine - 理解引擎
整合 Parser、Classifier、Extractor，提供统一的理解接口

职责：
- 协调各组件工作
- 管理市场上下文
- 追踪 Narrative 和 Regime 变化
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig
)

from ..parser.parser import DataParser, ParsedContent, get_data_parser
from ..classifier.classifier import (
    EventClassifier,
    SentimentLabel,
    RegimeLabel,
    RiskLevel,
    get_event_classifier
)
from ..extractor.extractor import EventExtractor, get_event_extractor

logger = get_logger("event_service.engine")


@dataclass
class MarketContext:
    """市场上下文"""
    regime: RegimeLabel
    regime_confidence: float
    narratives: List[str]
    risk_level: RiskLevel
    fear_greed_index: int
    dominant_sentiment: str
    key_events: List[str]
    recommended_exposure: Dict[str, str]
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))


@dataclass
class EnrichedContent:
    """增强后的内容"""
    original: ParsedContent
    llm_extraction: Dict[str, Any]
    classification: Dict[str, Any]
    sentiment: SentimentLabel
    sentiment_score: float
    narratives: List[str]
    importance: float
    regime_relevance: float
    actionability: float


class UnderstandingEngine:
    """理解引擎

    数据流：
    Raw Data → Parser → ParsedContent
                         ↓
                   Classifier → Classification
                         ↓
                   Extractor → LLM Extraction
                         ↓
                   Enriched Content
    """

    def __init__(self):
        self.parser: DataParser = get_data_parser()
        self.classifier: EventClassifier = get_event_classifier()
        self.extractor: EventExtractor = get_event_extractor()

        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="understanding_engine_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))

        self._current_context: Optional[MarketContext] = None
        self._event_history: List[EnrichedContent] = []

        logger.info("UnderstandingEngine initialized")

    async def initialize(self):
        """初始化"""
        await self.update_context()

    async def understand(self, raw_data: Dict[str, Any], source_type: str = "news") -> EnrichedContent:
        """理解原始数据"""
        parsed = self.parser.parse(raw_data, source_type)

        classification = self.classifier.classify(
            title=parsed.title,
            content=parsed.content,
            importance=parsed.metadata.get("importance", 0.5)
        )

        llm_extraction = await self.extractor.extract(parsed)

        sentiment = SentimentLabel(classification.sentiment.value)
        self.classifier.update_regime(sentiment)

        enriched = EnrichedContent(
            original=parsed,
            llm_extraction=llm_extraction,
            classification={
                "regime": classification.regime,
                "risk_level": classification.risk_level,
                "event_category": classification.event_category,
                "keywords": classification.keywords,
                "reasoning": classification.reasoning
            },
            sentiment=sentiment,
            sentiment_score=classification.sentiment_score,
            narratives=classification.narratives,
            importance=llm_extraction.get("confidence", 0.5),
            regime_relevance=classification.regime_confidence,
            actionability=self._calculate_actionability(
                classification, llm_extraction, parsed
            )
        )

        self._event_history.append(enriched)
        if len(self._event_history) > 1000:
            self._event_history = self._event_history[-1000:]

        return enriched

    async def understand_batch(self, raw_datas: List[Dict[str, Any]], source_type: str = "news") -> List[EnrichedContent]:
        """批量理解"""
        import asyncio
        tasks = [self.understand(data, source_type) for data in raw_datas]
        return await asyncio.gather(*tasks)

    async def update_context(self):
        """更新市场上下文"""
        if not self.odaily:
            return

        try:
            regime_context = await self.odaily.get_regime_context()
            analysis = await self.odaily.get_market_analysis()

            from ..classifier.classifier import MarketRegime

            regime_map = {
                "bull": RegimeLabel.BULL,
                "bear": RegimeLabel.BEAR,
                "neutral": RegimeLabel.NEUTRAL,
                "volatile": RegimeLabel.VOLATILE
            }

            regime = regime_map.get(
                regime_context.get("current_regime", "unknown"),
                RegimeLabel.UNKNOWN
            )

            self._current_context = MarketContext(
                regime=regime,
                regime_confidence=regime_context.get("regime_confidence", 0.5),
                narratives=regime_context.get("narratives", []),
                risk_level=self._map_risk_level(regime_context.get("risk_level", "medium")),
                fear_greed_index=analysis.fear_greed_index if analysis else 50,
                dominant_sentiment=regime_context.get("current_regime", "neutral"),
                key_events=[],
                recommended_exposure=regime_context.get("recommended_exposure", {})
            )

            logger.info(f"Context updated: regime={regime.value}, narratives={len(self._current_context.narratives)}")

        except Exception as e:
            logger.error(f"Failed to update context: {e}")

    def get_context(self) -> Optional[MarketContext]:
        """获取当前市场上下文"""
        return self._current_context

    def _calculate_actionability(
        self,
        classification,
        extraction: Dict,
        parsed: ParsedContent
    ) -> float:
        """计算可操作性评分"""
        score = 0.5

        if extraction.get("confidence", 0) >= 0.8:
            score += 0.2

        if len(extraction.get("affected_assets", [])) > 0:
            score += 0.1

        if parsed.metadata.get("sentiment") != "neutral":
            score += 0.1

        if len(classification.narratives) > 0:
            score += 0.1

        return min(1.0, score)

    def _map_risk_level(self, risk_str: str) -> RiskLevel:
        """映射风险等级"""
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL
        }
        return risk_map.get(risk_str, RiskLevel.MEDIUM)


_engine: Optional[UnderstandingEngine] = None


async def get_understanding_engine() -> UnderstandingEngine:
    """获取理解引擎"""
    global _engine
    if _engine is None:
        _engine = UnderstandingEngine()
        await _engine.initialize()
    return _engine
