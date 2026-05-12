"""
Circuit Breaker - 熔断器
防止级联故障，提供快速失败机制
"""
import time
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Optional, Any, Dict
from functools import wraps

from infrastructure.logging import get_logger

logger = get_logger("resilience.circuit")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"           # 正常状态，允许请求
    OPEN = "open"               # 熔断状态，直接拒绝
    HALF_OPEN = "half_open"     # 半开状态，尝试恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    name: str = "default"
    failure_threshold: int = 5              # 失败阈值
    recovery_timeout: float = 30.0          # 恢复超时（秒）
    half_open_max_calls: int = 3            # 半开状态允许的请求数
    expected_exception: tuple = (Exception,)  # 捕获的异常类型
    success_threshold: int = 2              # 半开状态成功阈值


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state
    
    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置"""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，带熔断保护"""
        async with self._lock:
            current_state = self.state
            
            if current_state == CircuitState.OPEN:
                logger.warning(f"Circuit '{self.config.name}' is OPEN, rejecting request")
                raise CircuitOpenError(f"Circuit {self.config.name} is open")
            
            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.warning(f"Circuit '{self.config.name}' half-open limit reached")
                    raise CircuitOpenError(f"Circuit {self.config.name} half-open limit reached")
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.expected_exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """成功回调"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    logger.info(f"Circuit '{self.config.name}' transitioning from HALF_OPEN to CLOSED")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        """失败回调"""
        async with self._lock:
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit '{self.config.name}' failed in HALF_OPEN, transitioning to OPEN")
                self._state = CircuitState.OPEN
                self._success_count = 0
                self._half_open_calls = 0
            else:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(f"Circuit '{self.config.name}' failure threshold reached, transitioning to OPEN")
                    self._state = CircuitState.OPEN
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "name": self.config.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "half_open_calls": self._half_open_calls
        }
    
    def reset(self):
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None


class CircuitOpenError(Exception):
    """熔断器打开异常"""
    pass


def circuit(config: CircuitBreakerConfig):
    """熔断器装饰器"""
    breaker = CircuitBreaker(config)
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.execute(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            raise NotImplementedError("Synchronous circuit breaker not implemented")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """获取或创建熔断器"""
    if name not in _circuit_breakers:
        cfg = config or CircuitBreakerConfig(name=name)
        _circuit_breakers[name] = CircuitBreaker(cfg)
    return _circuit_breakers[name]
