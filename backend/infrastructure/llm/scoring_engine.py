import json
import re
from typing import Dict, List, Optional, Any
from enum import Enum

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig
from engines.compute.scoring.llm_scorer import LLMAnalysisResult, KeywordScorer

logger = get_logger("infrastructure.llm.scoring_engine")


class ScoringPriority(Enum):
    P0_FULL = 0
    P1_LIGHT = 1
    P2_KEYWORD = 2


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
