"""
Unified Clock System - 统一时钟系统

所有运行模式共用同一时钟抽象，确保：
- live: 使用真实时间
- paper: 使用真实时间
- replay: 使用事件时间
- backtest: 使用模拟时间

这是系统一致性的基础。
"""

import asyncio
import time
from typing import Optional, Callable, Awaitable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
import functools

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.clock")


class ClockMode(str, Enum):
    """时钟模式"""
    LIVE = "live"
    PAPER = "paper"
    REPLAY = "replay"
    BACKTEST = "backtest"


@dataclass
class ClockConfig:
    """时钟配置"""
    mode: ClockMode = ClockMode.LIVE
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    speed: float = 1.0
    
    step_size: timedelta = field(default_factory=lambda: timedelta(milliseconds=100))
    
    auto_advance: bool = True


class Clock:
    """统一时钟
    
    所有运行模式共用的时钟抽象
    """
    
    def __init__(self, config: Optional[ClockConfig] = None):
        self.config = config or ClockConfig()
        
        self._current_time: Optional[datetime] = None
        self._is_running = False
        self._listeners: list[Callable[[datetime], Awaitable[None]]] = []
        
        self._step_count = 0
        self._last_advance_time: Optional[float] = None
        
        if self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]:
            self._current_time = datetime.utcnow()
        elif self.config.start_time:
            self._current_time = self.config.start_time
        else:
            self._current_time = datetime.utcnow()
    
    def now(self) -> datetime:
        """获取当前时间"""
        if self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]:
            return datetime.utcnow()
        return self._current_time or datetime.utcnow()
    
    def timestamp(self) -> float:
        """获取当前时间戳"""
        return self.now().timestamp()
    
    def timestamp_ms(self) -> int:
        """获取当前毫秒时间戳"""
        return int(self.now().timestamp() * 1000)
    
    def advance(self, delta: timedelta) -> datetime:
        """推进时间"""
        if self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]:
            return self.now()
        
        self._current_time = (self._current_time or datetime.utcnow()) + delta
        self._step_count += 1
        self._last_advance_time = time.time()
        
        logger.debug(f"Clock advanced to {self._current_time} (step {self._step_count})")
        
        return self._current_time
    
    async def advance_async(self, delta: timedelta) -> datetime:
        """异步推进时间"""
        new_time = self.advance(delta)
        
        for listener in self._listeners:
            try:
                await listener(new_time)
            except Exception as e:
                logger.error(f"Clock listener error: {e}")
        
        return new_time
    
    def advance_to(self, target_time: datetime) -> datetime:
        """推进到指定时间"""
        if self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]:
            return self.now()
        
        if target_time > self._current_time:
            self._current_time = target_time
            self._step_count += 1
            self._last_advance_time = time.time()
        
        return self._current_time
    
    def sleep(self, seconds: float) -> None:
        """睡眠（同步）"""
        if self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]:
            time.sleep(seconds)
        else:
            self.advance(timedelta(seconds=seconds))
    
    async def sleep_async(self, seconds: float) -> None:
        """睡眠（异步）"""
        if self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]:
            await asyncio.sleep(seconds)
        else:
            await self.advance_async(timedelta(seconds=seconds))
    
    def add_listener(self, listener: Callable[[datetime], Awaitable[None]]) -> None:
        """添加时间变化监听器"""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[datetime], Awaitable[None]]) -> None:
        """移除时间变化监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    @contextmanager
    def freeze(self):
        """冻结时间上下文"""
        frozen_time = self._current_time
        original_mode = self.config.mode
        
        self.config.mode = ClockMode.BACKTEST
        
        try:
            yield self
        finally:
            self._current_time = frozen_time
            self.config.mode = original_mode
    
    def get_mode(self) -> ClockMode:
        """获取时钟模式"""
        return self.config.mode
    
    def is_live(self) -> bool:
        """是否实时模式"""
        return self.config.mode in [ClockMode.LIVE, ClockMode.PAPER]
    
    def is_simulated(self) -> bool:
        """是否模拟模式"""
        return self.config.mode in [ClockMode.REPLAY, ClockMode.BACKTEST]
    
    def get_step_count(self) -> int:
        """获取步进次数"""
        return self._step_count
    
    def reset(self, start_time: Optional[datetime] = None) -> None:
        """重置时钟"""
        self._current_time = start_time or self.config.start_time or datetime.utcnow()
        self._step_count = 0
        self._last_advance_time = None
        logger.info(f"Clock reset to {self._current_time}")


_clock_instance: Optional[Clock] = None


def get_clock() -> Clock:
    """获取全局时钟实例"""
    global _clock_instance
    if _clock_instance is None:
        _clock_instance = Clock()
    return _clock_instance


def set_clock(clock: Clock) -> None:
    """设置全局时钟实例"""
    global _clock_instance
    _clock_instance = clock


def now() -> datetime:
    """便捷函数：获取当前时间"""
    return get_clock().now()


def timestamp() -> float:
    """便捷函数：获取当前时间戳"""
    return get_clock().timestamp()


def clock_sleep(seconds: float) -> None:
    """便捷函数：睡眠"""
    get_clock().sleep(seconds)


async def clock_sleep_async(seconds: float) -> None:
    """便捷函数：异步睡眠"""
    await get_clock().sleep_async(seconds)


def use_clock(mode: ClockMode):
    """装饰器：使用指定时钟模式"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            clock = get_clock()
            original_mode = clock.config.mode
            clock.config.mode = mode
            try:
                return func(*args, **kwargs)
            finally:
                clock.config.mode = original_mode
        return wrapper
    return decorator
