"""
Base Collector - 所有收集器的基类
集成熔断、降级、重试等弹性能力
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig
from infrastructure.utilities.resilience.fallback import FallbackChain, PrimaryFallback, StaticValueFallback, FallbackResult, create_default_chain

logger = get_logger("collectors.base")


class CollectorStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STALE = "stale"


@dataclass
class CollectorResult:
    """收集器结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    latency_ms: int = 0
    confidence: float = 1.0


@dataclass
class SourceConfig:
    """数据源配置"""
    name: str
    type: str
    priority: int = 1
    weight: float = 1.0
    enabled: bool = True
    timeout: float = 10.0
    retry_count: int = 3
    retry_delay: float = 1.0
    check_interval: int = 60
    api_key_required: bool = False


class BaseCollector(ABC):
    """收集器基类 - 自动集成熔断、降级、重试"""

    def __init__(
        self,
        name: str,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        fallback_value: Optional[Any] = None,
        fallback_func: Optional[Callable] = None
    ):
        self.name = name
        self.status = CollectorStatus.IDLE
        self.last_run: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.error_count = 0
        self.total_runs = 0
        self._cache: Dict[str, Any] = {}
        
        # 弹性基础设施
        self._init_resilience(circuit_config, retry_config, fallback_value, fallback_func)
    
    def _init_resilience(
        self,
        circuit_config: Optional[CircuitBreakerConfig],
        retry_config: Optional[RetryConfig],
        fallback_value: Optional[Any],
        fallback_func: Optional[Callable]
    ):
        """初始化弹性基础设施"""
        # 熔断器配置
        if circuit_config is None:
            circuit_config = CircuitBreakerConfig(
                name=f"{self.name}_circuit",
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_max_calls=2,
                success_threshold=2
            )
        self.circuit_breaker = get_circuit_breaker(circuit_config.name, circuit_config)
        
        # 重试策略
        if retry_config is None:
            retry_config = RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                max_delay=10.0,
                backoff_multiplier=2.0,
                jitter=True
            )
        self.retry_policy = RetryPolicy(retry_config)
        
        # 降级链
        self.fallback_chain = create_default_chain(
            primary_name=self.name,
            static_value=fallback_value,
            alternate_func=fallback_func
        )

    @abstractmethod
    async def collect(self) -> CollectorResult:
        """执行数据采集"""
        pass

    async def collect_with_resilience(self) -> CollectorResult:
        """带完整弹性能力的采集：重试 + 熔断 + 降级"""
        start_time = time.time()
        
        # 使用熔断和重试执行
        async def wrapped_collect():
            return await self.retry_policy.execute(self.collect)
        
        try:
            # 先通过熔断和重试执行
            result = await self.circuit_breaker.execute(wrapped_collect)
            self._on_collect_success(result, start_time)
            return result
            
        except Exception as e:
            logger.warning(f"{self.name} 熔断触发或全部重试失败: {e}")
            
            # 尝试降级
            fallback_result = await self._try_fallback(start_time)
            if fallback_result is not None:
                return fallback_result
            
            # 完全失败
            self._on_collect_failure(start_time, e)
            return CollectorResult(
                success=False,
                error=f"采集失败: {str(e)}",
                source=self.name,
                latency_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _try_fallback(self, start_time: float) -> Optional[CollectorResult]:
        """尝试降级策略"""
        try:
            fallback_result = await self.fallback_chain.execute(lambda: None)
            
            if fallback_result.success:
                logger.info(f"{self.name} 使用降级策略: {fallback_result.strategy_used}")
                
                # 如果降级值是一个 CollectorResult，直接返回
                if isinstance(fallback_result.data, CollectorResult):
                    fallback_result.data.latency_ms = int((time.time() - start_time) * 1000)
                    fallback_result.data.source = f"{self.name}_fallback"
                    return fallback_result.data
                
                # 否则包装为 CollectorResult
                return CollectorResult(
                    success=True,
                    data=fallback_result.data,
                    source=f"{self.name}_fallback",
                    latency_ms=int((time.time() - start_time) * 1000),
                    confidence=0.5  # 降级数据置信度较低
                )
        except Exception as fallback_err:
            logger.error(f"{self.name} 降级策略也失败了: {fallback_err}")
        
        return None
    
    def _on_collect_success(self, result: CollectorResult, start_time: float):
        """采集成功回调"""
        self.total_runs += 1
        self.status = CollectorStatus.IDLE
        self.last_run = datetime.now()
        self.last_success = datetime.now()
        self.error_count = 0
        result.latency_ms = int((time.time() - start_time) * 1000)
        result.source = self.name
    
    def _on_collect_failure(self, start_time: float, error: Exception):
        """采集失败回调"""
        self.total_runs += 1
        self.error_count += 1
        self.status = CollectorStatus.ERROR
    
    async def collect_with_retry(self, max_retries: int = 3) -> CollectorResult:
        """带重试的采集（向后兼容，现在优先使用 collect_with_resilience）"""
        for attempt in range(max_retries):
            try:
                result = await self.collect()
                self.total_runs += 1

                if result.success:
                    self.status = CollectorStatus.IDLE
                    self.last_run = datetime.now()
                    self.last_success = datetime.now()
                    self.error_count = 0
                    return result
                else:
                    self.error_count += 1
                    logger.warning(f"{self.name} 采集失败 (尝试 {attempt + 1}/{max_retries}): {result.error}")

            except Exception as e:
                self.error_count += 1
                logger.error(f"{self.name} 异常 (尝试 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))

        self.status = CollectorStatus.ERROR
        return CollectorResult(
            success=False,
            error=f"连续{max_retries}次采集失败"
        )

    def get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        return self._cache.get(key)

    def set_cache(self, key: str, value: Any, ttl: int = 60):
        """设置缓存"""
        self._cache[key] = {
            "value": value,
            "expire_at": time.time() + ttl
        }

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()

    def is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False
        return time.time() < self._cache[key]["expire_at"]

    def get_status(self) -> Dict:
        """获取状态（包含弹性基础设施状态）"""
        circuit_stats = self.circuit_breaker.get_stats() if hasattr(self, 'circuit_breaker') else None
        
        return {
            "name": self.name,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "error_count": self.error_count,
            "total_runs": self.total_runs,
            "resilience": {
                "circuit_breaker": circuit_stats,
                "has_fallback": hasattr(self, 'fallback_chain') and len(self.fallback_chain.strategies) > 1
            }
        }


class MultiSourceCollector(BaseCollector):
    """多数据源收集器基类 - 每个源有独立的熔断器"""

    def __init__(self, name: str, sources: List[SourceConfig]):
        super().__init__(name)
        self.sources = {s.name: s for s in sources}
        self.results: Dict[str, CollectorResult] = {}
        
        # 每个源独立的熔断器
        self._source_circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._source_retry_policies: Dict[str, RetryPolicy] = {}
        self._init_source_resilience()
    
    def _init_source_resilience(self):
        """为每个源初始化独立的弹性配置"""
        for name, config in self.sources.items():
            # 熔断器 - 使用源配置的参数
            circuit_config = CircuitBreakerConfig(
                name=f"{self.name}_{name}_circuit",
                failure_threshold=config.retry_count + 2,
                recovery_timeout=30.0,
                half_open_max_calls=2
            )
            self._source_circuit_breakers[name] = get_circuit_breaker(circuit_config.name, circuit_config)
            
            # 重试策略
            retry_config = RetryConfig(
                max_attempts=config.retry_count,
                initial_delay=config.retry_delay,
                max_delay=10.0,
                backoff_multiplier=2.0
            )
            self._source_retry_policies[name] = RetryPolicy(retry_config)

    async def collect_all_sources(self) -> Dict[str, CollectorResult]:
        """并行采集所有数据源"""
        tasks = []
        source_names = []

        for name, config in self.sources.items():
            if config.enabled:
                tasks.append(self._collect_source(name, config))
                source_names.append(name)

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for name, result in zip(source_names, results_list):
            if isinstance(result, Exception):
                results[name] = CollectorResult(
                    success=False,
                    error=str(result),
                    source=name
                )
            else:
                results[name] = result

        self.results = results
        return results

    async def _collect_source(self, name: str, config: SourceConfig) -> CollectorResult:
        """采集单个数据源（带源独立的熔断和重试）"""
        start_time = time.time()
        
        async def wrapped_source_collect():
            return await self.collect_source(name, config)
        
        try:
            # 获取源的弹性配置
            circuit_breaker = self._source_circuit_breakers.get(name)
            retry_policy = self._source_retry_policies.get(name)
            
            if circuit_breaker and retry_policy:
                # 完整弹性流程：先重试，再熔断
                async def with_retry():
                    return await retry_policy.execute(wrapped_source_collect)
                
                result = await circuit_breaker.execute(with_retry)
            else:
                # 无弹性配置，直接采集
                result = await wrapped_source_collect()
            
            result.latency_ms = int((time.time() - start_time) * 1000)
            result.source = name
            return result

        except Exception as e:
            logger.warning(f"{self.name} 源 {name} 采集失败: {e}")
            return CollectorResult(
                success=False,
                error=str(e),
                source=name,
                latency_ms=int((time.time() - start_time) * 1000)
            )

    @abstractmethod
    async def collect_source(self, name: str, config: SourceConfig) -> CollectorResult:
        """采集单个数据源（子类实现）"""
        pass

    def get_valid_results(self) -> List[CollectorResult]:
        """获取成功的采集结果"""
        return [r for r in self.results.values() if r.success]

    def get_best_result(self) -> Optional[CollectorResult]:
        """获取最佳结果（按优先级和置信度）"""
        valid = self.get_valid_results()
        if not valid:
            return None

        return max(valid, key=lambda r: (
            self.sources[r.source].priority if r.source in self.sources else 0,
            r.confidence
        ))
    
    def get_source_status(self) -> Dict[str, Dict]:
        """获取所有源的状态（包含熔断状态）"""
        source_status = {}
        
        for name, config in self.sources.items():
            circuit_breaker = self._source_circuit_breakers.get(name)
            status = {
                "enabled": config.enabled,
                "priority": config.priority,
                "timeout": config.timeout,
                "circuit_state": circuit_breaker.get_stats() if circuit_breaker else None
            }
            
            if name in self.results:
                status["last_result"] = {
                    "success": self.results[name].success,
                    "latency_ms": self.results[name].latency_ms,
                    "timestamp": self.results[name].timestamp
                }
            
            source_status[name] = status
        
        return source_status
