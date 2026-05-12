"""
Intelligence Layer - 情报层

功能：
- Skill 数据整合
- LLM 语义处理
- 事件提取
- 情绪分析
- Narrative 检测
- Regime 标记

Intelligence 数据通过 Skill Adapter → StandardEvent → EventBus
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio

from shared.contracts import StandardEvent, EventType, Sentiment, Source, create_news_event
from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)

logger = get_logger("intelligence")


class MarketRegime(Enum):
    """市场状态"""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class MarketContext:
    """市场上下文"""
    regime: MarketRegime
    regime_confidence: float
    narratives: List[str]
    risk_level: str  # low/medium/high
    fear_greed_index: int
    dominant_sentiment: str
    recommended_exposure: Dict[str, str]
    key_events: List[str]
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))


@dataclass
class EnrichedEvent:
    """增强后的事件"""
    original: StandardEvent
    llm_summary: str = ""
    extracted_entities: List[str] = field(default_factory=list)
    sentiment_score: float = 0.5
    importance_score: float = 0.5
    regime_relevance: float = 0.5
    narratives: List[str] = field(default_factory=list)
    actionability: float = 0.5  # 可操作性评分


class IntelligenceEngine:
    """情报引擎
    
    负责：
    - 从 EventBus 接收原始事件
    - LLM 增强处理
    - 情绪分析
    - Narrative 检测
    - Regime 标记
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._current_context: Optional[MarketContext] = None
        self._event_history: List[StandardEvent] = []
        
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="intelligence_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        
        logger.info("IntelligenceEngine initialized")
    
    async def enrich_event(self, event: StandardEvent) -> EnrichedEvent:
        """增强单个事件"""
        enriched = EnrichedEvent(original=event)
        
        # TODO: 调用 LLM 进行增强
        # 1. 生成摘要
        enriched.llm_summary = self._generate_summary(event)
        
        # 2. 提取实体
        enriched.extracted_entities = self._extract_entities(event)
        
        # 3. 评估重要性
        enriched.importance_score = self._score_importance(event)
        
        # 4. 评估叙事相关性
        enriched.regime_relevance = self._assess_regime_relevance(event)
        
        # 5. 评估可操作性
        enriched.actionability = self._score_actionability(event)
        
        return enriched
    
    async def enrich_batch(self, events: List[StandardEvent]) -> List[EnrichedEvent]:
        """批量增强事件"""
        tasks = [self.enrich_event(e) for e in events]
        return await asyncio.gather(*tasks)
    
    async def update_context(self, events: List[StandardEvent]):
        """更新市场上下文"""
        if not events:
            return
        
        # 分析最近事件，更新 regime
        bull_count = sum(1 for e in events if e.sentiment == Sentiment.BULLISH.value)
        bear_count = sum(1 for e in events if e.sentiment == Sentiment.BEARISH.value)
        total = bull_count + bear_count
        
        if total > 0:
            bull_ratio = bull_count / total
            
            if bull_ratio > 0.7:
                regime = MarketRegime.BULL
                confidence = bull_ratio
            elif bull_ratio < 0.3:
                regime = MarketRegime.BEAR
                confidence = 1 - bull_ratio
            else:
                regime = MarketRegime.NEUTRAL
                confidence = 0.5
            
            self._current_context = MarketContext(
                regime=regime,
                regime_confidence=confidence,
                narratives=self._extract_narratives(events),
                risk_level=self._assess_risk_level(events),
                fear_greed_index=self._estimate_fear_greed(events),
                dominant_sentiment="bullish" if bull_ratio > 0.5 else "bearish",
                recommended_exposure=self._generate_exposure(regime)
            )
    
    def get_current_context(self) -> Optional[MarketContext]:
        """获取当前市场上下文"""
        return self._current_context
    
    def _generate_summary(self, event: StandardEvent) -> str:
        """生成摘要"""
        # TODO: 调用 LLM
        return f"{event.title}: {event.summary[:100]}..."
    
    def _extract_entities(self, event: StandardEvent) -> List[str]:
        """提取实体"""
        entities = []
        
        # 从 symbols 提取
        entities.extend(event.symbols)
        
        # 从 tags 提取
        entities.extend([t for t in event.tags if t not in entities])
        
        return list(set(entities))
    
    def _score_importance(self, event: StandardEvent) -> float:
        """评估重要性"""
        score = event.importance
        
        # 加分项
        if event.confidence > 0.9:
            score += 0.1
        if "critical" in event.tags:
            score += 0.2
        if event.get_age_minutes() < 30:
            score += 0.1
        
        # 减分项
        if event.get_age_minutes() > 120:
            score -= 0.2
        
        return min(1.0, max(0.0, score))
    
    def _assess_regime_relevance(self, event: StandardEvent) -> float:
        """评估与当前 regime 的相关性"""
        narrative_keywords = {
            "bull": ["etf", "institutional", "adoption", "approval", "upgrade"],
            "bear": ["ban", "regulation", "hack", "crash", "selloff"],
            "neutral": ["update", "partnership", "listing"]
        }
        
        content = f"{event.title} {event.content}".lower()
        
        relevance = 0.5
        
        # 检查是否与牛市叙事相关
        if any(kw in content for kw in narrative_keywords["bull"]):
            relevance += 0.3
        
        # 检查是否与熊市叙事相关
        if any(kw in content for kw in narrative_keywords["bear"]):
            relevance -= 0.3
        
        return min(1.0, max(0.0, relevance))
    
    def _score_actionability(self, event: StandardEvent) -> float:
        """评估可操作性"""
        score = 0.5
        
        # 高重要性加分
        if event.importance >= 0.75:
            score += 0.2
        
        # 有明确标的加分
        if len(event.symbols) > 0:
            score += 0.1
        
        # 高置信度加分
        if event.confidence >= 0.8:
            score += 0.1
        
        # 新事件加分
        if event.get_age_minutes() < 60:
            score += 0.1
        
        return min(1.0, score)
    
    def _extract_narratives(self, events: List[StandardEvent]) -> List[str]:
        """提取当前叙事"""
        narrative_counts = {}
        
        for event in events:
            for tag in event.tags:
                narrative_counts[tag] = narrative_counts.get(tag, 0) + 1
        
        # 返回最常见的叙事
        sorted_narratives = sorted(narrative_counts.items(), key=lambda x: x[1], reverse=True)
        return [n[0] for n in sorted_narratives[:5]]
    
    def _assess_risk_level(self, events: List[StandardEvent]) -> str:
        """评估风险等级"""
        high_risk_count = 0
        
        for event in events:
            if event.importance >= 0.9:
                high_risk_count += 1
        
        if high_risk_count >= 3:
            return "high"
        elif high_risk_count >= 1:
            return "medium"
        else:
            return "low"
    
    def _estimate_fear_greed(self, events: List[StandardEvent]) -> int:
        """估算恐惧贪婪指数"""
        if not events:
            return 50
        
        bull_count = sum(1 for e in events if e.sentiment == Sentiment.BULLISH.value)
        total = len(events)
        
        ratio = bull_count / total if total > 0 else 0.5
        
        # 0-100 映射
        return int(ratio * 100)
    
    def _generate_exposure(self, regime: MarketRegime) -> Dict[str, str]:
        """生成建议仓位"""
        exposures = {
            MarketRegime.BULL: {"BTC": "overweight", "ETH": "overweight", "ALT": "selective"},
            MarketRegime.BEAR: {"BTC": "neutral", "ETH": "underweight", "ALT": "avoid"},
            MarketRegime.NEUTRAL: {"BTC": "neutral", "ETH": "neutral", "ALT": "neutral"},
            MarketRegime.VOLATILE: {"BTC": "neutral", "ETH": "neutral", "ALT": "avoid"},
            MarketRegime.UNKNOWN: {"BTC": "neutral", "ETH": "neutral", "ALT": "neutral"}
        }
        
        return exposures.get(regime, exposures[MarketRegime.UNKNOWN])


