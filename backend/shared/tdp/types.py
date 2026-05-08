"""
TDP 消息类型定义
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


class TDPMessageType(str, Enum):
    MARKET_DATA_REQUEST = "market_data_request"
    MARKET_DATA_RESPONSE = "market_data_response"
    MARKET_DATA_EVENT = "market_data_event"
    FACTOR_REQUEST = "factor_request"
    FACTOR_RESPONSE = "factor_response"
    RISK_REQUEST = "risk_request"
    RISK_RESPONSE = "risk_response"
    SIGNAL_REQUEST = "signal_request"
    SIGNAL_RESPONSE = "signal_response"
    SIGNAL_EVENT = "signal_event"
    POSITION_REQUEST = "position_request"
    POSITION_RESPONSE = "position_response"
    ORDER_REQUEST = "order_request"
    ORDER_RESPONSE = "order_response"
    ORDER_EVENT = "order_event"
    CONFIG_REQUEST = "config_request"
    CONFIG_RESPONSE = "config_response"
    STATE_REQUEST = "state_request"
    STATE_RESPONSE = "state_response"
    RISK_ALERT_EVENT = "risk_alert_event"
    SYSTEM_EVENT = "system_event"


class MessageDirection(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"


@dataclass
class TDPMeta:
    request_id: str
    source: str
    destination: Optional[str] = None
    time_generated: Optional[int] = None
    time_received: Optional[int] = None
    status: str = "OK"
    error: Optional[str] = None
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "source": self.source,
            "destination": self.destination,
            "time_generated": self.time_generated,
            "time_received": self.time_received,
            "status": self.status,
            "error": self.error,
            "version": self.version,
        }


@dataclass
class CryptoData:
    symbol: str
    price: float
    open: float
    high: float
    low: float
    volume: float
    change_24h: Optional[float] = None
    change_percent_24h: Optional[float] = None
    timestamp: Optional[int] = None
    timeframe: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "change_24h": self.change_24h,
            "change_percent_24h": self.change_percent_24h,
            "timestamp": self.timestamp,
            "timeframe": self.timeframe,
        }


@dataclass
class CommodityData:
    name: str
    price: float
    change_percent_24h: Optional[float] = None
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "price": self.price,
            "change_percent_24h": self.change_percent_24h,
            "timestamp": self.timestamp,
        }


@dataclass
class ETFData:
    symbol: str
    inflow_24h: float
    outflow_24h: float
    net_flow_24h: float
    total_aum: Optional[float] = None
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "inflow_24h": self.inflow_24h,
            "outflow_24h": self.outflow_24h,
            "net_flow_24h": self.net_flow_24h,
            "total_aum": self.total_aum,
            "timestamp": self.timestamp,
        }


@dataclass
class FundingRateData:
    symbol: str
    current: float
    next_rate: Optional[float] = None
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "current": self.current,
            "next": self.next_rate,
            "timestamp": self.timestamp,
        }


@dataclass
class EventData:
    id: str
    type: str
    subtype: Optional[str] = None
    source: Optional[str] = None
    title: str = ""
    content: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    impact: Optional[str] = None
    timestamp: Optional[int] = None
    related_assets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "subtype": self.subtype,
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "impact": self.impact,
            "timestamp": self.timestamp,
            "related_assets": self.related_assets,
        }


@dataclass
class FactorSignals:
    trend: Optional[float] = None
    flow: Optional[float] = None
    sentiment: Optional[float] = None
    macro: Optional[float] = None
    behavioral: Optional[float] = None
    historical: Optional[float] = None
    composite_score: Optional[float] = None
    regime: Optional[str] = None
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trend": self.trend,
            "flow": self.flow,
            "sentiment": self.sentiment,
            "macro": self.macro,
            "behavioral": self.behavioral,
            "historical": self.historical,
            "composite_score": self.composite_score,
            "regime": self.regime,
            "confidence": self.confidence,
        }


@dataclass
class RiskSignals:
    risk_index: int
    risk_level: str
    allow_trading: bool = True
    max_position: float = 0.3
    max_leverage: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_index": self.risk_index,
            "risk_level": self.risk_level,
            "allow_trading": self.allow_trading,
            "max_position": self.max_position,
            "max_leverage": self.max_leverage,
        }


@dataclass
class TradeSignals:
    symbol: str
    signal: str
    confidence: float
    action: str
    position_size: float
    leverage: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "signal": self.signal,
            "confidence": self.confidence,
            "action": self.action,
            "position_size": self.position_size,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }


@dataclass
class MarketData:
    crypto: Dict[str, CryptoData] = field(default_factory=dict)
    commodities: Dict[str, CommodityData] = field(default_factory=dict)
    etf: Dict[str, ETFData] = field(default_factory=dict)
    funding_rate: Dict[str, FundingRateData] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crypto": {k: v.to_dict() for k, v in self.crypto.items()},
            "commodities": {k: v.to_dict() for k, v in self.commodities.items()},
            "etf": {k: v.to_dict() for k, v in self.etf.items()},
            "funding_rate": {k: v.to_dict() for k, v in self.funding_rate.items()},
        }


@dataclass
class SignalsData:
    factors: Optional[FactorSignals] = None
    risk: Optional[RiskSignals] = None
    trade: Optional[TradeSignals] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.factors:
            result["factors"] = self.factors.to_dict()
        if self.risk:
            result["risk"] = self.risk.to_dict()
        if self.trade:
            result["trade"] = self.trade.to_dict()
        return result


MESSAGE_TYPE_MAPPING: Dict[str, Dict] = {
    "market_data_request": {"direction": "REQUEST", "response": "market_data_response"},
    "factor_request": {"direction": "REQUEST", "response": "factor_response"},
    "risk_request": {"direction": "REQUEST", "response": "risk_response"},
    "signal_request": {"direction": "REQUEST", "response": "signal_response"},
    "position_request": {"direction": "REQUEST", "response": "position_response"},
    "order_request": {"direction": "REQUEST", "response": "order_response"},
    "config_request": {"direction": "REQUEST", "response": "config_response"},
    "state_request": {"direction": "REQUEST", "response": "state_response"},
}


REQUIRED_FIELDS = {
    "market_data": ["version", "timestamp", "market"],
    "factor_request": ["version", "timestamp", "symbols"],
    "execution_request": ["version", "timestamp", "order"],
}


FIELD_TYPES = {
    "price": float,
    "volume": float,
    "timestamp": int,
    "sentiment_score": float,
    "change_percent": float,
}


FIELD_RANGES = {
    "sentiment_score": (-1.0, 1.0),
    "change_percent": (-1.0, 1.0),
    "leverage": (1, 125),
    "position_size": (0.0, 1.0),
}