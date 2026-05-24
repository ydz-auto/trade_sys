"""
Retry Mechanism - 重试机制
提供智能重试支持
"""
import asyncio
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, Any, Tuple, List
from functools import wraps

from infrastructure.logging import get_logger

logger = get_logger("resilience.retry")


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_exceptions: Tuple[type, ...] = (Exception,)
    retry_callback: Optional[Callable] = None


class RetryPolicy:
    """重试策略"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def calculate_delay(self, attempt: int) -> float:
        """计算延迟时间（指数退避 + 抖动）"""
        delay = self.config.initial_delay * (self.config.backoff_multiplier ** attempt)
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)
        
        return delay
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，带重试"""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}")
                
                return result
                
            except self.config.retry_exceptions as e:
                last_exception = e
                
                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
                    )
                    
                    if self.config.retry_callback:
                        try:
                            self.config.retry_callback(attempt, e)
                        except Exception as cb_err:
                            logger.error(f"Retry callback error: {cb_err}")
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.config.max_attempts} attempts failed")
        
        raise last_exception


def retry(config: RetryConfig):
    """重试装饰器"""
    policy = RetryPolicy(config)
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await policy.execute(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            raise NotImplementedError("Synchronous retry not implemented")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0
):
    """便捷装饰器 - 指数退避重试"""
    return retry(RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay
    ))
