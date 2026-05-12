"""
Fallback Mechanism - 降级机制
提供多策略降级支持
"""
import asyncio
from dataclasses import dataclass
from typing import Callable, Optional, Any, List, Dict
from functools import wraps

from infrastructure.logging import get_logger

logger = get_logger("resilience.fallback")


@dataclass
class FallbackResult:
    """降级结果"""
    success: bool
    data: Any
    strategy_used: str
    error: Optional[Exception] = None


class FallbackStrategy:
    """降级策略基类"""
    
    def __init__(self, name: str):
        self.name = name
    
    async def execute(self, func: Callable, *args, **kwargs) -> FallbackResult:
        """执行降级策略"""
        raise NotImplementedError


class PrimaryFallback(FallbackStrategy):
    """主策略"""
    
    def __init__(self):
        super().__init__("primary")
    
    async def execute(self, func: Callable, *args, **kwargs) -> FallbackResult:
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            return FallbackResult(success=True, data=result, strategy_used=self.name)
        except Exception as e:
            return FallbackResult(success=False, data=None, strategy_used=self.name, error=e)


class StaticValueFallback(FallbackStrategy):
    """静态值降级"""
    
    def __init__(self, value: Any):
        super().__init__("static_value")
        self.value = value
    
    async def execute(self, func: Callable, *args, **kwargs) -> FallbackResult:
        logger.info(f"Using static value fallback: {self.value}")
        return FallbackResult(success=True, data=self.value, strategy_used=self.name)


class AlternateFunctionFallback(FallbackStrategy):
    """备用函数降级"""
    
    def __init__(self, alternate_func: Callable):
        super().__init__("alternate_function")
        self.alternate_func = alternate_func
    
    async def execute(self, func: Callable, *args, **kwargs) -> FallbackResult:
        try:
            logger.info("Using alternate function fallback")
            result = await self.alternate_func(*args, **kwargs) if asyncio.iscoroutinefunction(self.alternate_func) else self.alternate_func(*args, **kwargs)
            return FallbackResult(success=True, data=result, strategy_used=self.name)
        except Exception as e:
            return FallbackResult(success=False, data=None, strategy_used=self.name, error=e)


class FallbackChain:
    """降级链"""
    
    def __init__(self, strategies: Optional[List[FallbackStrategy]] = None):
        self.strategies = strategies or []
    
    def add_strategy(self, strategy: FallbackStrategy) -> "FallbackChain":
        """添加降级策略"""
        self.strategies.append(strategy)
        return self
    
    async def execute(self, primary_func: Callable, *args, **kwargs) -> FallbackResult:
        """执行降级链"""
        if not self.strategies:
            chain = [PrimaryFallback()]
        else:
            chain = self.strategies
        
        last_error = None
        
        for strategy in chain:
            try:
                result = await strategy.execute(primary_func, *args, **kwargs)
                if result.success:
                    return result
                last_error = result.error
            except Exception as e:
                logger.warning(f"Fallback strategy '{strategy.name}' failed: {e}")
                last_error = e
        
        return FallbackResult(
            success=False,
            data=None,
            strategy_used="none",
            error=last_error or Exception("All fallback strategies failed")
        )


def fallback(chain: FallbackChain):
    """降级装饰器"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await chain.execute(func, *args, **kwargs)
            if not result.success:
                raise result.error
            return result.data
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            raise NotImplementedError("Synchronous fallback not implemented")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def create_default_chain(
    primary_name: str,
    static_value: Any = None,
    alternate_func: Callable = None
) -> FallbackChain:
    """创建默认降级链"""
    chain = FallbackChain([PrimaryFallback()])
    
    if alternate_func:
        chain.add_strategy(AlternateFunctionFallback(alternate_func))
    
    if static_value is not None:
        chain.add_strategy(StaticValueFallback(static_value))
    
    return chain
