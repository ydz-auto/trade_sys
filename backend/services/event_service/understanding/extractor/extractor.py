"""
Event Extractor - 事件提取器
负责使用 LLM 从原始数据中提取结构化事件

职责：
- 调用 LLM 提取事件信息
- 将原始数据转换为 Structured Event
- 缓存管理
"""

import json
from typing import Dict, Optional, Any, List
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)
from infrastructure.llm.client import LLMServiceClient
from domain.event.event_type import EventType
from domain.event.direction import Direction

from ..parser.parser import ParsedContent
from ..classifier.classifier import SentimentLabel

logger = get_logger("event_service.extractor")


class ExtractionPrompt:
    """提取 Prompt 模板"""

    NEWS_TEMPLATE = """你是一个专业的加密货币事件提取专家。
从以下新闻内容中提取结构化事件信息，返回JSON格式：
{{
    "event_type": "事件类型（见下方列表）",
    "asset": "主要相关资产，如BTC/ETH",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（提取置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{}}
}}

可用事件类型:
- etf_inflow: ETF净流入
- etf_outflow: ETF净流出
- hack: 黑客攻击/安全事件
- stablecoin_depeg: 稳定币脱锚
- regulation_positive: 正面监管消息
- regulation_negative: 负面监管消息
- rate_cut: 降息
- rate_hike: 加息
- whale_transfer: 大户转账
- airdrop: 空投
- partnership: 合作
- upgrade: 协议升级
- narrative_trend: 叙事趋势
- kol_bullish: KOL看多
- kol_bearish: KOL看空

标题: {title}
内容: {content}
"""

    SOCIAL_TEMPLATE = """你是一个加密货币交易员言论分析专家。
从以下社交媒体内容中提取结构化事件信息，返回JSON格式：
{{
    "event_type": "kol_bullish/kol_bearish/narrative_trend/social_spike",
    "asset": "主要相关资产",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（提取置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{"platform": "twitter"}}
}}

作者: {author}
内容: {content}
"""

    TRADING_TEMPLATE = """你是一个加密货币交易员言论分析专家。
从以下交易员言论中提取结构化事件信息，返回JSON格式：
{{
    "event_type": "kol_bullish/kol_bearish/narrative_trend",
    "asset": "主要相关资产",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（提取置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{"trader": "交易员名称", "time_horizon": "short/medium/long"}}
}}

交易员: {trader_name}
内容: {content}
"""


class EventExtractor:
    """事件提取器

    唯一 LLM 调用入口
    """

    def __init__(self):
        self.llm_client = LLMServiceClient()
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="event_extractor_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=1.0
        ))
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 300

    def _get_cache_key(self, content_hash: str, source_type: str) -> str:
        return f"{source_type}:{content_hash}"

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        if not cache_entry:
            return False
        cached_at = cache_entry.get("cached_at", 0)
        return (datetime.now().timestamp() - cached_at) < self._cache_ttl

    async def extract(self, parsed_content: ParsedContent) -> Dict[str, Any]:
        """提取事件"""
        content_hash = str(hash(parsed_content.content))[:16]
        cache_key = self._get_cache_key(content_hash, parsed_content.source_type)

        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            logger.debug(f"Using cached extraction for {cache_key}")
            return self._cache[cache_key]["result"]

        extraction_result = await self._extract_with_llm(parsed_content)

        self._cache[cache_key] = {
            "result": extraction_result,
            "cached_at": datetime.now().timestamp()
        }

        return extraction_result

    async def _extract_with_llm(self, content: ParsedContent) -> Dict[str, Any]:
        """使用 LLM 提取"""
        try:
            if content.source_type == "news" or not content.source_type:
                return await self._extract_news(content)
            elif content.source_type == "social":
                return await self._extract_social(content)
            else:
                return self._create_default_extraction()
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            return self._create_default_extraction()

    async def _extract_news(self, content: ParsedContent) -> Dict[str, Any]:
        """提取新闻事件"""
        title = content.title
        body = content.content[:3000]

        if not title and not body:
            return self._create_default_extraction()

        prompt = ExtractionPrompt.NEWS_TEMPLATE.format(title=title, content=body)

        messages = [
            {"role": "system", "content": "你是一个专业的加密货币事件提取专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                return self._normalize_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON")

        return self._create_default_extraction()

    async def _extract_social(self, content: ParsedContent) -> Dict[str, Any]:
        """提取社交媒体事件"""
        content_text = content.content[:2000]

        if not content_text:
            return self._create_default_extraction()

        prompt = ExtractionPrompt.SOCIAL_TEMPLATE.format(
            author=content.author or "unknown",
            content=content_text
        )

        messages = [
            {"role": "system", "content": "你是一个加密货币交易员言论分析专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                return self._normalize_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON")

        return self._create_default_extraction()

    def _normalize_result(self, result: Dict) -> Dict:
        """标准化提取结果"""
        direction_str = result.get("direction", "neutral").lower()

        try:
            direction = Direction(direction_str)
        except ValueError:
            direction = Direction.NEUTRAL

        event_type_str = result.get("event_type", "narrative_trend")
        mapped_type = self._map_event_type(event_type_str)

        return {
            "event_type": mapped_type,
            "direction": direction,
            "strength": min(max(result.get("strength", 0.5), 0.0), 1.0),
            "confidence": min(max(result.get("confidence", 0.5), 0.0), 1.0),
            "summary": result.get("summary", ""),
            "affected_assets": result.get("affected_assets", []),
            "metadata": result.get("metadata", {})
        }

    def _map_event_type(self, raw_type: str) -> EventType:
        """映射事件类型"""
        type_mapping = {
            "etf_inflow": EventType.FLOW_ETF_INFLOW,
            "etf_outflow": EventType.FLOW_ETF_OUTFLOW,
            "hack": EventType.PROTOCOL_HACK,
            "stablecoin_depeg": EventType.RISK_STABLECOIN_DEPEG,
            "regulation_positive": EventType.POLICY_REGULATION_POSITIVE,
            "regulation_negative": EventType.POLICY_REGULATION_NEGATIVE,
            "rate_cut": EventType.MACRO_INTEREST_RATE_CUT,
            "rate_hike": EventType.MACRO_INTEREST_RATE_HIKE,
            "whale_transfer": EventType.FLOW_WHALE_TRANSFER,
            "airdrop": EventType.PROTOCOL_AIRDROP,
            "partnership": EventType.PROTOCOL_PARTNERSHIP,
            "upgrade": EventType.PROTOCOL_UPGRADE,
            "narrative_trend": EventType.SENTIMENT_NARRATIVE_TREND,
            "kol_bullish": EventType.SENTIMENT_KOL_BULLISH,
            "kol_bearish": EventType.SENTIMENT_KOL_BEARISH,
            "social_spike": EventType.SENTIMENT_SOCIAL_SPIKE,
        }

        return type_mapping.get(raw_type, EventType.SENTIMENT_NARRATIVE_TREND)

    def _create_default_extraction(self) -> Dict:
        """创建默认提取"""
        return {
            "event_type": EventType.SENTIMENT_NARRATIVE_TREND,
            "direction": Direction.NEUTRAL,
            "strength": 0.5,
            "confidence": 0.3,
            "summary": "",
            "affected_assets": [],
            "metadata": {}
        }


_extractor: Optional[EventExtractor] = None


def get_event_extractor() -> EventExtractor:
    """获取事件提取器"""
    global _extractor
    if _extractor is None:
        _extractor = EventExtractor()
    return _extractor
