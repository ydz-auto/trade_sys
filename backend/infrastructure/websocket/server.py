"""
WebSocket 工具 - 提供通用WebSocket类型和工具
注意：这只是类型定义和简单工具，FastAPI的WebSocket在 data_service/websocket/ 中使用
"""

from dataclasses import dataclass, field
from typing import Set, Dict, Any
import time


@dataclass
class WSMessage:
    """WebSocket消息"""
    type: str
    channel: str
    data: Any
    timestamp: float = field(default_factory=time.time)


class WSChannel:
    """WebSocket频道常量"""

    CHANNEL_PRICES = "prices"
    CHANNEL_NEWS = "news"
    CHANNEL_ETFS = "etfs"
    CHANNEL_MACRO = "macro"
    CHANNEL_ALERTS = "alerts"
    CHANNEL_TRADER = "trader"
    CHANNEL_SYSTEM = "system"

    ALL_CHANNELS = {
        CHANNEL_PRICES: "实时价格",
        CHANNEL_NEWS: "新闻资讯",
        CHANNEL_ETFS: "ETF数据",
        CHANNEL_MACRO: "宏观数据",
        CHANNEL_ALERTS: "预警通知",
        CHANNEL_TRADER: "KOL观点",
        CHANNEL_SYSTEM: "系统消息"
    }


__all__ = ["WSMessage", "WSChannel"]
