"""
Event Type Mapper - 翻译层

将 LLM/外部世界的原始事件类型映射到 domain 标准类型

三层语言架构:
  外部 (LLM/API) → mapper → domain (唯一标准)
"""

from typing import Optional
from infrastructure.logging import get_logger

logger = get_logger("event_service.mapper")

from domain.event.event_type import EventType
from domain.event.event_category import EventCategory


RAW_TO_DOMAIN: dict[str, EventType] = {
    "ETF_INFLOW": EventType.FLOW_ETF_INFLOW,
    "ETF_OUTFLOW": EventType.FLOW_ETF_OUTFLOW,
    "MACRO_CHANGE": EventType.MACRO_FOMC_RATE_DECISION,
    "LIQUIDATION": EventType.MARKET_STRUCTURE_LIQUIDATION,
    "REGULATORY": EventType.POLICY_REGULATION_POSITIVE,
    "REGULATORY_NEGATIVE": EventType.POLICY_REGULATION_NEGATIVE,
    "HACK_SECURITY": EventType.PROTOCOL_HACK,
    "WHALE_MOVEMENT": EventType.FLOW_WHALE_TRANSFER,
    "EXCHANGE_FLOW": EventType.FLOW_EXCHANGE_NET_INFLOW,
    "ONCHAIN_ACTIVITY": EventType.FLOW_WHALE_TRANSFER,
    "SOCIAL_SENTIMENT": EventType.SENTIMENT_SOCIAL_SPIKE,
    "NEWS_EVENT": EventType.SENTIMENT_NARRATIVE_TREND,
    "MARKET_REGIME": EventType.MARKET_STRUCTURE_VOLATILITY_EXPANSION,
    "BLACK_SWAN": EventType.RISK_SYSTEMIC_RISK,
    "NORMAL": EventType.SENTIMENT_NARRATIVE_TREND,
    "STABLECOIN_INFLOW": EventType.FLOW_STABLECOIN_INFLOW,
    "STABLECOIN_OUTFLOW": EventType.FLOW_STABLECOIN_OUTFLOW,
    "RATE_CUT": EventType.MACRO_INTEREST_RATE_CUT,
    "RATE_HIKE": EventType.MACRO_INTEREST_RATE_HIKE,
    "CPI_RELEASE": EventType.MACRO_CPI_RELEASE,
    "ETF_APPROVAL": EventType.POLICY_ETF_APPROVAL,
    "ETF_REJECTION": EventType.POLICY_ETF_REJECTION,
    "TOKEN_UNLOCK": EventType.PROTOCOL_TOKEN_UNLOCK,
    "MAINNET_LAUNCH": EventType.PROTOCOL_MAINNET_LAUNCH,
    "AIRDROP": EventType.PROTOCOL_AIRDROP,
    "PARTNERSHIP": EventType.PROTOCOL_PARTNERSHIP,
    "STABLECOIN_DEPEG": EventType.RISK_STABLECOIN_DEPEG,
    "LARGE_HACK": EventType.RISK_LARGE_HACK,
    "EXCHANGE_COLLAPSE": EventType.RISK_EXCHANGE_COLLAPSE,
    "KOL_BULLISH": EventType.SENTIMENT_KOL_BULLISH,
    "KOL_BEARISH": EventType.SENTIMENT_KOL_BEARISH,
    "NARRATIVE_TREND": EventType.SENTIMENT_NARRATIVE_TREND,
    "SOCIAL_SPIKE": EventType.SENTIMENT_SOCIAL_SPIKE,
}


UNKNOWN_EVENT_TYPE = EventType.SENTIMENT_NARRATIVE_TREND


def map_event_type(raw_type: str) -> tuple[EventType, bool]:
    """
    将原始事件类型映射到 domain EventType
    
    Returns:
        tuple: (mapped_event_type, was_mapped)
            - mapped_event_type: 映射后的事件类型
            - was_mapped: 是否成功映射（False表示使用了 fallback）
    """
    if not raw_type:
        logger.warning("Empty event type received, using fallback")
        return UNKNOWN_EVENT_TYPE, False

    normalized = raw_type.upper().strip()

    if normalized in RAW_TO_DOMAIN:
        return RAW_TO_DOMAIN[normalized], True

    for key, value in RAW_TO_DOMAIN.items():
        if key.upper() in normalized or normalized in key.upper():
            logger.debug(f"Mapped '{raw_type}' -> {value.value} (partial match)")
            return value, True

    logger.warning(f"Unknown event type: '{raw_type}', using fallback: {UNKNOWN_EVENT_TYPE.value}")
    return UNKNOWN_EVENT_TYPE, False


def get_event_category(event_type: EventType) -> EventCategory:
    """获取事件类型对应的分类"""
    return event_type.category


def is_high_priority(event_type: EventType) -> bool:
    """判断事件是否为高优先级（值得立即处理）"""
    category = event_type.category
    return category in [
        EventCategory.FLOW,
        EventCategory.MARKET_STRUCTURE,
        EventCategory.RISK,
    ]


def get_all_supported_raw_types() -> list[str]:
    """获取所有支持的原始类型（用于日志/调试）"""
    return list(RAW_TO_DOMAIN.keys())
