"""
Availability Authority - 可用性权威

设计原则：
- 不允许任何组件直接设置 available_time_ms
- 必须由 Authority 自动计算
- 支持不同事件类型的延迟模型
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("runtime.authority.availability")


class EventTypeLatency(Enum):
    """事件类型延迟配置"""
    CANDLE = 100      # K线延迟 (ms)
    TRADE = 50        # 成交延迟 (ms)
    ORDERBOOK = 20    # 订单簿延迟 (ms)
    FUNDING = 200     # 资金费率延迟 (ms)
    LIQUIDATION = 100 # 清算延迟 (ms)


class LatencyModel(ABC):
    """延迟模型基类"""
    
    @abstractmethod
    def get_latency_ms(self, event_type: str, timestamp_ms: int) -> int:
        """
        获取延迟时间
        
        Args:
            event_type: 事件类型
            timestamp_ms: 事件时间戳
        
        Returns:
            延迟 (ms)
        """
        pass


class FixedLatencyModel(LatencyModel):
    """固定延迟模型"""
    
    def __init__(self, default_latency_ms: int = 100):
        self._default_latency_ms = default_latency_ms
        self._latency_config: Dict[str, int] = {
            EventTypeLatency.CANDLE.name: EventTypeLatency.CANDLE.value,
            EventTypeLatency.TRADE.name: EventTypeLatency.TRADE.value,
            EventTypeLatency.ORDERBOOK.name: EventTypeLatency.ORDERBOOK.value,
            EventTypeLatency.FUNDING.name: EventTypeLatency.FUNDING.value,
            EventTypeLatency.LIQUIDATION.name: EventTypeLatency.LIQUIDATION.value,
        }
    
    def set_latency(self, event_type: str, latency_ms: int) -> None:
        """设置特定事件类型的延迟"""
        self._latency_config[event_type] = latency_ms
    
    def get_latency_ms(self, event_type: str, timestamp_ms: int) -> int:
        """获取延迟时间"""
        return self._latency_config.get(event_type, self._default_latency_ms)


class AvailabilityAuthority:
    """
    可用性权威：计算特征可用时间
    
    不允许任何组件直接设置 available_time_ms
    """
    
    def __init__(self, latency_model: Optional[LatencyModel] = None):
        self._latency_model = latency_model or FixedLatencyModel()
    
    @property
    def latency_model(self) -> LatencyModel:
        """延迟模型"""
        return self._latency_model
    
    def compute_available_time(
        self,
        event_time_ms: int,
        event_type: str,
    ) -> int:
        """
        自动计算可用时间
        
        设计原则：
        - 不允许手填
        - 必须由 Authority 自动生成
        
        Args:
            event_time_ms: 事件发生时间
            event_type: 事件类型
        
        Returns:
            available_time_ms: 自动计算的可用时间
        """
        latency_ms = self._latency_model.get_latency_ms(event_type, event_time_ms)
        available_time_ms = event_time_ms + latency_ms
        
        logger.debug(
            f"Computed available_time: event={event_time_ms}, "
            f"latency={latency_ms}, available={available_time_ms}"
        )
        
        return available_time_ms
    
    def is_available(
        self,
        available_time_ms: int,
        clock_ms: int,
    ) -> bool:
        """
        检查是否可用
        
        Args:
            available_time_ms: 事件可用时间
            clock_ms: 当前时钟时间
        
        Returns:
            是否可用
        """
        return available_time_ms <= clock_ms
    
    def validate_availability(
        self,
        available_time_ms: int,
        clock_ms: int,
        event_id: str,
    ) -> tuple[bool, Optional[str]]:
        """
        验证可用性
        
        Args:
            available_time_ms: 事件可用时间
            clock_ms: 当前时钟时间
            event_id: 事件 ID
        
        Returns:
            (是否可用, 错误信息)
        """
        if not self.is_available(available_time_ms, clock_ms):
            error_msg = (
                f"Event {event_id} not available: "
                f"available_time={available_time_ms} > clock_time={clock_ms}"
            )
            logger.warning(error_msg)
            return False, error_msg
        
        return True, None
    
    def __repr__(self) -> str:
        return f"AvailabilityAuthority(latency_model={type(self._latency_model).__name__})"
