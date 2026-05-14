"""
Dashboard Schemas - Trading Dashboard Models
"""
from pydantic import BaseModel
from typing import Dict, List, Optional


class PriceItem(BaseModel):
    symbol: str
    price: float
    change24h: float
    volume_24h: float
    exchange: str


class FactorItem(BaseModel):
    type: str
    name: str
    nameEn: str
    weight: float
    value: float
    confidence: int
    color: str


class RegimeState(BaseModel):
    state: str
    confidence: float
    trendStrength: Optional[float] = None


class RiskComponent(BaseModel):
    volatility: float
    flow: float
    sentiment: float
    macro: float


class RiskIndex(BaseModel):
    total: int
    level: str
    components: RiskComponent


class Signal(BaseModel):
    action: str
    confidence: float
    riskLevel: str
    reason: str


class PositionItem(BaseModel):
    symbol: str
    side: str
    size: float
    entryPrice: float
    leverage: int
    pnl: float
    stopLoss: Optional[float] = None
    takeProfit: Optional[float] = None


class NewsItem(BaseModel):
    id: str
    title: str
    content: str
    source: str
    sentiment: str
    sentiment_score: float
    published: int
    url: Optional[str] = None


class WeightVersion(BaseModel):
    version: str
    timestamp: str
    weights: Dict[str, float]
    author: str


class DataSourceStatus(BaseModel):
    name: str
    status: str
    lastUpdate: str
    recordsCount: int


class TraderItem(BaseModel):
    id: str
    name: str
    platform: str
    followers: int
    sentiment: float
    recentPosition: str
    symbol: str
    winRate: float
    avatar: Optional[str] = None


class SocialPost(BaseModel):
    id: str
    platform: str
    author: str
    authorAvatar: Optional[str] = None
    content: str
    sentiment: float
    likes: int
    time: str
    timestamp: str
    symbols: List[str]


class MacroData(BaseModel):
    gold: Optional[Dict[str, float]] = None
    usd_index: Optional[Dict[str, float]] = None
    oil: Optional[Dict[str, float]] = None


class EtfData(BaseModel):
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    confidence: float


class FearGreedData(BaseModel):
    value: int
    classification: str
    timestamp: str


class DashboardResponse(BaseModel):
    prices: List[PriceItem]
    compositeScore: float
    regime: RegimeState
    risk: RiskIndex
    signal: Signal
    factors: List[FactorItem]
    positions: List[PositionItem]
    weightVersions: List[WeightVersion]
    dataSources: List[DataSourceStatus]
    traders: List[TraderItem]
    socialPosts: List[SocialPost]
    news: List[NewsItem]
    macro: Optional[MacroData] = None
    fearGreed: Optional[FearGreedData] = None
    etf: Optional[EtfData] = None
