"""
Event Extractor - LLM驱动的结构化事件提取服务
唯一的LLM调用入口

⚠️ 重要：所有事件类型使用 domain.event.EventType（系统唯一标准语言）
"""

import json
from typing import Dict, Optional, Any
from datetime import datetime

from infrastructure.logging import get_logger
logger = get_logger("event_service.extractor")

from infrastructure.llm.client import LLMServiceClient
from .schemas import (
    Event,
    DataSource,
    RawDataType,
    RawDataMessage,
    NewsExtractionPrompt,
    SocialExtractionPrompt,
    TraderOpinionExtractionPrompt,
    EtfFlowExtractionPrompt,
    OnChainExtractionPrompt,
)
from domain.event.event_type import EventType
from domain.event.direction import Direction
from ..mapper import map_event_type


class EventExtractor:
    def __init__(self):
        self.llm_client = LLMServiceClient()
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 300

    def _get_cache_key(self, data_type: str, content_hash: str) -> str:
        return f"{data_type}:{content_hash}"

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        if not cache_entry:
            return False
        cached_at = cache_entry.get("cached_at", 0)
        return (datetime.now().timestamp() - cached_at) < self._cache_ttl

    async def extract_from_raw_data(self, raw_message: RawDataMessage) -> Event:
        content_hash = str(hash(raw_message.raw_content))[:16]
        cache_key = self._get_cache_key(raw_message.data_type, content_hash)

        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            logger.debug(f"Using cached extraction for {cache_key}")
            cached = self._cache[cache_key]["result"]
            return self._create_event_from_extraction(cached, raw_message)

        extraction_result = await self._extract_with_llm(raw_message)

        self._cache[cache_key] = {
            "result": extraction_result,
            "cached_at": datetime.now().timestamp()
        }

        return self._create_event_from_extraction(extraction_result, raw_message)

    async def _extract_with_llm(self, raw_message: RawDataMessage) -> Dict[str, Any]:
        try:
            if raw_message.data_type == RawDataType.NEWS:
                return await self._extract_news_event(raw_message)
            elif raw_message.data_type == RawDataType.SOCIAL:
                return await self._extract_social_event(raw_message)
            elif raw_message.data_type == RawDataType.TRADER_OPINION:
                return await self._extract_trader_event(raw_message)
            elif raw_message.data_type == RawDataType.ETF_FLOW:
                return await self._extract_etf_event(raw_message)
            elif raw_message.data_type == RawDataType.ONCHAIN:
                return await self._extract_onchain_event(raw_message)
            else:
                return self._create_default_extraction("narrative_trend")
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            return self._create_default_extraction("narrative_trend")

    async def _extract_news_event(self, raw_message: RawDataMessage) -> Dict[str, Any]:
        title = raw_message.title or raw_message.content.get("title", "")
        content = raw_message.raw_content or raw_message.content.get("content", "")

        if not title and not content:
            return self._create_default_extraction("narrative_trend")

        prompt = NewsExtractionPrompt.TEMPLATE.format(title=title, content=content[:3000])

        messages = [
            {"role": "system", "content": "你是一个专业的加密货币事件提取专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                return self._normalize_extraction_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content}")

        return self._create_default_extraction("narrative_trend")

    async def _extract_social_event(self, raw_message: RawDataMessage) -> Dict[str, Any]:
        content = raw_message.raw_content or raw_message.content.get("content", "")
        platform = raw_message.content.get("platform", "unknown")
        author = raw_message.content.get("author", "unknown")

        if not content:
            return self._create_default_extraction("social_spike")

        prompt = SocialExtractionPrompt.TEMPLATE.format(
            trader_name=author,
            platform=platform,
            content=content[:2000]
        )

        messages = [
            {"role": "system", "content": "你是一个加密货币交易员言论分析专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                return self._normalize_extraction_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content}")

        return self._create_default_extraction("social_spike")

    async def _extract_trader_event(self, raw_message: RawDataMessage) -> Dict[str, Any]:
        content = raw_message.raw_content or raw_message.content.get("content", "")
        trader_name = raw_message.content.get("trader_name", "unknown")
        asset = raw_message.content.get("asset", "BTC")

        if not content:
            return self._create_default_extraction("kol_bullish")

        prompt = TraderOpinionExtractionPrompt.TEMPLATE.format(
            trader_name=trader_name,
            content=content[:2000]
        )

        messages = [
            {"role": "system", "content": "你是一个加密货币交易员言论分析专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                if "affected_assets" not in result:
                    result["affected_assets"] = [asset]
                return self._normalize_extraction_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content}")

        return self._create_default_extraction("kol_bullish")

    async def _extract_etf_event(self, raw_message: RawDataMessage) -> Dict[str, Any]:
        content = raw_message.raw_content or json.dumps(raw_message.content)

        if not content:
            return self._create_default_extraction("etf_inflow")

        prompt = EtfFlowExtractionPrompt.TEMPLATE.format(content=content)

        messages = [
            {"role": "system", "content": "你是一个ETF流量分析专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                return self._normalize_extraction_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content}")

        net_flow = raw_message.content.get("net_flow", 0)
        event_type_str = "etf_inflow" if net_flow > 0 else "etf_outflow"
        direction_str = "bullish" if net_flow > 0 else "bearish"

        return {
            "event_type": event_type_str,
            "asset": raw_message.content.get("symbol", "BTC"),
            "direction": direction_str,
            "strength": min(abs(net_flow) / 100000000, 1.0),
            "confidence": 0.7,
            "summary": f"ETF {'流入' if net_flow > 0 else '流出'}",
            "affected_assets": [raw_message.content.get("symbol", "BTC")],
            "metadata": {"net_flow": net_flow}
        }

    async def _extract_onchain_event(self, raw_message: RawDataMessage) -> Dict[str, Any]:
        content = raw_message.raw_content or json.dumps(raw_message.content)

        if not content:
            return self._create_default_extraction("whale_transfer")

        prompt = OnChainExtractionPrompt.TEMPLATE.format(content=content)

        messages = [
            {"role": "system", "content": "你是一个链上数据分析专家。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.llm_client.chat(messages, model="gpt-4o-mini")

        if response.content:
            try:
                result = json.loads(response.content)
                return self._normalize_extraction_result(result)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response.content}")

        return self._create_default_extraction("whale_transfer")

    def _normalize_extraction_result(self, result: Dict) -> Dict:
        raw_event_type = result.get("event_type", "narrative_trend")
        direction_str = result.get("direction", "neutral").lower()

        mapped_type, was_mapped = map_event_type(raw_event_type)

        try:
            direction = Direction(direction_str)
        except ValueError:
            direction = Direction.NEUTRAL

        return {
            "event_type": mapped_type,
            "direction": direction,
            "strength": min(max(result.get("strength", 0.5), 0.0), 1.0),
            "confidence": min(max(result.get("confidence", 0.5), 0.0), 1.0),
            "summary": result.get("summary", ""),
            "affected_assets": result.get("affected_assets", []),
            "metadata": result.get("metadata", {})
        }

    def _create_default_extraction(self, default_type: str) -> Dict:
        mapped_type, _ = map_event_type(default_type)
        return {
            "event_type": mapped_type,
            "direction": Direction.NEUTRAL,
            "strength": 0.5,
            "confidence": 0.3,
            "summary": "",
            "affected_assets": [],
            "metadata": {}
        }

    def _create_event_from_extraction(self, extraction: Dict, raw_message: RawDataMessage) -> Event:
        source_map = {
            RawDataType.NEWS: DataSource.NEWS,
            RawDataType.SOCIAL: DataSource.SOCIAL,
            RawDataType.TRADER_OPINION: DataSource.TRADER,
            RawDataType.ETF_FLOW: DataSource.ETF,
            RawDataType.ONCHAIN: DataSource.ONCHAIN,
            RawDataType.MACRO: DataSource.MACRO,
        }

        return Event(
            event_id=f"evt_{raw_message.message_id[:8]}",
            event_type=extraction["event_type"],
            asset=extraction.get("asset", "BTC"),
            direction=extraction["direction"],
            strength=extraction["strength"],
            confidence=extraction["confidence"],
            sources=[source_map.get(raw_message.data_type, DataSource.NEWS)],
            source_details=[{"source": raw_message.source, "original": raw_message.content}],
            timestamp=raw_message.timestamp,
            metadata={
                "summary": extraction["summary"],
                "affected_assets": extraction["affected_assets"],
                **extraction.get("metadata", {})
            },
            raw_data_refs=[raw_message.message_id]
        )


_event_extractor: Optional[EventExtractor] = None


def get_event_extractor() -> EventExtractor:
    global _event_extractor
    if _event_extractor is None:
        _event_extractor = EventExtractor()
    return _event_extractor
