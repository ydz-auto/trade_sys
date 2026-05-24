"""
Signal Runtime - 指标收集

职责：
- 事件计数
- 处理延迟
- 错误统计
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import time

from infrastructure.utilities.runtime_clock import now_ms


@dataclass
class SignalMetricsData:
    """指标数据"""
    events_received: int = 0
    events_processed: int = 0
    decisions_made: int = 0
    errors: int = 0
    
    total_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    
    start_time: float = field(default_factory=lambda: now_ms() / 1000)


class SignalMetrics:
    """
    Signal Runtime 指标收集
    
    只负责运行时指标，不包含业务逻辑。
    """
    
    def __init__(self):
        self.data = SignalMetricsData()
        self._processing_start: float = 0.0
    
    def record_event_received(self) -> None:
        """记录接收到的事件"""
        self.data.events_received += 1
    
    def record_event_processed(self, duration_ms: float = None) -> None:
        """记录处理完成的事件"""
        self.data.events_processed += 1
        
        if duration_ms is not None:
            self.data.total_processing_time_ms += duration_ms
            self.data.max_processing_time_ms = max(
                self.data.max_processing_time_ms, duration_ms
            )
    
    def record_decision_made(self) -> None:
        """记录生成的决策"""
        self.data.decisions_made += 1
    
    def record_error(self) -> None:
        """记录错误"""
        self.data.errors += 1
    
    def start_processing_timer(self) -> None:
        """开始计时"""
        self._processing_start = now_ms() / 1000
    
    def stop_processing_timer(self) -> float:
        """停止计时，返回毫秒"""
        if self._processing_start > 0:
            duration_ms = (now_ms() / 1000 - self._processing_start) * 1000
            self.record_event_processed(duration_ms)
            self._processing_start = 0.0
            return duration_ms
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        uptime = now_ms() / 1000 - self.data.start_time
        
        avg_processing_time = 0.0
        if self.data.events_processed > 0:
            avg_processing_time = (
                self.data.total_processing_time_ms / self.data.events_processed
            )
        
        return {
            "events_received": self.data.events_received,
            "events_processed": self.data.events_processed,
            "decisions_made": self.data.decisions_made,
            "errors": self.data.errors,
            "uptime_seconds": uptime,
            "avg_processing_time_ms": avg_processing_time,
            "max_processing_time_ms": self.data.max_processing_time_ms,
            "events_per_second": self.data.events_processed / uptime if uptime > 0 else 0,
        }
    
    def reset(self) -> None:
        """重置指标"""
        self.data = SignalMetricsData()