class NarrativeTracker:
    """叙事追踪器
    
    追踪当前市场的主流叙事和变化
    """
    
    def __init__(self):
        self._narrative_history: List[Dict] = []
    
    def track(self, events: List[StandardEvent]) -> Dict:
        """追踪叙事"""
        narrative_counts = {}
        
        for event in events:
            for tag in event.tags:
                narrative_counts[tag] = narrative_counts.get(tag, 0) + 1
        
        sorted_narratives = sorted(narrative_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "dominant_narrative": sorted_narratives[0][0] if sorted_narratives else "none",
            "narratives": [{"name": n[0], "count": n[1]} for n in sorted_narratives[:10]],
            "timestamp": int(datetime.now().timestamp())
        }
    
    def detect_shift(self, old_narratives: List[str], new_narratives: List[str]) -> List[str]:
        """检测叙事变化"""
        old_set = set(old_narratives)
        new_set = set(new_narratives)
        
        emerged = list(new_set - old_set)
        faded = list(old_set - new_set)
        
        return emerged + faded


# 全局实例
_intelligence_engine: Optional[IntelligenceEngine] = None

def get_intelligence_engine() -> IntelligenceEngine:
    """获取情报引擎"""
    global _intelligence_engine
    if _intelligence_engine is None:
        _intelligence_engine = IntelligenceEngine()
    return _intelligence_engine
