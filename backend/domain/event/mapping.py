from domain.event.event_type import EventType
from domain.event.direction import Direction

EVENT_DIRECTION_MAP: dict[EventType, Direction] = {
    EventType.FLOW_ETF_INFLOW: Direction.BULLISH,
    EventType.FLOW_ETF_OUTFLOW: Direction.BEARISH,
    EventType.FLOW_STABLECOIN_INFLOW: Direction.BULLISH,
    EventType.FLOW_STABLECOIN_OUTFLOW: Direction.BEARISH,
    EventType.FLOW_EXCHANGE_NET_INFLOW: Direction.BEARISH,
    EventType.FLOW_EXCHANGE_NET_OUTFLOW: Direction.BULLISH,
    EventType.FLOW_WHALE_TRANSFER: Direction.NEUTRAL,
    EventType.MARKET_STRUCTURE_LIQUIDATION: Direction.BEARISH,
    EventType.MARKET_STRUCTURE_FUNDING_RATE_SPIKE: Direction.NEUTRAL,
    EventType.MARKET_STRUCTURE_OPEN_INTEREST_SPIKE: Direction.NEUTRAL,
    EventType.MARKET_STRUCTURE_ORDERBOOK_IMBALANCE: Direction.NEUTRAL,
    EventType.MARKET_STRUCTURE_VOLATILITY_EXPANSION: Direction.NEUTRAL,
    EventType.MACRO_INTEREST_RATE_CUT: Direction.BULLISH,
    EventType.MACRO_INTEREST_RATE_HIKE: Direction.BEARISH,
    EventType.MACRO_CPI_RELEASE: Direction.NEUTRAL,
    EventType.MACRO_FOMC_RATE_DECISION: Direction.NEUTRAL,
    EventType.MACRO_GDP_RELEASE: Direction.NEUTRAL,
    EventType.MACRO_JOBS_REPORT: Direction.NEUTRAL,
    EventType.POLICY_REGULATION_POSITIVE: Direction.BULLISH,
    EventType.POLICY_REGULATION_NEGATIVE: Direction.BEARISH,
    EventType.POLICY_ETF_APPROVAL: Direction.BULLISH,
    EventType.POLICY_ETF_REJECTION: Direction.BEARISH,
    EventType.POLICY_BAN_ANNOUNCEMENT: Direction.BEARISH,
    EventType.PROTOCOL_MAINNET_LAUNCH: Direction.BULLISH,
    EventType.PROTOCOL_TOKEN_UNLOCK: Direction.BEARISH,
    EventType.PROTOCOL_UPGRADE: Direction.BULLISH,
    EventType.PROTOCOL_AIRDROP: Direction.BULLISH,
    EventType.PROTOCOL_PARTNERSHIP: Direction.BULLISH,
    EventType.PROTOCOL_HACK: Direction.BEARISH,
    EventType.RISK_EXCHANGE_COLLAPSE: Direction.BEARISH,
    EventType.RISK_STABLECOIN_DEPEG: Direction.BEARISH,
    EventType.RISK_LARGE_HACK: Direction.BEARISH,
    EventType.RISK_LIQUIDITY_CRISIS: Direction.BEARISH,
    EventType.RISK_SYSTEMIC_RISK: Direction.BEARISH,
    EventType.SENTIMENT_NARRATIVE_TREND: Direction.NEUTRAL,
    EventType.SENTIMENT_SOCIAL_SPIKE: Direction.NEUTRAL,
    EventType.SENTIMENT_KOL_BULLISH: Direction.BULLISH,
    EventType.SENTIMENT_KOL_BEARISH: Direction.BEARISH,
    EventType.SENTIMENT_FEAR_INDEX_EXTREME: Direction.NEUTRAL,
}


def get_direction(event_type: EventType) -> Direction:
    return EVENT_DIRECTION_MAP.get(event_type, Direction.NEUTRAL)
