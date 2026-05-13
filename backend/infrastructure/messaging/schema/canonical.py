"""
统一事件模型 - Canonical Event Schema

所有事件的基础体系，支持全链路追踪和 schema 演进

设计原则：
1. 所有事件都有 trace_id，全链路透传
2. 统一 symbol, exchange 字段格式
3. Schema 版本化，支持演进
4. 事件类型枚举化
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator


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


class EventSource(str, Enum):
    """事件来源"""
    DATA_WORKER = "data_worker"
    STRATEGY_WORKER = "strategy_worker"
    EXECUTION_WORKER = "execution_worker"
    EXTERNAL = "external"
    SYSTEM = "system"


def generate_trace_id() -> str:
    """生成 trace_id"""
    return f"trc_{uuid.uuid4().hex[:16]}"


def generate_event_id() -> str:
    """生成 event_id"""
    return f"evt_{uuid.uuid4().hex[:16]}"


class BaseEvent(BaseModel):
    """
    统一事件基类
    
    所有事件都必须继承此类，确保：
    - trace_id 全链路透传
    - 统一的字段格式
    - 可追溯性
    """
    
    event_id: str = Field(default_factory=generate_event_id, description="事件唯一ID")
    trace_id: str = Field(default_factory=generate_trace_id, description="链路追踪ID")
    parent_event_id: Optional[str] = Field(default=None, description="父事件ID")
    
    event_type: EventType = Field(description="事件类型")
    source: EventSource = Field(default=EventSource.SYSTEM, description="事件来源")
    
    symbol: str = Field(default="BTC", description="交易品种，统一格式如 BTCUSDT")
    exchange: str = Field(default="binance", description="交易所")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="事件时间")
    version: str = Field(default="1.0", description="Schema 版本")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            EventType: lambda v: v.value,
            EventSource: lambda v: v.value,
        }
    
    def derive_child(self, event_type: EventType, source: EventSource, **kwargs) -> "BaseEvent":
        """
        派生子事件，继承 trace_id
        """
        return BaseEvent(
            trace_id=self.trace_id,
            parent_event_id=self.event_id,
            event_type=event_type,
            source=source,
            symbol=self.symbol,
            exchange=self.exchange,
            **kwargs
        )
    
    def to_trace_dict(self) -> Dict[str, Any]:
        """转换为可追踪的字典"""
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
        }


class RawDataEvent(BaseEvent):
    """
    原始数据事件
    
    data_worker 采集的原始数据
    """
    
    event_type: EventType = EventType.RAW_DATA
    source: EventSource = EventSource.DATA_WORKER
    
    data_type: str = Field(default="news", description="数据类型: news/tweet/trade/kline")
    data: Dict[str, Any] = Field(default_factory=dict, description="原始数据内容")
    data_source: str = Field(default="", description="数据来源名称")
    
    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, v):
        if isinstance(v, list):
            return v[0] if v else "BTC"
        return v or "BTC"


class MarketEvent(BaseEvent):
    """
    市场数据事件
    
    行情、K线、成交等
    """
    
    event_type: EventType = EventType.MARKET
    source: EventSource = EventSource.DATA_WORKER
    
    market_type: str = Field(default="spot", description="市场类型: spot/futures/swap")
    timeframe: str = Field(default="1m", description="时间周期")
    
    open: Optional[float] = Field(default=None, description="开盘价")
    high: Optional[float] = Field(default=None, description="最高价")
    low: Optional[float] = Field(default=None, description="最低价")
    close: Optional[float] = Field(default=None, description="收盘价")
    volume: Optional[float] = Field(default=None, description="成交量")
    
    price: Optional[float] = Field(default=None, description="当前价格")
    quantity: Optional[float] = Field(default=None, description="数量")


class AnalysisEvent(BaseEvent):
    """
    分析事件
    
    事件检测、情感分析等
    """
    
    event_type: EventType = EventType.EVENT
    source: EventSource = EventSource.STRATEGY_WORKER
    
    event_category: str = Field(default="unknown", description="事件分类")
    direction: str = Field(default="neutral", description="方向: bullish/bearish/neutral")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="事件强度")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")
    
    raw_event_type: str = Field(default="", description="原始事件类型")
    affected_symbols: List[str] = Field(default_factory=list, description="受影响的品种")


class SignalEvent(BaseEvent):
    """
    信号事件
    
    融合后产生的交易信号
    """
    
    event_type: EventType = EventType.SIGNAL
    source: EventSource = EventSource.STRATEGY_WORKER
    
    signal_name: str = Field(default="", description="信号名称，如 BTC_BULLISH")
    direction: str = Field(default="neutral", description="方向: bullish/bearish/neutral")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="信号强度")
    
    event_count: int = Field(default=0, description="聚合的事件数量")
    event_types: List[str] = Field(default_factory=list, description="触发的事件类型")
    
    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and self.event_count >= 3
    
    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.6 and self.event_count >= 2


class DecisionEvent(BaseEvent):
    """
    决策事件
    
    策略产生的交易决策
    """
    
    event_type: EventType = EventType.DECISION
    source: EventSource = EventSource.STRATEGY_WORKER
    
    decision_id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    
    action: str = Field(description="动作: LONG/SHORT/HOLD/CLOSE")
    quantity: float = Field(default=0.0, ge=0.0, description="数量")
    price: Optional[float] = Field(default=None, description="价格，None 表示市价单")
    
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    reason: str = Field(default="", description="决策原因")
    
    strategy_id: str = Field(default="", description="策略ID")
    
    @property
    def is_buy(self) -> bool:
        return self.action.upper() in ("LONG", "BUY")
    
    @property
    def is_sell(self) -> bool:
        return self.action.upper() in ("SHORT", "SELL")
    
    @property
    def is_hold(self) -> bool:
        return self.action.upper() == "HOLD"
    
    @property
    def is_actionable(self) -> bool:
        return not self.is_hold and self.confidence >= 0.5


class RiskCheckedEvent(BaseEvent):
    """
    风控检查事件
    
    风控检查后的决策
    """
    
    event_type: EventType = EventType.RISK_CHECKED
    source: EventSource = EventSource.EXECUTION_WORKER
    
    original_decision_id: str = Field(description="原始决策ID")
    approved: bool = Field(default=False, description="是否通过风控")
    risk_level: str = Field(default="low", description="风险等级: low/medium/high/extreme")
    
    rejection_reason: Optional[str] = Field(default=None, description="拒绝原因")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    check_results: Dict[str, Any] = Field(default_factory=dict, description="检查结果详情")
    
    @property
    def can_execute(self) -> bool:
        return self.approved


class OrderEvent(BaseEvent):
    """
    订单事件
    
    订单创建、更新、取消
    """
    
    event_type: EventType = EventType.ORDER
    source: EventSource = EventSource.EXECUTION_WORKER
    
    order_id: str = Field(description="订单ID")
    client_order_id: Optional[str] = Field(default=None, description="客户端订单ID")
    
    order_type: str = Field(default="limit", description="订单类型: limit/market")
    side: str = Field(description="方向: buy/sell")
    
    price: Optional[float] = Field(default=None, description="价格")
    quantity: float = Field(description="数量")
    filled_quantity: float = Field(default=0.0, description="已成交数量")
    
    status: str = Field(default="new", description="状态: new/filled/cancelled/rejected")
    
    decision_id: Optional[str] = Field(default=None, description="关联的决策ID")


class FillEvent(BaseEvent):
    """
    成交事件
    
    订单成交
    """
    
    event_type: EventType = EventType.FILL
    source: EventSource = EventSource.EXECUTION_WORKER
    
    fill_id: str = Field(default_factory=lambda: f"fill_{uuid.uuid4().hex[:12]}")
    order_id: str = Field(description="订单ID")
    
    side: str = Field(description="方向: buy/sell")
    price: float = Field(description="成交价格")
    quantity: float = Field(description="成交数量")
    fee: float = Field(default=0.0, description="手续费")
    fee_currency: str = Field(default="USDT", description="手续费币种")
    
    realized_pnl: Optional[float] = Field(default=None, description="已实现盈亏")


class PNLEvent(BaseEvent):
    """
    盈亏事件
    
    持仓盈亏更新
    """
    
    event_type: EventType = EventType.PNL
    source: EventSource = EventSource.EXECUTION_WORKER
    
    position_id: str = Field(description="持仓ID")
    
    unrealized_pnl: float = Field(default=0.0, description="未实现盈亏")
    realized_pnl: float = Field(default=0.0, description="已实现盈亏")
    
    entry_price: float = Field(description="开仓价格")
    current_price: float = Field(description="当前价格")
    quantity: float = Field(description="持仓数量")
    
    pnl_percent: float = Field(default=0.0, description="盈亏百分比")


class ErrorEvent(BaseEvent):
    """
    错误事件
    
    系统错误、异常
    """
    
    event_type: EventType = EventType.ERROR
    
    error_code: str = Field(default="UNKNOWN", description="错误码")
    error_message: str = Field(default="", description="错误信息")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="错误详情")
    
    stack_trace: Optional[str] = Field(default=None, description="堆栈跟踪")
    recoverable: bool = Field(default=False, description="是否可恢复")


EVENT_CLASS_MAP = {
    EventType.RAW_DATA: RawDataEvent,
    EventType.MARKET: MarketEvent,
    EventType.EVENT: AnalysisEvent,
    EventType.SIGNAL: SignalEvent,
    EventType.DECISION: DecisionEvent,
    EventType.RISK_CHECKED: RiskCheckedEvent,
    EventType.ORDER: OrderEvent,
    EventType.FILL: FillEvent,
    EventType.PNL: PNLEvent,
    EventType.ERROR: ErrorEvent,
}


def parse_event(data: Dict[str, Any]) -> BaseEvent:
    """
    解析事件数据为对应的事件类型
    """
    event_type = data.get("event_type")
    if event_type is None:
        raise ValueError("Missing event_type field")
    
    event_class = EVENT_CLASS_MAP.get(EventType(event_type))
    if event_class is None:
        raise ValueError(f"Unknown event_type: {event_type}")
    
    return event_class(**data)
