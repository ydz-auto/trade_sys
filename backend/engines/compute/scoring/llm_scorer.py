import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig

logger = get_logger("llm_scorer")


class ScoringPriority(Enum):
    P0_FULL = 0
    P1_LIGHT = 1
    P2_KEYWORD = 2


@dataclass
class LLMAnalysisResult:
    title_zh: str = ""
    content_zh: str = ""
    sentiment: str = "neutral"
    importance: float = 0.5
    relevance: float = 0.5
    confidence: float = 0.5
    symbols: List[str] = field(default_factory=list)
    narratives: List[str] = field(default_factory=list)
    actionable: bool = False
    source_quality: float = 0.5
    content_quality: float = 0.5
    timeliness: float = 0.5
    reasoning: str = ""
    scored_by: str = "llm"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title_zh": self.title_zh,
            "content_zh": self.content_zh,
            "sentiment": self.sentiment,
            "importance": self.importance,
            "relevance": self.relevance,
            "confidence": self.confidence,
            "symbols": self.symbols,
            "narratives": self.narratives,
            "actionable": self.actionable,
            "source_quality": self.source_quality,
            "content_quality": self.content_quality,
            "timeliness": self.timeliness,
            "reasoning": self.reasoning,
            "scored_by": self.scored_by
        }


class LLMScoringConfig:

    PRIORITY_MAP = {
        "odaily": ScoringPriority.P0_FULL,
        "clawhub_odaily": ScoringPriority.P0_FULL,
        "etf": ScoringPriority.P0_FULL,
        "macro": ScoringPriority.P0_FULL,
        "twitter": ScoringPriority.P1_LIGHT,
        "telegram": ScoringPriority.P1_LIGHT,
        "rss": ScoringPriority.P2_KEYWORD,
        "whale": ScoringPriority.P2_KEYWORD,
        "cryptonews": ScoringPriority.P2_KEYWORD,
        "cointelegraph": ScoringPriority.P2_KEYWORD,
    }

    P0_PROMPT = """你是一个加密货币新闻分析专家。请完成以下任务：

任务1：翻译
- 将标题翻译成中文
- 将内容压缩成简洁的中文摘要（100字以内）

任务2：分析
- 分析新闻的情绪、重要性、叙事等

任务3：提取
- 提取相关币种和叙事标签

返回 JSON 格式：
{
    "title_zh": "中文标题",
    "content_zh": "中文摘要，100字以内",
    "sentiment": "bullish/neutral/bearish",
    "importance": 0.0-1.0（事件重要性）,
    "relevance": 0.0-1.0（与交易相关性）,
    "confidence": 0.0-1.0（分析置信度）,
    "symbols": ["相关币种，如BTC,ETH"],
    "narratives": ["叙事标签，如ETF,DeFi"],
    "actionable": true/false（是否可交易）,
    "source_quality": 0.0-1.0（来源可信度）,
    "content_quality": 0.0-1.0（内容质量）,
    "timeliness": 0.0-1.0（时效性）,
    "reasoning": "分析理由，50字以内"
}

原文标题：{title}
原文内容：{content}
来源：{source}

只返回 JSON，不要其他内容。"""

    P1_PROMPT = """翻译并分析新闻，返回 JSON：

{
    "title_zh": "中文标题",
    "content_zh": "中文摘要，80字以内",
    "sentiment": "bullish/neutral/bearish",
    "importance": 0.0-1.0,
    "relevance": 0.0-1.0,
    "symbols": ["币种"],
    "actionable": true/false,
    "confidence": 0.0-1.0
}

标题：{title}
内容：{content[:300]}

只返回 JSON。"""

    @classmethod
    def get_priority(cls, source: str) -> ScoringPriority:
        source_lower = source.lower()
        for key, priority in cls.PRIORITY_MAP.items():
            if key in source_lower:
                return priority
        return ScoringPriority.P2_KEYWORD


