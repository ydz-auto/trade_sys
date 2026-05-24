from enum import Enum

from domain.event.event_category import EventCategory


class EventType(str, Enum):
    MARKET_STRUCTURE_LIQUIDATION = "liquidation"
    MARKET_STRUCTURE_FUNDING_RATE_SPIKE = "funding_rate_spike"
    MARKET_STRUCTURE_OPEN_INTEREST_SPIKE = "open_interest_spike"
    MARKET_STRUCTURE_ORDERBOOK_IMBALANCE = "orderbook_imbalance"
    MARKET_STRUCTURE_VOLATILITY_EXPANSION = "volatility_expansion"

    FLOW_ETF_INFLOW = "etf_inflow"
    FLOW_ETF_OUTFLOW = "etf_outflow"
    FLOW_STABLECOIN_INFLOW = "stablecoin_inflow"
    FLOW_STABLECOIN_OUTFLOW = "stablecoin_outflow"
    FLOW_EXCHANGE_NET_INFLOW = "exchange_net_inflow"
    FLOW_EXCHANGE_NET_OUTFLOW = "exchange_net_outflow"
    FLOW_WHALE_TRANSFER = "whale_transfer"

    MACRO_CPI_RELEASE = "cpi_release"
    MACRO_FOMC_RATE_DECISION = "fomc_rate_decision"
    MACRO_INTEREST_RATE_CUT = "rate_cut"
    MACRO_INTEREST_RATE_HIKE = "rate_hike"
    MACRO_GDP_RELEASE = "gdp_release"
    MACRO_JOBS_REPORT = "jobs_report"

    POLICY_REGULATION_POSITIVE = "regulation_positive"
    POLICY_REGULATION_NEGATIVE = "regulation_negative"
    POLICY_ETF_APPROVAL = "etf_approval"
    POLICY_ETF_REJECTION = "etf_rejection"
    POLICY_BAN_ANNOUNCEMENT = "ban_announcement"

    PROTOCOL_MAINNET_LAUNCH = "mainnet_launch"
    PROTOCOL_TOKEN_UNLOCK = "token_unlock"
    PROTOCOL_UPGRADE = "upgrade"
    PROTOCOL_AIRDROP = "airdrop"
    PROTOCOL_PARTNERSHIP = "partnership"
    PROTOCOL_HACK = "hack"

    RISK_EXCHANGE_COLLAPSE = "exchange_collapse"
    RISK_STABLECOIN_DEPEG = "stablecoin_depeg"
    RISK_LARGE_HACK = "large_hack"
    RISK_LIQUIDITY_CRISIS = "liquidity_crisis"
    RISK_SYSTEMIC_RISK = "systemic_risk"

    SENTIMENT_NARRATIVE_TREND = "narrative_trend"
    SENTIMENT_SOCIAL_SPIKE = "social_spike"
    SENTIMENT_KOL_BULLISH = "kol_bullish"
    SENTIMENT_KOL_BEARISH = "kol_bearish"
    SENTIMENT_FEAR_INDEX_EXTREME = "fear_index_extreme"

    @property
    def category(self) -> EventCategory:
        name = self.name
        if name.startswith("MARKET_STRUCTURE"):
            return EventCategory.MARKET_STRUCTURE
        elif name.startswith("FLOW"):
            return EventCategory.FLOW
        elif name.startswith("MACRO"):
            return EventCategory.MACRO
        elif name.startswith("POLICY"):
            return EventCategory.POLICY
        elif name.startswith("PROTOCOL"):
            return EventCategory.PROTOCOL
        elif name.startswith("RISK"):
            return EventCategory.RISK
        elif name.startswith("SENTIMENT"):
            return EventCategory.SENTIMENT
        return EventCategory.SENTIMENT

    @classmethod
    def by_category(cls, category: EventCategory) -> list["EventType"]:
        return [e for e in cls if e.category == category]

    @classmethod
    def all(cls) -> list[str]:
        return [e.value for e in cls]
