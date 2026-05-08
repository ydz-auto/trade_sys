"""
Signal Schemas - 信号数据模型定义
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class SignalType(str, Enum):
    ETF_INFLOW = "ETF_INFLOW"
    ETF_OUTFLOW = "ETF_OUTFLOW"
    MACRO_CHANGE = "MACRO_CHANGE"
    LIQUIDATION = "LIQUIDATION"
    REGULATORY = "REGULATORY"
    HACK_SECURITY = "HACK_SECURITY"
    WHALE_MOVEMENT = "WHALE_MOVEMENT"
    EXCHANGE_FLOW = "EXCHANGE_FLOW"
    ONCHAIN_ACTIVITY = "ONCHAIN_ACTIVITY"
    SOCIAL_SENTIMENT = "SOCIAL_SENTIMENT"
    NEWS_EVENT = "NEWS_EVENT"
    MARKET_REGIME = "MARKET_REGIME"
    BLACK_SWAN = "BLACK_SWAN"
    COMPOSITE = "COMPOSITE"


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class DataSource(str, Enum):
    NEWS = "news"
    SOCIAL = "social"
    ONCHAIN = "onchain"
    ETF = "etf"
    MACRO = "macro"
    EXCHANGE = "exchange"
    TRADER = "trader"


class Signal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_type: SignalType
    asset: str = "BTC"
    direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    consensus: float = Field(ge=0.0, le=1.0)
    strength: float = Field(ge=0.0, le=1.0)
    sources: List[str] = Field(default_factory=list)
    source_count: int = 0
    total_sources: int = 7
    event_type: str = "NORMAL"
    summary: str = ""
    timestamp: float = Field(default_factory=datetime.now().timestamp)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    event_ids: List[str] = Field(default_factory=list)
    quality_score: float = Field(ge=0.0, le=1.0, default=0.5)


class EventGroup(BaseModel):
    group_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    asset: str
    direction: Direction
    events: List[Dict[str, Any]] = Field(default_factory=list)
    window_start: float
    window_end: float
    source_count: int = 0
    avg_strength: float = 0.0
    avg_confidence: float = 0.0
    data_quality: float = 0.5


class EventWindowConfig(BaseModel):
    window_seconds: int = 300
    min_consensus: float = 0.3
    consensus_weight: float = 0.4
    strength_weight: float = 0.3
    quality_weight: float = 0.2
    market_weight: float = 0.1