class KeywordScorer:

    SENTIMENT_KEYWORDS = {
        "bullish": [
            "surge", "rally", "soar", "jump", "gain", "rise", "high", "breakout",
            "bull", "buy", "ETF", "approval", "positive", "上涨", "暴涨", "突破", "利好",
            "approved", "success", "growth", "adoption"
        ],
        "bearish": [
            "crash", "plunge", "dump", "drop", "fall", "decline", "low",
            "bear", "sell", "hack", "ban", "negative", "下跌", "暴跌", "跌破", "利空",
            "rejected", "failure", "crisis", "scam"
        ]
    }

    IMPORTANCE_KEYWORDS = {
        "high": [
            "ETF", "SEC", "FDA", "regulation", "hack", "crash", "breakout",
            "批准", "重大", "突破", "崩盘", "暴跌", "黑天鹅"
        ],
        "medium": [
            "update", "launch", "partnership", "upgrade", "listing",
            "升级", "合作", "发布", "上线"
        ]
    }

    SYMBOLS = {
        "BTC": ["BTC", "BITCOIN", "比特币"],
        "ETH": ["ETH", "ETHEREUM", "以太坊"],
        "SOL": ["SOL", "SOLANA"],
        "XRP": ["XRP", "RIPPLE"],
        "BNB": ["BNB", "BINANCE"],
        "ADA": ["ADA", "CARDANO"],
        "DOGE": ["DOGE", "DOGECOIN"],
        "DOT": ["DOT", "POLKADOT"],
        "AVAX": ["AVAX", "AVALANCHE"],
        "LINK": ["LINK", "CHAINLINK"],
    }

    NARRATIVES = {
        "ETF": ["ETF", "SPOT", "BLACKROCK", "Fidelity"],
        "DeFi": ["DeFi", "DEX", "LENDING", "uniswap", "compound"],
        "NFT": ["NFT", "opensea", "blur", "collection"],
        "Layer2": ["Layer2", "L2", "Arbitrum", "Optimism", "Polygon"],
        "Regulation": ["SEC", "CFTC", "regulation", "regulatory", "监管"],
        "Institutional": ["institutional", "bank", "fund", "hedge fund"],
        "Bitcoin": ["bitcoin", "BTC", "halving", "mining"],
        "Ethereum": ["ethereum", "ETH", "merge", "upgrade", "ETH2"],
    }

    KEYWORD_TRANSLATION = {
        "surge": "暴涨",
        "rally": "上涨",
        "soar": "飙升",
        "jump": "跳涨",
        "gain": "上涨",
        "rise": "上升",
        "high": "新高",
        "breakout": "突破",
        "bull": "看涨",
        "buy": "买入",
        "etf": "ETF",
        "approval": "获批",
        "positive": "利好",
        "crash": "暴跌",
        "plunge": "跳水",
        "dump": "砸盘",
        "drop": "下跌",
        "fall": "下跌",
        "decline": "下跌",
        "low": "新低",
        "bear": "看跌",
        "sell": "卖出",
        "hack": "被盗",
        "ban": "禁令",
        "negative": "利空",
        "bitcoin": "比特币",
        "btc": "BTC",
        "ethereum": "以太坊",
        "eth": "ETH",
        "solana": "Solana",
        "sol": "SOL",
    }

    @classmethod
    def _simple_translate_title(cls, title: str) -> str:
        result = title
        for en, zh in cls.KEYWORD_TRANSLATION.items():
            result = result.replace(en, zh, 1)
            result = result.replace(en.title(), zh)
        return result

    @classmethod
    def _simple_summarize(cls, content: str) -> str:
        if not content:
            return ""
        return content[:100].strip()

    @classmethod
    def score(cls, title: str, content: str = "") -> LLMAnalysisResult:
        title_zh = cls._simple_translate_title(title)

        content_zh = cls._simple_summarize(content)

        text = (title + " " + content).lower()

        bullish_count = sum(1 for kw in cls.SENTIMENT_KEYWORDS["bullish"]
                          if kw.lower() in text)
        bearish_count = sum(1 for kw in cls.SENTIMENT_KEYWORDS["bearish"]
                          if kw.lower() in text)

        if bullish_count > bearish_count:
            sentiment = "bullish"
        elif bearish_count > bullish_count:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        importance = 0.5
        if any(kw.lower() in text for kw in cls.IMPORTANCE_KEYWORDS["high"]):
            importance = 0.85
        elif any(kw.lower() in text for kw in cls.IMPORTANCE_KEYWORDS["medium"]):
            importance = 0.65

        symbols = []
        for symbol, keywords in cls.SYMBOLS.items():
            if any(kw.lower() in text for kw in keywords):
                if symbol not in symbols:
                    symbols.append(symbol)

        narratives = []
        for narrative, keywords in cls.NARRATIVES.items():
            if any(kw.lower() in text for kw in keywords):
                narratives.append(narrative)

        actionable = importance > 0.7 and len(symbols) > 0

        confidence = 0.6

        return LLMAnalysisResult(
            title_zh=title_zh,
            content_zh=content_zh,
            sentiment=sentiment,
            importance=importance,
            relevance=0.5,
            confidence=confidence,
            symbols=symbols[:5],
            narratives=narratives[:3],
            actionable=actionable,
            source_quality=0.5,
            content_quality=0.5,
            timeliness=0.5,
            reasoning="Keyword-based scoring (fallback)",
            scored_by="keyword"
        )


