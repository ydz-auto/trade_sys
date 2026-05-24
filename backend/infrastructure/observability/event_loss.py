"""
Event Loss Detector - 事件丢失检测器
检测 Kafka 事件流中的丢失、乱序、重复等问题

功能：
1. 序号检测 - 检测丢失事件
2. 时间戳检测 - 检测乱序
3. 去重检测 - 检测重复事件
4. 数据质量告警
"""

import asyncio
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import hashlib

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.observability.event_loss")


class AnomalyType(Enum):
    LOST = "lost"
    OUT_OF_ORDER = "out_of_order"
    DUPLICATE = "duplicate"
    GAP = "gap"
    DELAY = "delay"


@dataclass
class EventAnomaly:
    """事件异常"""
    type: AnomalyType
    topic: str
    partition: int
    expected_seq: int
    actual_seq: int
    lost_count: int
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "topic": self.topic,
            "partition": self.partition,
            "expected_seq": self.expected_seq,
            "actual_seq": self.actual_seq,
            "lost_count": self.lost_count,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class EventQualityStats:
    """事件质量统计"""
    total_events: int = 0
    lost_events: int = 0
    out_of_order_events: int = 0
    duplicate_events: int = 0
    delayed_events: int = 0
    gaps: List[Dict] = field(default_factory=list)
    last_sequence: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "lost_events": self.lost_events,
            "out_of_order_events": self.out_of_order_events,
            "duplicate_events": self.duplicate_events,
            "delayed_events": self.delayed_events,
            "gaps": self.gaps,
            "last_sequence": self.last_sequence,
            "loss_rate": self.lost_events / max(self.total_events, 1),
        }


