"""
Authority System - 权威系统组合入口

整合三个核心 Authority：
- ClockAuthority: 时钟权威
- AvailabilityAuthority: 可用性权威
- OrderingAuthority: 顺序权威

提供一站式事件处理入口
"""

from typing import Dict, Optional, Tuple, Any

from runtime.kernel.authority.clock_authority import ClockAuthority, ClockMode
from runtime.kernel.authority.availability_authority import (
    AvailabilityAuthority,
    LatencyModel,
)
from runtime.kernel.authority.ordering_authority import OrderingAuthority
from domain.event.protocol import (
    ImmutableEvent,
    ImmutableEventBuilder,
    EventSource,
)
import logging

logger = logging.getLogger(__name__)


class AuthoritySystem:
    """
    权威系统：一站式处理所有时间和顺序相关逻辑
    
    设计原则：
    - 单点控制，全局一致
    - 不允许绕过 Authority 直接设置时间
    - 所有事件必须通过这里处理
    """
    
    def __init__(
        self,
        clock_mode: ClockMode = ClockMode.LIVE,
        latency_model: Optional[LatencyModel] = None,
    ):
        self.clock = ClockAuthority(clock_mode)
        self.availability = AvailabilityAuthority(latency_model)
        self.ordering = OrderingAuthority()
        
        logger.info("AuthoritySystem initialized")
    
    def process_raw_event(
        self,
        event_type: str,
        symbol: str,
        exchange: str,
        event_time_ms: int,
        payload: Dict[str, Any],
        source: EventSource = EventSource.LIVE,
    ) -> Tuple[ImmutableEvent, int]:
        """
        处理原始事件：生成完整的 ImmutableEvent
        
        这是创建事件的**唯一入口**，不允许直接创建 ImmutableEvent
        
        流程：
        1. 获取当前时钟时间 (processing_time)
        2. 自动计算可用时间 (available_time)
        3. 验证并分配序列号 (ordering)
        4. 创建 ImmutableEvent
        
        Args:
            event_type: 事件类型
            symbol: 交易对
            exchange: 交易所
            event_time_ms: 事件发生时间（交易所时间）
            payload: 数据载荷
            source: 事件来源
        
        Returns:
            (ImmutableEvent, sequence_number)
        
        Raises:
            ValueError: 验证失败
        """
        # 1. 获取当前时钟时间
        processing_time_ms = self.clock.now_ms()
        
        # 2. 自动计算可用时间
        available_time_ms = self.availability.compute_available_time(
            event_time_ms=event_time_ms,
            event_type=event_type,
        )
        
        # 3. 构建事件
        event_id = f"{event_type}_{symbol}_{event_time_ms}"
        
        builder = ImmutableEventBuilder()
        event = (
            builder
            .event_id(event_id)
            .event_type(event_type)
            .symbol(symbol)
            .exchange(exchange)
            .event_time_ms(event_time_ms)
            .available_time_ms(available_time_ms)
            .processing_time_ms(processing_time_ms)
            .payload(payload)
            .source(source)
            .build()
        )
        
        # 4. 验证顺序并分配序列号
        sequence_number, error_msg = self.ordering.process_event(event)
        if error_msg:
            raise ValueError(f"Ordering validation failed: {error_msg}")
        
        logger.debug(
            f"Processed event: {event.event_id}, "
            f"seq={sequence_number}, "
            f"event_time={event.event_time_ms}, "
            f"available_time={event.available_time_ms}, "
            f"processing_time={event.processing_time_ms}"
        )
        
        return event, sequence_number
    
    def validate_event(
        self,
        event: ImmutableEvent,
    ) -> Tuple[bool, Optional[str]]:
        """
        验证事件（用于处理已有的事件）
        
        检查：
        1. 事件完整性
        2. 事件可用性
        3. 事件顺序
        
        Args:
            event: 要验证的事件
        
        Returns:
            (是否通过, 错误信息)
        """
        # 1. 验证完整性
        if not event.verify_integrity():
            return False, "Event integrity verification failed"
        
        # 2. 验证可用性
        is_available, error_msg = self.availability.validate_availability(
            available_time_ms=event.available_time_ms,
            clock_ms=self.clock.now_ms(),
            event_id=event.event_id,
        )
        if not is_available:
            return False, error_msg
        
        # 3. 验证顺序
        is_ordered, error_msg = self.ordering.validate_order(event)
        if not is_ordered:
            return False, error_msg
        
        return True, None
    
    def switch_to_replay_mode(self, start_time_ms: int) -> None:
        """
        切换到 REPLAY 模式
        
        Args:
            start_time_ms: 回放起始时间
        """
        self.clock.switch_to_replay_mode(start_time_ms)
        self.ordering.reset()
    
    def switch_to_live_mode(self) -> None:
        """
        切换到 LIVE 模式
        """
        self.clock.switch_to_live_mode()
        self.ordering.reset()
    
    def advance_clock(self, target_ms: int) -> None:
        """
        推进时钟（仅 REPLAY 模式）
        
        Args:
            target_ms: 目标时间戳
        """
        self.clock.advance_to(target_ms)
    
    def __repr__(self) -> str:
        return (
            f"AuthoritySystem("
            f"clock={self.clock}, "
            f"availability={self.availability}, "
            f"ordering={self.ordering})"
        )
