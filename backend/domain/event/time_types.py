"""
Event Time Types - 事件时间类型定义

纯 domain 类型，不包含运行时状态管理。
时间管理器（EventTimeManager）在 runtime/kernel/event/event_time_manager.py
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class EventSource(str, Enum):
    """事件来源"""
    EXCHANGE = "exchange"       # 交易所直接推送
    WEBSOCKET = "websocket"     # WebSocket 接收
    REST_API = "rest_api"       # REST API 获取
    REPLAY = "replay"           # 回放数据
    SIMULATED = "simulated"     # 模拟数据


@dataclass
class EventTimeRecord:
    """
    事件时间记录

    核心概念：
    - exchange_time: 交易所时间（事件实际发生时间）
    - receive_time: 本地接收时间
    - available_at: 可用时间（考虑延迟后，特征可以被使用的时间）
    - processing_delay: 处理延迟
    """
    event_id: str
    event_type: str

    exchange_time: int          # 交易所时间
    receive_time: int           # 本地接收时间
    available_at: int           # 可用时间

    source: EventSource

    network_delay_ms: int = 0   # 网络延迟
    processing_delay_ms: int = 0 # 处理延迟

    symbol: str = ""
    exchange: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.available_at == 0:
            self.available_at = self.receive_time + self.processing_delay_ms

    def is_available_at(self, query_time: int) -> bool:
        """检查在指定时间是否可用"""
        return query_time >= self.available_at

    def get_total_delay_ms(self) -> int:
        """获取总延迟"""
        return self.receive_time - self.exchange_time + self.processing_delay_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "exchange_time": self.exchange_time,
            "receive_time": self.receive_time,
            "available_at": self.available_at,
            "source": self.source.value,
            "network_delay_ms": self.network_delay_ms,
            "processing_delay_ms": self.processing_delay_ms,
            "total_delay_ms": self.get_total_delay_ms(),
            "symbol": self.symbol,
            "exchange": self.exchange,
        }


@dataclass
class EventTimeConfig:
    """事件时间配置"""
    default_network_delay_ms: int = 100
    default_processing_delay_ms: int = 50

    max_acceptable_delay_ms: int = 5000

    simulate_delay_in_replay: bool = True
    strict_time_order: bool = True
