"""
Event Classifier - 事件分类器
负责对事件进行分类和标记

功能：
- Sentiment 分类（bullish/bearish/neutral）
- Narrative 分类（ETF、DeFi、机构等）
- Regime 分类（bull/bear/neutral/volatile）
- Risk 评估（low/medium/high/critical）
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("event_service.classifier")


class SentimentLabel(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class RegimeLabel(Enum):
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ClassificationResult:
    """分类结果"""
    sentiment: SentimentLabel
    sentiment_score: float
    regime: RegimeLabel
    regime_confidence: float
    narratives: List[str]
    risk_level: RiskLevel
    event_category: str
    keywords: List[str]
    reasoning: str


class NarrativeClassifier:
    """叙事分类器"""

    NARRATIVE_PATTERNS = {
        "ETF": ["etf", "spot", "approval", "sec", "sEC", "blackrock", "fidelity"],
        "DeFi": ["defi", "lending", "dex", "uniswap", "curve", "aave", "compound"],
        "NFT": ["nft", "opensea", "blur", "collection"],
        "Layer2": ["layer2", "rollup", "arbitrum", "optimism", "polygon", "zk"],
        "Institutional": ["institutional", "bank", "fund", "treasury", "billion"],
        "Gaming": ["gaming", "gamefi", "axie", "sandbox", "decentraland"],
        "AI": ["ai", "artificial", "neural", "ml", "bot"],
        "Meme": ["meme", "dogecoin", "shiba", "pepe"],
        "Regulation": ["regulation", "law", "ban", "illegal", "sec", "doj"],
        "Hack": ["hack", "exploit", "bridge", "scam", "rug"],
    }

    def classify(self, text: str) -> List[str]:
        """分类叙事"""
        text_lower = text.lower()
        found_narratives = []

        for narrative, keywords in self.NARRATIVE_PATTERNS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                found_narratives.append(narrative)

        return found_narratives


class SentimentClassifier:
    """情绪分类器"""

    BULLISH_PATTERNS = [
        "bull", "long", "buy", "breakout", "pump", "moon", "soar", "surge",
        "approval", "adoption", "upgrade", "partnership", "launch", "upgrade",
        "inflow", "institutional", "buy", "accumulation", "all-time", "high"
    ]

    BEARISH_PATTERNS = [
        "bear", "short", "sell", "crash", "dump", "plunge", "drop",
        "ban", "regulation", "hack", "exploit", "outflow", "selloff",
        "rejection", "delist", "crisis", "risk", "warning", "fear"
    ]

    def classify(self, text: str, confidence: float = 0.5) -> tuple[SentimentLabel, float]:
        """分类情绪"""
        text_lower = text.lower()

        bullish_count = sum(1 for p in self.BULLISH_PATTERNS if p in text_lower)
        bearish_count = sum(1 for p in self.BEARISH_PATTERNS if p in text_lower)

        total = bullish_count + bearish_count

        if total == 0:
            return SentimentLabel.NEUTRAL, confidence

        if bullish_count > bearish_count:
            score = min(0.9, 0.5 + bullish_count * 0.15)
            return SentimentLabel.BULLISH, score
        elif bearish_count > bullish_count:
            score = min(0.9, 0.5 + bearish_count * 0.15)
            return SentimentLabel.BEARISH, score
        else:
            return SentimentLabel.NEUTRAL, 0.5


class RegimeClassifier:
    """Regime 分类器"""

    def __init__(self):
        self.event_history: List[Dict] = []
        self._window_size = 50

    def update(self, sentiment: SentimentLabel, timestamp: int):
        """更新历史"""
        self.event_history.append({
            "sentiment": sentiment.value,
            "timestamp": timestamp
        })

        if len(self.event_history) > self._window_size:
            self.event_history = self.event_history[-self._window_size:]

    def classify(self) -> tuple[RegimeLabel, float]:
        """分类 Regime"""
        if not self.event_history:
            return RegimeLabel.UNKNOWN, 0.0

        recent = self.event_history[-20:]

        bull_count = sum(1 for e in recent if e["sentiment"] == "bullish")
        bear_count = sum(1 for e in recent if e["sentiment"] == "bearish")
        total = len(recent)

        if total == 0:
            return RegimeLabel.NEUTRAL, 0.5

        bull_ratio = bull_count / total
        bear_ratio = bear_count / total

        if bull_ratio > 0.65:
            return RegimeLabel.BULL, bull_ratio
        elif bear_ratio > 0.65:
            return RegimeLabel.BEAR, bear_ratio
        elif bull_ratio > 0.4 and bear_ratio > 0.4:
            return RegimeLabel.VOLATILE, 0.6
        else:
            return RegimeLabel.NEUTRAL, 0.5


class RiskClassifier:
    """风险分类器"""

    CRITICAL_KEYWORDS = [
        "hack", "exploit", "bridge", "collapse", "bankruptcy",
        "ban", "seizure", "fraud", "investigation", "lawsuit"
    ]

    HIGH_KEYWORDS = [
        "regulation", "sec", "doj", "warning", "risk", "selloff",
        "liquidation", "default", "crisis"
    ]

    def classify(self, sentiment: SentimentLabel, importance: float, has_critical_keywords: bool) -> RiskLevel:
        """分类风险"""
        if has_critical_keywords or importance > 0.9:
            return RiskLevel.CRITICAL
        elif importance > 0.75 or sentiment == SentimentLabel.BEARISH:
            return RiskLevel.HIGH
        elif importance > 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


class EventClassifier:
    """统一事件分类器"""

    def __init__(self):
        self.narrative_classifier = NarrativeClassifier()
        self.sentiment_classifier = SentimentClassifier()
        self.regime_classifier = RegimeClassifier()
        self.risk_classifier = RiskClassifier()

    def classify(
        self,
        title: str,
        content: str,
        importance: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> ClassificationResult:
        """统一分类"""
        full_text = f"{title} {content}"

        narratives = self.narrative_classifier.classify(full_text)

        sentiment, sentiment_score = self.sentiment_classifier.classify(full_text, importance)

        regime, regime_confidence = self.regime_classifier.classify()

        has_critical = any(kw in full_text.lower() for kw in self.risk_classifier.CRITICAL_KEYWORDS)
        risk_level = self.risk_classifier.classify(sentiment, importance, has_critical)

        keywords = self._extract_keywords(full_text, narratives)

        reasoning = self._generate_reasoning(sentiment, narratives, risk_level)

        event_category = self._categorize(narratives, sentiment)

        return ClassificationResult(
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            regime=regime,
            regime_confidence=regime_confidence,
            narratives=narratives,
            risk_level=risk_level,
            event_category=event_category,
            keywords=keywords,
            reasoning=reasoning
        )

    def update_regime(self, sentiment: SentimentLabel, timestamp: int = None):
        """更新 Regime"""
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        self.regime_classifier.update(sentiment, timestamp)

    def _extract_keywords(self, text: str, narratives: List[str]) -> List[str]:
        """提取关键词"""
        text_lower = text.lower()

        keywords = []

        narrative_keywords = {
            "ETF": ["etf", "sec", "approval", "spot"],
            "DeFi": ["defi", "dex", "lending"],
            "Hack": ["hack", "exploit"],
            "Regulation": ["regulation", "sec", "ban"],
            "Institutional": ["institutional", "bank", "fund"],
        }

        for narrative in narratives:
            if narrative in narrative_keywords:
                for kw in narrative_keywords[narrative]:
                    if kw in text_lower:
                        keywords.append(kw)

        return list(set(keywords))

    def _generate_reasoning(self, sentiment: SentimentLabel, narratives: List[str], risk: RiskLevel) -> str:
        """生成推理"""
        parts = []

        parts.append(f"Sentiment: {sentiment.value}")

        if narratives:
            parts.append(f"Narratives: {', '.join(narratives)}")

        parts.append(f"Risk: {risk.value}")

        return "; ".join(parts)

    def _categorize(self, narratives: List[str], sentiment: SentimentLabel) -> str:
        """分类事件类别"""
        if "Hack" in narratives or "Regulation" in narratives:
            return "risk_event"
        elif "ETF" in narratives:
            return "macro_event"
        elif sentiment == SentimentLabel.BULLISH:
            return "bullish_signal"
        elif sentiment == SentimentLabel.BEARISH:
            return "bearish_signal"
        else:
            return "neutral_event"


_classifier: Optional[EventClassifier] = None


def get_event_classifier() -> EventClassifier:
    """获取事件分类器"""
    global _classifier
    if _classifier is None:
        _classifier = EventClassifier()
    return _classifier