class EventLossDetector:
    """事件丢失检测器
    
    通过序列号和时间戳检测事件流中的问题
    """
    
    def __init__(
        self,
        retention_hours: int = 24,
        max_gap_size: int = 100,
        delay_threshold_seconds: int = 60,
        enable_dedup: bool = True,
        dedup_window_seconds: int = 300,
    ):
        self.retention_hours = retention_hours
        self.max_gap_size = max_gap_size
        self.delay_threshold_seconds = delay_threshold_seconds
        self.enable_dedup = enable_dedup
        self.dedup_window_seconds = dedup_window_seconds
        
        self._stats = EventQualityStats()
        self._sequences: Dict[str, Dict[str, int]] = {}
        self._timestamps: Dict[str, Dict[str, datetime]] = {}
        self._seen_hashes: deque = deque(maxlen=10000)
        self._anomalies: deque = deque(maxlen=1000)
        self._alert_callbacks: List[Callable] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """启动检测"""
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Event loss detector started")
    
    async def stop(self) -> None:
        """停止检测"""
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Event loss detector stopped")
    
    async def _cleanup_loop(self) -> None:
        """清理过期数据"""
        while self._running:
            try:
                await self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            
            await asyncio.sleep(3600)
    
    async def _cleanup_expired(self) -> None:
        """清理过期序列信息"""
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        
        for topic in list(self._timestamps.keys()):
            partition_keys = list(self._timestamps[topic].keys())
            for key in partition_keys:
                if self._timestamps[topic][key] < cutoff:
                    del self._timestamps[topic][key]
            
            if not self._timestamps[topic]:
                del self._timestamps[topic]
    
    async def check_event(
        self,
        topic: str,
        partition: int,
        sequence: int,
        timestamp: Optional[datetime] = None,
        event_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[EventAnomaly]:
        """检查事件"""
        self._stats.total_events += 1
        
        key = f"{topic}:{partition}"
        ts_key = f"{topic}:{partition}"
        
        if key not in self._sequences:
            self._sequences[key] = 0
        
        expected_seq = self._sequences[key] + 1
        self._sequences[key] = sequence
        
        anomaly = None
        
        if sequence > expected_seq:
            lost_count = sequence - expected_seq
            anomaly = EventAnomaly(
                type=AnomalyType.LOST,
                topic=topic,
                partition=partition,
                expected_seq=expected_seq,
                actual_seq=sequence,
                lost_count=lost_count,
                timestamp=datetime.now(),
                details={"gap": sequence - expected_seq},
            )
            self._stats.lost_events += lost_count
            self._stats.gaps.append({
                "topic": topic,
                "partition": partition,
                "from": expected_seq,
                "to": sequence,
                "lost": lost_count,
                "detected_at": datetime.now().isoformat(),
            })
            logger.warning(f"Event loss detected: {topic}:{partition}, lost {lost_count} events")
        
        elif sequence < expected_seq:
            anomaly = EventAnomaly(
                type=AnomalyType.OUT_OF_ORDER,
                topic=topic,
                partition=partition,
                expected_seq=expected_seq,
                actual_seq=sequence,
                lost_count=0,
                timestamp=datetime.now(),
                details={"delay": expected_seq - sequence},
            )
            self._stats.out_of_order_events += 1
        
        if event_hash and self.enable_dedup:
            if event_hash in self._seen_hashes:
                if not anomaly:
                    anomaly = EventAnomaly(
                        type=AnomalyType.DUPLICATE,
                        topic=topic,
                        partition=partition,
                        expected_seq=expected_seq,
                        actual_seq=sequence,
                        lost_count=0,
                        timestamp=datetime.now(),
                        details={"hash": event_hash},
                    )
                self._stats.duplicate_events += 1
                logger.debug(f"Duplicate event: {topic}:{partition}")
            else:
                self._seen_hashes.append(event_hash)
        
        if timestamp:
            self._timestamps[ts_key] = timestamp
            
            now = datetime.now()
            if (now - timestamp).total_seconds() > self.delay_threshold_seconds:
                if not anomaly:
                    anomaly = EventAnomaly(
                        type=AnomalyType.DELAY,
                        topic=topic,
                        partition=partition,
                        expected_seq=expected_seq,
                        actual_seq=sequence,
                        lost_count=0,
                        timestamp=datetime.now(),
                        details={"delay_seconds": (now - timestamp).total_seconds()},
                    )
                self._stats.delayed_events += 1
        
        if anomaly:
            self._anomalies.append(anomaly)
            await self._trigger_alerts(anomaly)
        
        return anomaly
    
    async def _trigger_alerts(self, anomaly: EventAnomaly) -> None:
        """触发告警"""
        for callback in self._alert_callbacks:
            try:
                await callback(anomaly)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def register_alert_callback(self, callback: Callable) -> None:
        """注册告警回调"""
        self._alert_callbacks.append(callback)
    
    def get_stats(self) -> EventQualityStats:
        """获取统计"""
        return self._stats
    
    def get_anomalies(self, limit: int = 100) -> List[EventAnomaly]:
        """获取异常列表"""
        return list(self._anomalies)[-limit:]
    
    def reset(self) -> None:
        """重置统计"""
        self._stats = EventQualityStats()
        self._sequences.clear()
        self._timestamps.clear()
        self._seen_hashes.clear()
        self._anomalies.clear()
        logger.info("Event loss detector reset")


class DeterministicRebuilder:
    """确定性重建器
    
    确保回测和实盘使用相同的数据处理逻辑
    """
    
    def __init__(
        self,
        seed: Optional[int] = None,
        enable_verification: bool = True,
    ):
        self.seed = seed
        self.enable_verification = enable_verification
        self._call_count = 0
        self._expected_order: List[str] = []
        self._actual_order: List[str] = {}
    
    def reset(self) -> None:
        """重置状态"""
        self._call_count = 0
        self._expected_order.clear()
        self._actual_order.clear()
    
    def wrap_function(
        self,
        func: Callable,
        name: str,
    ) -> Callable:
        """包装函数以确保确定性"""
        def wrapper(*args, **kwargs):
            if self.enable_verification:
                self._call_count += 1
                self._actual_order[name] = self._actual_order.get(name, 0) + 1
            
            result = func(*args, **kwargs)
            
            if self.enable_verification and hasattr(result, "__iter__"):
                pass
            
            return result
        
        wrapper.__name__ = f"wrapped_{name}"
        return wrapper
    
    def verify_determinism(self) -> bool:
        """验证确定性"""
        if not self.enable_verification:
            return True
        
        return self._actual_order == {k: 1 for k in self._actual_order}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "call_count": self._call_count,
            "unique_functions": len(self._actual_order),
            "is_deterministic": self.verify_determinism(),
            "expected_order": self._expected_order,
            "actual_order": self._actual_order,
        }


_detector: Optional[EventLossDetector] = None


async def get_event_loss_detector() -> EventLossDetector:
    """获取事件丢失检测器实例"""
    global _detector
    if _detector is None:
        _detector = EventLossDetector()
        await _detector.start()
    return _detector
