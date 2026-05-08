"""
Event Schemas - 事件数据模型定义

⚠️ 重要：所有 EventType 和 Direction 使用 domain.event 中的定义
这是系统唯一标准语言
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from domain.event.event_type import EventType
from domain.event.direction import Direction


class DataSource(str):
    NEWS = "news"
    SOCIAL = "social"
    ONCHAIN = "onchain"
    ETF = "etf"
    MACRO = "macro"
    EXCHANGE = "exchange"
    TRADER = "trader"


class RawDataType(str):
    NEWS = "news"
    SOCIAL = "social"
    TRADER_OPINION = "trader_opinion"
    ETF_FLOW = "etf_flow"
    ONCHAIN = "onchain"
    MACRO = "macro"


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.SENTIMENT_NARRATIVE_TREND
    asset: str = "BTC"
    direction: Direction = Direction.NEUTRAL
    strength: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    sources: List[str] = Field(default_factory=list)
    source_details: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: float = Field(default_factory=datetime.now().timestamp)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_data_refs: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class RawDataMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_type: RawDataType
    source: str
    content: Dict[str, Any]
    raw_content: str = ""
    title: str = ""
    timestamp: float = Field(default_factory=datetime.now().timestamp)
    collected_at: float = Field(default_factory=datetime.now().timestamp)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventExtractionResult(BaseModel):
    event_type: EventType
    asset: str
    direction: Direction
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = ""
    affected_assets: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NewsExtractionPrompt:
    TEMPLATE = """你是一个专业的加密货币事件提取专家。
从以下新闻内容中提取结构化事件信息，返回JSON格式：
{
    "event_type": "事件类型（见下方列表）",
    "asset": "主要相关资产，如BTC/ETH",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（提取置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{}}
}

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


class SocialExtractionPrompt:
    TEMPLATE = """你是一个加密货币交易员言论分析专家。
从以下交易员言论中提取结构化事件信息，返回JSON格式：
{
    "event_type": "kol_bullish/kol_bearish/narrative_trend/social_spike",
    "asset": "主要相关资产",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（提取置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{"trader": "交易员名称", "platform": "twitter/reddit"}}
}

交易员: {trader_name}
平台: {platform}
内容: {content}
"""


class TraderOpinionExtractionPrompt:
    TEMPLATE = """你是一个加密货币交易员言论分析专家。
从以下交易员言论中提取结构化事件信息，返回JSON格式：
{
    "event_type": "kol_bullish/kol_bearish/narrative_trend/social_spike",
    "asset": "主要相关资产",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（提取置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{"trader": "交易员名称", "time_horizon": "short/medium/long"}}
}

交易员: {trader_name}
内容: {content}
"""


class EtfFlowExtractionPrompt:
    TEMPLATE = """你是一个ETF流量分析专家。
从以下ETF数据中提取结构化事件信息，返回JSON格式：
{
    "event_type": "etf_inflow/etf_outflow",
    "asset": "ETF标的资产，如BTC/ETH",
    "direction": "bullish（流入=看涨，流出=看跌）",
    "strength": 0.0-1.0（流量强度，1.0表示大幅流入/流出）,
    "confidence": 0.0-1.0（数据置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC"],
    "metadata": {{"net_flow": 数值, "aum": 数值, "flow_type": "inflow/outflow"}}
}

ETF数据: {content}
"""


class OnChainExtractionPrompt:
    TEMPLATE = """你是一个链上数据分析专家。
从以下链上数据中提取结构化事件信息，返回JSON格式：
{
    "event_type": "whale_transfer/stablecoin_inflow/stablecoin_outflow/exchange_net_inflow",
    "asset": "相关资产",
    "direction": "bullish/bearish/neutral",
    "strength": 0.0-1.0（事件强度）,
    "confidence": 0.0-1.0（数据置信度）,
    "summary": "一句话事件摘要",
    "affected_assets": ["BTC", "ETH", ...],
    "metadata": {{"wallet_label": "标签", "net_flow": 数值}}
}

链上数据: {content}
"""
