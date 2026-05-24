"""
Runtime Metrics - 统一的指标收集

所有 Runtime 共享的指标收集组件。
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List
from collections import defaultdict

from runtime.adapters.clock_adapter import now_ms


@dataclass
class MetricValue:
    """指标值"""
    count: int = 0
    total: float = 0.0
    min: float = float('inf')
    max: float = float('-inf')
    last: float = 0.0


class RuntimeMetrics:
    """
    统一的 Runtime 指标收集
    
    职责：
    - 计数器
    - 直方图
    - 仪表盘
    """
    
    def __init__(self, name: str):
        self.name = name
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, MetricValue] = defaultdict(MetricValue)
        self._start_time: float = now_ms() / 1000
    
    def increment(self, name: str, delta: int = 1) -> None:
        """增加计数器"""
        self._counters[name] += delta
    
    def decrement(self, name: str, delta: int = 1) -> None:
        """减少计数器"""
        self._counters[name] -= delta
    
    def gauge(self, name: str, value: float) -> None:
        """设置仪表盘值"""
        self._gauges[name] = value
    
    def observe(self, name: str, value: float) -> None:
        """观察直方图值"""
        metric = self._histograms[name]
        metric.count += 1
        metric.total += value
        metric.min = min(metric.min, value)
        metric.max = max(metric.max, value)
        metric.last = value
    
    def timing(self, name: str) -> "TimingContext":
        """计时上下文"""
        return TimingContext(self, name)
    
    def get_counter(self, name: str) -> int:
        """获取计数器值"""
        return self._counters[name]
    
    def get_gauge(self, name: str) -> float:
        """获取仪表盘值"""
        return self._gauges[name]
    
    def get_histogram(self, name: str) -> Dict[str, float]:
        """获取直方图统计"""
        metric = self._histograms[name]
        if metric.count == 0:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "last": 0}
        return {
            "count": metric.count,
            "total": metric.total,
            "avg": metric.total / metric.count,
            "min": metric.min,
            "max": metric.max,
            "last": metric.last,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        uptime = now_ms() / 1000 - self._start_time
        
        return {
            "name": self.name,
            "uptime_seconds": uptime,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: self.get_histogram(k) for k in self._histograms},
        }
    
    def reset(self) -> None:
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = now_ms() / 1000


class TimingContext:
    """计时上下文管理器"""
    
    def __init__(self, metrics: RuntimeMetrics, name: str):
        self.metrics = metrics
        self.name = name
        self._start: float = 0.0
    
    def __enter__(self):
        self._start = now_ms() / 1000
        return self
    
    def __exit__(self, *args):
        duration_ms = (now_ms() / 1000 - self._start) * 1000
        self.metrics.observe(self.name, duration_ms)
    
    async def __aenter__(self):
        self._start = now_ms() / 1000
        return self
    
    async def __aexit__(self, *args):
        duration_ms = (now_ms() / 1000 - self._start) * 1000
        self.metrics.observe(self.name, duration_ms)
