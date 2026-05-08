"""
Base Collector - 所有收集器的基类
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger
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
    """收集器基类"""

    def __init__(self, name: str):
        self.name = name
        self.status = CollectorStatus.IDLE
        self.last_run: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.error_count = 0
        self.total_runs = 0
        self._cache: Dict[str, Any] = {}

    @abstractmethod
    async def collect(self) -> CollectorResult:
        """执行数据采集"""
        pass

    async def collect_with_retry(self, max_retries: int = 3) -> CollectorResult:
        """带重试的采集"""
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
        """获取状态"""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "error_count": self.error_count,
            "total_runs": self.total_runs
        }


class MultiSourceCollector(BaseCollector):
    """多数据源收集器基类"""

    def __init__(self, name: str, sources: List[SourceConfig]):
        super().__init__(name)
        self.sources = {s.name: s for s in sources}
        self.results: Dict[str, CollectorResult] = {}

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
        """采集单个数据源"""
        start_time = time.time()

        try:
            result = await self.collect_source(name, config)
            result.latency_ms = int((time.time() - start_time) * 1000)
            result.source = name
            return result

        except Exception as e:
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
