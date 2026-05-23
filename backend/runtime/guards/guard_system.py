"""
Guard System - 守卫系统组合入口

整合所有守卫，提供一站式验证
"""

from typing import List, Dict, Any, Optional

from runtime.guards.base_guard import GuardViolation, BaseGuard
from runtime.guards.availability_guard import AvailabilityGuard
from runtime.guards.ordering_guard import OrderingGuard
from runtime.guards.mutation_guard import MutationGuard
from runtime.guards.partial_candle_guard import PartialCandleGuard
from runtime.guards.duplicate_guard import DuplicateGuard
from runtime.guards.clock_guard import ClockGuard
from runtime.authority import ClockAuthority, ClockMode
from domain.event.protocol import ImmutableEvent
from domain.logging import get_logger

logger = get_logger("runtime.guards.system")


class GuardSystem:
    """
    守卫系统：整合所有守卫
    
    提供一站式验证，所有事件必须通过才能处理
    """
    
    def __init__(
        self,
        clock_authority: ClockAuthority,
        enable_all: bool = True,
    ):
        self._clock_authority = clock_authority
        self._guards: List[BaseGuard] = []
        self._guard_map: Dict[str, BaseGuard] = {}
        
        # 初始化所有守卫
        self._init_guards(enable_all)
    
    def _init_guards(self, enable_all: bool) -> None:
        """初始化所有守卫"""
        # 1. MutationGuard (检查完整性)
        self.add_guard(MutationGuard(enabled=enable_all))
        
        # 2. AvailabilityGuard (检查可用性)
        self.add_guard(
            AvailabilityGuard(
                clock_source=self._clock_authority.now_ms,
                enabled=enable_all,
            )
        )
        
        # 3. OrderingGuard (检查顺序)
        self.add_guard(OrderingGuard(enabled=enable_all))
        
        # 4. DuplicateGuard (去重)
        self.add_guard(DuplicateGuard(enabled=enable_all))
        
        # 5. PartialCandleGuard (检查完整K线)
        self.add_guard(PartialCandleGuard(enabled=enable_all))
        
        # 6. ClockGuard (监控时钟使用) - 单例
        self.add_guard(
            ClockGuard(
                clock_source=self._clock_authority.now_ms,
                enabled=enable_all,
                strict=False,  # 默认非严格，仅记录警告
            )
        )
    
    def add_guard(self, guard: BaseGuard) -> None:
        """
        添加一个守卫
        
        Args:
            guard: 要添加的守卫
        """
        self._guards.append(guard)
        self._guard_map[guard.name] = guard
        logger.debug(f"Added guard: {guard.name}")
    
    def get_guard(self, name: str) -> Optional[BaseGuard]:
        """
        获取指定守卫
        
        Args:
            name: 守卫名称
        
        Returns:
            守卫对象，不存在则返回 None
        """
        return self._guard_map.get(name)
    
    def process_before(self, event: ImmutableEvent) -> None:
        """
        处理前检查：执行所有守卫的 before_process
        
        Args:
            event: 要处理的事件
        
        Raises:
            GuardViolation: 任何守卫验证失败时
        """
        for guard in self._guards:
            guard.before_process(event)
        
        logger.debug(f"All guards passed for event: {event.event_id}")
    
    def process_after(self, event: ImmutableEvent, result: Any) -> None:
        """
        处理后检查：执行所有守卫的 after_process
        
        Args:
            event: 已处理的事件
            result: 处理结果
        
        Raises:
            GuardViolation: 任何守卫验证失败时
        """
        for guard in self._guards:
            guard.after_process(event, result)
    
    def validate_event(self, event: ImmutableEvent) -> bool:
        """
        验证事件但不抛出异常
        
        Args:
            event: 要验证的事件
        
        Returns:
            是否通过所有验证
        """
        try:
            self.process_before(event)
            return True
        except GuardViolation as e:
            logger.warning(f"Event validation failed: {e}")
            return False
    
    def reset(self) -> None:
        """重置所有守卫"""
        for guard in self._guards:
            guard.reset()
        logger.info("All guards reset")
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有守卫的统计信息
        
        Returns:
            统计字典 {guard_name: {violations, processed}}
        """
        stats = {}
        for guard in self._guards:
            stats[guard.name] = {
                "violations": guard.violation_count,
                "processed": guard.processed_count,
                "enabled": guard.enabled,
            }
        return stats
    
    def set_enabled(self, guard_name: str, enabled: bool) -> bool:
        """
        启用或禁用指定守卫
        
        Args:
            guard_name: 守卫名称
            enabled: 是否启用
        
        Returns:
            是否成功
        """
        guard = self._guard_map.get(guard_name)
        if guard:
            guard.enabled = enabled
            logger.info(f"Guard {guard_name} set to enabled={enabled}")
            return True
        logger.warning(f"Guard not found: {guard_name}")
        return False
    
    def __repr__(self) -> str:
        enabled_count = sum(1 for g in self._guards if g.enabled)
        return f"GuardSystem(guards={len(self._guards)}, enabled={enabled_count})"