class LLMScoringEngine:

    def __init__(self, llm_pool=None):
        self.llm_pool = llm_pool
        self.config = LLMScoringConfig()
        self.keyword_scorer = KeywordScorer()

        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                name="llm_scorer",
                failure_threshold=3,
                recovery_timeout=60.0
            )
        )

        self.retry_policy = RetryPolicy(
            RetryConfig(
                max_attempts=2,
                initial_delay=1.0
            )
        )

        self._stats = {
            "total": 0,
            "llm_success": 0,
            "llm_failed": 0,
            "fallback_used": 0
        }

        logger.info("LLMScoringEngine initialized")

    def get_priority(self, source: str) -> ScoringPriority:
        return self.config.get_priority(source)

    async def analyze(self, event: Dict[str, Any]) -> LLMAnalysisResult:
        title = event.get("title", "")
        content = event.get("content", "")[:1000]
        source = event.get("source", "unknown")

        self._stats["total"] += 1

        priority = self.get_priority(source)

        if priority == ScoringPriority.P0_FULL:
            return await self._full_llm_analysis(title, content, source)
        elif priority == ScoringPriority.P1_LIGHT:
            return await self._light_llm_analysis(title, content, source)
        else:
            return self._fallback_analysis(title, content, source)

    async def _full_llm_analysis(
        self,
        title: str,
        content: str,
        source: str
    ) -> LLMAnalysisResult:
        try:
            if not self.llm_pool or not self.circuit_breaker.can_execute():
                return self._fallback_analysis(title, content, source)

            prompt = self.config.P0_PROMPT.format(
                title=title,
                content=content[:500],
                source=source
            )

            async def _call_llm():
                return await self.llm_pool.analyze(prompt)

            result = await self.retry_policy.execute(_call_llm)

            if result:
                parsed = self._parse_llm_result(result)
                self._stats["llm_success"] += 1
                self.circuit_breaker.record_success()
                return parsed

            raise Exception("LLM returned empty result")

        except Exception as e:
            logger.warning(f"Full LLM analysis failed: {e}")
            self._stats["llm_failed"] += 1
            self.circuit_breaker.record_failure()
            return self._fallback_analysis(title, content, source)

    async def _light_llm_analysis(
        self,
        title: str,
        content: str,
        source: str
    ) -> LLMAnalysisResult:
        try:
            if not self.llm_pool or not self.circuit_breaker.can_execute():
                return self._fallback_analysis(title, content, source)

            prompt = self.config.P1_PROMPT.format(
                title=title,
                content=content[:300]
            )

            async def _call_llm():
                return await self.llm_pool.analyze(prompt)

            result = await self.retry_policy.execute(_call_llm)

            if result:
                parsed = self._parse_llm_result(result)
                self._stats["llm_success"] += 1
                self.circuit_breaker.record_success()
                return parsed

            raise Exception("LLM returned empty result")

        except Exception as e:
            logger.warning(f"Light LLM analysis failed: {e}")
            self._stats["llm_failed"] += 1
            self.circuit_breaker.record_failure()
            return self._fallback_analysis(title, content, source)

    def _fallback_analysis(
        self,
        title: str,
        content: str,
        source: str
    ) -> LLMAnalysisResult:
        logger.info(f"Using keyword fallback for source: {source}")
        self._stats["fallback_used"] += 1
        return self.keyword_scorer.score(title, content)

    def _parse_llm_result(self, result: str) -> Optional[LLMAnalysisResult]:
        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                return LLMAnalysisResult(
                    title_zh=data.get("title_zh", ""),
                    content_zh=data.get("content_zh", ""),
                    sentiment=data.get("sentiment", "neutral"),
                    importance=float(data.get("importance", 0.5)),
                    relevance=float(data.get("relevance", 0.5)),
                    confidence=float(data.get("confidence", 0.8)),
                    symbols=data.get("symbols", []),
                    narratives=data.get("narratives", []),
                    actionable=bool(data.get("actionable", False)),
                    source_quality=float(data.get("source_quality", 0.7)),
                    content_quality=float(data.get("content_quality", 0.7)),
                    timeliness=float(data.get("timeliness", 0.7)),
                    reasoning=data.get("reasoning", ""),
                    scored_by="llm"
                )
        except Exception as e:
            logger.warning(f"Failed to parse LLM result: {e}")

        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "llm_success_rate": self._stats["llm_success"] / max(self._stats["total"], 1),
            "fallback_rate": self._stats["fallback_used"] / max(self._stats["total"], 1)
        }


_llm_scorer: Optional[LLMScoringEngine] = None


def get_llm_scorer(llm_pool=None) -> LLMScoringEngine:
    global _llm_scorer
    if _llm_scorer is None:
        _llm_scorer = LLMScoringEngine(llm_pool)
    return _llm_scorer
