"""
Clock Guard - 时钟守卫

强制统一使用指定时钟，防止直接调用系统时间
"""

import time
import datetime
from typing import Callable, Set, Optional
from threading import Lock

from runtime.kernel.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class ClockGuard(BaseGuard):
    """
    时钟守卫：强制统一使用指定时钟
    
    监控是否有代码绕过 Authority 直接调用系统时间
    """
    
    _lock = Lock()
    _instance: Optional['ClockGuard'] = None
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(
        self,
        clock_source: Callable[[], int],
        enabled: bool = True,
        strict: bool = True,
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        super().__init__("ClockGuard", enabled)
        self._clock_source = clock_source
        self._strict = strict
        self._direct_call_count = 0
        self._initialized = True
        
        # 保存原始函数
        self._original_time = time.time
        self._original_datetime_now = datetime.datetime.now
        self._original_datetime_utcnow = datetime.datetime.utcnow
        
        # 只有启用时才替换
        if enabled:
            self._install()
        
        logger.info(f"ClockGuard initialized, strict={strict}")
    
    def _install(self) -> None:
        """安装监控"""
        if not self._strict:
            return
        
        # 替换 time.time
        def _wrapped_time():
            self._direct_call_count += 1
            logger.warning(
                f"Direct call to time.time() detected! "
                f"Use ClockAuthority instead. "
                f"Total: {self._direct_call_count}"
            )
            return self._original_time()
        
        time.time = _wrapped_time
        
        # 替换 datetime.now
        def _wrapped_datetime_now(tz=None):
            self._direct_call_count += 1
            logger.warning(
                f"Direct call to datetime.datetime.now() detected! "
                f"Use ClockAuthority instead. "
                f"Total: {self._direct_call_count}"
            )
            return self._original_datetime_now(tz)
        
        datetime.datetime.now = _wrapped_datetime_now
        
        # 替换 datetime.utcnow
        def _wrapped_datetime_utcnow():
            self._direct_call_count += 1
            logger.warning(
                f"Direct call to datetime.datetime.utcnow() detected! "
                f"Use ClockAuthority instead. "
                f"Total: {self._direct_call_count}"
            )
            return self._original_datetime_utcnow()
        
        datetime.datetime.utcnow = _wrapped_datetime_utcnow
    
    def _uninstall(self) -> None:
        """卸载监控"""
        time.time = self._original_time
        datetime.datetime.now = self._original_datetime_now
        datetime.datetime.utcnow = self._original_datetime_utcnow
    
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """处理前检查：当前时钟是否合理"""
        pass
    
    def reset(self) -> None:
        """重置"""
        super().reset()
        self._direct_call_count = 0
    
    def __del__(self):
        """析构：确保卸载"""
        try:
            self._uninstall()
        except:
            pass
    
    def __repr__(self) -> str:
        return (
            f"ClockGuard(enabled={self.enabled}, "
            f"strict={self._strict}, "
            f"direct_calls={self._direct_call_count})"
        )
