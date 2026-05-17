"""
Event Schema Registry - 统一事件 Schema 管理

确保所有事件符合统一的 Schema 规范

Schema 规范：
1. 必须有 event_id, trace_id, event_type
2. timestamp 统一为 ISO 格式
3. symbol 统一格式为 BTCUSDT
4. 所有事件都继承 BaseEvent
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, Type, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("schema_registry")


class SchemaVersion(str, Enum):
    """Schema 版本"""
    V1_0 = "1.0"
    V2_0 = "2.0"


class EventType(str, Enum):
    """事件类型枚举"""
    RAW_DATA = "raw_data"
    MARKET = "market"
    EVENT = "event"
    SIGNAL = "signal"
    DECISION = "decision"
    RISK_CHECKED = "risk_checked"
    ORDER = "order"
    FILL = "fill"
    PNL = "pnl"
    ERROR = "error"
    SYSTEM = "system"


class EventSource(str, Enum):
    """事件来源"""
    DATA_WORKER = "data_worker"
    STRATEGY_WORKER = "strategy_worker"
    EXECUTION_WORKER = "execution_worker"
    PROJECTION_WORKER = "projection_worker"
    EXTERNAL = "external"
    SYSTEM = "system"


class SymbolFormat(str, Enum):
    """Symbol 格式"""
    STANDARD = "BTCUSDT"
    ALT = "BTC/USDT"
    SPOT = "BTC-USDT"


class BaseEventV2(BaseModel):
    """
    统一事件基类 v2
    
    所有事件都必须继承此类
    """
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        ser_json_timedelta="iso8601",
    )
    
    event_id: str = Field(description="事件唯一ID")
    event_type: EventType = Field(description="事件类型")
    
    trace_id: str = Field(description="链路追踪ID")
    parent_event_id: Optional[str] = Field(default=None, description="父事件ID")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="事件时间")
    version: SchemaVersion = Field(default=SchemaVersion.V2_0, description="Schema 版本")
    
    source: EventSource = Field(default=EventSource.SYSTEM, description="事件来源")
    symbol: str = Field(default="BTCUSDT", description="交易品种")
    exchange: str = Field(default="binance", description="交易所")
    timeframe: str = Field(default="4h", description="时间周期")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    
    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, v):
        if isinstance(v, list):
            v = v[0] if v else "BTC"
        if not v:
            return "BTCUSDT"
        v = str(v).upper()
        if "/" in v:
            v = v.replace("/", "")
        if "-" in v:
            v = v.replace("-", "")
        if not v.endswith("USDT") and not v.endswith("BTC"):
            v = f"{v}USDT"
        return v
    
    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v or datetime.utcnow()
    
    def to_canonical_dict(self) -> Dict[str, Any]:
        """转换为规范字典"""
        d = self.model_dump()
        d["timestamp"] = self.timestamp.isoformat()
        if isinstance(d.get("event_type"), EventType):
            d["event_type"] = d["event_type"].value
        if isinstance(d.get("source"), EventSource):
            d["source"] = d["source"].value
        return d
    
    def derive_child(self, event_type: EventType, source: EventSource, **kwargs) -> "BaseEventV2":
        """派生子事件"""
        return BaseEventV2(
            event_id=f"evt_{id(self)}",
            event_type=event_type,
            trace_id=self.trace_id,
            parent_event_id=self.event_id,
            source=source,
            symbol=self.symbol,
            exchange=self.exchange,
            timeframe=self.timeframe,
            **kwargs
        )


class RawDataEventV2(BaseEventV2):
    """原始数据事件"""
    event_type: EventType = EventType.RAW_DATA
    source: EventSource = EventSource.DATA_WORKER
    
    data_type: str = Field(default="news", description="数据类型: news/tweet/trade/kline")
    data: Dict[str, Any] = Field(default_factory=dict, description="原始数据内容")
    data_source: str = Field(default="", description="数据来源名称")


class MarketEventV2(BaseEventV2):
    """市场数据事件"""
    event_type: EventType = EventType.MARKET
    source: EventSource = EventSource.DATA_WORKER
    
    market_type: str = Field(default="spot", description="市场类型: spot/futures/swap")
    
    open: Optional[float] = Field(default=None, description="开盘价")
    high: Optional[float] = Field(default=None, description="最高价")
    low: Optional[float] = Field(default=None, description="最低价")
    close: Optional[float] = Field(default=None, description="收盘价")
    volume: Optional[float] = Field(default=None, description="成交量")
    
    price: Optional[float] = Field(default=None, description="当前价格")
    quantity: Optional[float] = Field(default=None, description="数量")


class AnalysisEventV2(BaseEventV2):
    """分析事件"""
    event_type: EventType = EventType.EVENT
    source: EventSource = EventSource.STRATEGY_WORKER
    
    event_category: str = Field(default="unknown", description="事件分类")
    direction: str = Field(default="neutral", description="方向: bullish/bearish/neutral")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="事件强度")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")
    
    raw_event_type: str = Field(default="", description="原始事件类型")
    affected_symbols: List[str] = Field(default_factory=list, description="受影响的品种")


class SignalEventV2(BaseEventV2):
    """信号事件"""
    event_type: EventType = EventType.SIGNAL
    source: EventSource = EventSource.STRATEGY_WORKER
    
    signal_name: str = Field(default="", description="信号名称")
    direction: str = Field(default="neutral", description="方向")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="信号强度")
    
    event_count: int = Field(default=0, description="聚合的事件数量")
    event_types: List[str] = Field(default_factory=list, description="触发的事件类型")
    
    factors: Dict[str, float] = Field(default_factory=dict, description="因子贡献")


class DecisionEventV2(BaseEventV2):
    """决策事件"""
    event_type: EventType = EventType.DECISION
    source: EventSource = EventSource.STRATEGY_WORKER
    
    decision_id: str = Field(description="决策ID")
    
    action: str = Field(description="动作: LONG/SHORT/HOLD/CLOSE")
    quantity: float = Field(default=0.0, ge=0.0, description="数量")
    price: Optional[float] = Field(default=None, description="价格")
    
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reason: str = Field(default="", description="决策原因")
    
    strategy_id: str = Field(default="", description="策略ID")
    signal_id: Optional[str] = Field(default=None, description="关联信号ID")
    
    @property
    def is_buy(self) -> bool:
        return self.action.upper() in ("LONG", "BUY")
    
    @property
    def is_sell(self) -> bool:
        return self.action.upper() in ("SHORT", "SELL")
    
    @property
    def is_hold(self) -> bool:
        return self.action.upper() == "HOLD"


class RiskCheckedEventV2(BaseEventV2):
    """风控检查事件"""
    event_type: EventType = EventType.RISK_CHECKED
    source: EventSource = EventSource.EXECUTION_WORKER
    
    original_decision_id: str = Field(description="原始决策ID")
    approved: bool = Field(default=False, description="是否通过风控")
    risk_level: str = Field(default="low", description="风险等级")
    
    rejection_reason: Optional[str] = Field(default=None, description="拒绝原因")
    warnings: List[str] = Field(default_factory=list, description="警告")
    check_results: Dict[str, Any] = Field(default_factory=dict, description="检查详情")


class OrderEventV2(BaseEventV2):
    """订单事件"""
    event_type: EventType = EventType.ORDER
    source: EventSource = EventSource.EXECUTION_WORKER
    
    order_id: str = Field(description="订单ID")
    client_order_id: Optional[str] = Field(default=None, description="客户端订单ID")
    
    order_type: str = Field(default="limit", description="订单类型")
    side: str = Field(description="方向: buy/sell")
    
    price: Optional[float] = Field(default=None, description="价格")
    quantity: float = Field(description="数量")
    filled_quantity: float = Field(default=0.0, description="已成交数量")
    
    status: str = Field(default="new", description="状态")
    
    decision_id: Optional[str] = Field(default=None, description="关联决策ID")


class FillEventV2(BaseEventV2):
    """成交事件"""
    event_type: EventType = EventType.FILL
    source: EventSource = EventSource.EXECUTION_WORKER
    
    fill_id: str = Field(description="成交ID")
    order_id: str = Field(description="订单ID")
    
    side: str = Field(description="方向: buy/sell")
    price: float = Field(description="成交价格")
    quantity: float = Field(description="成交数量")
    fee: float = Field(default=0.0, description="手续费")
    
    realized_pnl: Optional[float] = Field(default=None, description="已实现盈亏")


class SystemEventV2(BaseEventV2):
    """系统事件"""
    event_type: EventType = EventType.SYSTEM
    source: EventSource = EventSource.SYSTEM
    
    system_type: str = Field(description="系统类型")
    severity: str = Field(default="info", description="严重程度")
    message: str = Field(default="", description="消息")


EVENT_CLASS_MAP_V2: Dict[EventType, Type[BaseEventV2]] = {
    EventType.RAW_DATA: RawDataEventV2,
    EventType.MARKET: MarketEventV2,
    EventType.EVENT: AnalysisEventV2,
    EventType.SIGNAL: SignalEventV2,
    EventType.DECISION: DecisionEventV2,
    EventType.RISK_CHECKED: RiskCheckedEventV2,
    EventType.ORDER: OrderEventV2,
    EventType.FILL: FillEventV2,
    EventType.SYSTEM: SystemEventV2,
}


class EventSchemaRegistry:
    """
    Event Schema Registry
    
    统一管理所有事件的 Schema
    """
    
    def __init__(self):
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._validators: Dict[str, callable] = {}
        self._transformers: Dict[str, callable] = {}
        
        self._register_all_schemas()
    
    def _register_all_schemas(self) -> None:
        """注册所有 Schema"""
        for event_type, event_class in EVENT_CLASS_MAP_V2.items():
            self._schemas[event_type.value] = {
                "class": event_class,
                "version": SchemaVersion.V2_0,
                "fields": list(event_class.model_fields.keys()),
            }
    
    def get_schema(self, event_type: EventType) -> Dict[str, Any]:
        """获取 Schema"""
        return self._schemas.get(event_type.value, {})
    
    def parse_event(self, data: Dict[str, Any]) -> BaseEventV2:
        """解析事件"""
        event_type_str = data.get("event_type")
        if not event_type_str:
            raise ValueError("Missing event_type field")
        
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            raise ValueError(f"Unknown event_type: {event_type_str}")
        
        event_class = EVENT_CLASS_MAP_V2.get(event_type)
        if not event_class:
            raise ValueError(f"No schema for event_type: {event_type}")
        
        return event_class(**data)
    
    def validate_event(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证事件"""
        try:
            event = self.parse_event(data)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def transform_to_canonical(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """转换为规范格式"""
        try:
            event = self.parse_event(data)
            return event.to_canonical_dict()
        except Exception as e:
            logger.error(f"Transform failed: {e}")
            return data
    
    def register_validator(self, event_type: str, validator: callable) -> None:
        """注册自定义验证器"""
        self._validators[event_type] = validator
    
    def register_transformer(self, event_type: str, transformer: callable) -> None:
        """注册自定义转换器"""
        self._transformers[event_type] = transformer
    
    def get_all_event_types(self) -> List[str]:
        """获取所有事件类型"""
        return list(self._schemas.keys())


_schema_registry: Optional[EventSchemaRegistry] = None


def get_schema_registry() -> EventSchemaRegistry:
    """获取 Schema Registry 单例"""
    global _schema_registry
    if _schema_registry is None:
        _schema_registry = EventSchemaRegistry()
    return _schema_registry
