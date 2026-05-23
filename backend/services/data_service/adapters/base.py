"""
Adapter Base - 适配器基类

提供所有适配器的公共基类和配置。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from domain.contracts import StandardEvent, Sentiment
from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)

logger = get_logger("adapters.base")


@dataclass
class AdapterConfig:
    """适配器配置"""
    name: str
    source_type: str
    enabled: bool = True
    priority: int = 0
    cache_ttl: int = 300
    retry_count: int = 2


class BaseAdapter(ABC):
    """适配器基类
    
    所有数据源适配器都必须继承这个类。
    """
    
    def __init__(self, config: AdapterConfig = None):
        self.config = config or AdapterConfig(
            name=self.__class__.__name__,
            source_type="unknown"
        )
        
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name=f"{self.config.name}_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=config.retry_count if config else 2,
            initial_delay=1.0
        ))
        
        self._cache: Dict = {}
        self._last_fetch: int = 0
        
        logger.info(f"Adapter '{self.config.name}' initialized")
    
    @abstractmethod
    async def fetch_raw_data(self) -> Any:
        """获取原始数据（由子类实现）"""
        pass
    
    @abstractmethod
    def normalize(self, raw_data: Any) -> List[StandardEvent]:
        """将原始数据转换为标准事件（由子类实现）"""
        pass
    
    async def collect(self) -> List[StandardEvent]:
        """采集并转换数据"""
        try:
            raw_data = await self.retry_policy.execute(self.fetch_raw_data)
            events = self.normalize(raw_data)
            logger.info(f"{self.config.name}: Fetched {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"{self.config.name} failed: {e}")
            return []
    
    def _parse_sentiment(self, text: str) -> str:
        """解析情绪"""
        if not text:
            return Sentiment.NEUTRAL.value
        
        text_lower = text.lower()
        
        bullish_keywords = ["bullish", "看涨", "利好", "上涨", "surge", "rally", "突破"]
        bearish_keywords = ["bearish", "看跌", "利空", "下跌", "crash", "plunge", "暴跌"]
        
        if any(kw in text_lower for kw in bullish_keywords):
            return Sentiment.BULLISH.value
        if any(kw in text_lower for kw in bearish_keywords):
            return Sentiment.BEARISH.value
        
        return Sentiment.NEUTRAL.value


class AdapterRegistry:
    """适配器注册表"""
    
    def __init__(self):
        self._adapters: Dict[str, BaseAdapter] = {}
        self._enabled: List[str] = []
    
    def register(self, adapter: BaseAdapter):
        """注册适配器"""
        self._adapters[adapter.config.name] = adapter
        if adapter.config.enabled:
            self._enabled.append(adapter.config.name)
        logger.info(f"Registered adapter: {adapter.config.name}")
    
    def get(self, name: str) -> Optional[BaseAdapter]:
        """获取适配器"""
        return self._adapters.get(name)
    
    def get_enabled(self) -> List[BaseAdapter]:
        """获取所有启用的适配器"""
        return [self._adapters[name] for name in self._enabled if name in self._adapters]
    
    async def collect_all(self) -> List[StandardEvent]:
        """从所有适配器采集"""
        all_events = []
        
        for adapter in self.get_enabled():
            try:
                events = await adapter.collect()
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Adapter {adapter.config.name} failed: {e}")
        
        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        
        return all_events


_registry: Optional[AdapterRegistry] = None


def get_adapter_registry() -> AdapterRegistry:
    """获取适配器注册表单例"""
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry
