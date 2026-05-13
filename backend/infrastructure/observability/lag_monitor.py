"""
Consumer Lag Monitor - Consumer Lag 监控服务
监控所有 Kafka Consumer 的 Lag 情况

功能：
1. 实时 Lag 监控
2. Lag 告警
3. Consumer 健康检查
4. Lag 历史记录
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from infrastructure.logging import get_logger

try:
    from aiokafka import AIOKafkaAdminClient, AIOKafkaConsumer
    from aiokafka.admin import KafkaAdminClient
    KAFKA_ADMIN_AVAILABLE = True
except ImportError:
    KAFKA_ADMIN_AVAILABLE = False
    AIOKafkaAdminClient = None
    AIOKafkaConsumer = None

logger = get_logger("infrastructure.observability.lag_monitor")


class LagLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class LagThreshold:
    """Lag 阈值配置"""
    warning: int = 1000
    critical: int = 10000
    check_interval_seconds: int = 10


@dataclass
class ConsumerLag:
    """Consumer Lag 信息"""
    group_id: str
    topic: str
    partition: int
    current_offset: int
    end_offset: int
    lag: int
    level: LagLevel = LagLevel.NORMAL
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "topic": self.topic,
            "partition": self.partition,
            "current_offset": self.current_offset,
            "end_offset": self.end_offset,
            "lag": self.lag,
            "level": self.level.value,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class LagSnapshot:
    """Lag 快照"""
    timestamp: datetime
    total_lag: int
    max_lag: int
    consumer_count: int
    topic_count: int
    lag_by_consumer: Dict[str, int]
    lag_by_topic: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_lag": self.total_lag,
            "max_lag": self.max_lag,
            "consumer_count": self.consumer_count,
            "topic_count": self.topic_count,
            "lag_by_consumer": self.lag_by_consumer,
            "lag_by_topic": self.lag_by_topic,
        }


class ConsumerLagMonitor:
    """Consumer Lag 监控器
    
    监控所有 Consumer Group 的 Lag 情况
    支持：
    - 实时 Lag 监控
    - Lag 告警
    - Consumer 健康检查
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        thresholds: Optional[LagThreshold] = None,
        history_size: int = 100,
    ):
        if not KAFKA_ADMIN_AVAILABLE:
            raise RuntimeError("aiokafka not installed. Run: pip install aiokafka")
        
        self.bootstrap_servers = bootstrap_servers
        self.thresholds = thresholds or LagThreshold()
        self.history_size = history_size
        
        self._admin: Optional[AIOKafkaAdminClient] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._consumers: Dict[str, AIOKafkaConsumer] = {}
        self._lag_cache: Dict[str, List[ConsumerLag]] = {}
        self._history: deque[LagSnapshot] = deque(maxlen=history_size)
        self._alert_callbacks: List[callable] = []
    
    async def connect(self) -> None:
        """连接"""
        if self._admin is not None:
            return
        
        self._admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        await self._admin.start()
        logger.info("Lag monitor connected")
    
    async def disconnect(self) -> None:
        """断开连接"""
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        for consumer in self._consumers.values():
            await consumer.stop()
        self._consumers.clear()
        
        if self._admin:
            await self._admin.close()
            self._admin = None
        
        logger.info("Lag monitor disconnected")
    
    async def start(self) -> None:
        """启动监控"""
        await self.connect()
        
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """停止监控"""
        await self.disconnect()
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._collect_lag()
                await self._check_thresholds()
                await self._record_snapshot()
            except Exception as e:
                logger.error(f"Lag monitor error: {e}")
            
            await asyncio.sleep(self.thresholds.check_interval_seconds)
    
    async def _collect_lag(self) -> None:
        """收集 Lag 信息"""
        if not self._admin:
            return
        
        try:
            groups = await self._admin.list_consumer_groups()
            
            for group in groups:
                group_id = group.group_id
                
                if group_id not in self._consumers:
                    consumer = AIOKafkaConsumer(
                        bootstrap_servers=self.bootstrap_servers,
                        group_id=group_id,
                        auto_offset_reset="latest",
                    )
                    await consumer.start()
                    self._consumers[group_id] = consumer
                
                consumer = self._consumers[group_id]
                lags = []
                
                for tp in consumer.assignment():
                    try:
                        current = await consumer.position(tp)
                        _, end = await consumer.get_watermarks(tp)
                        
                        lag = max(0, end - current)
                        level = self._calculate_lag_level(lag)
                        
                        consumer_lag = ConsumerLag(
                            group_id=group_id,
                            topic=tp.topic,
                            partition=tp.partition,
                            current_offset=current,
                            end_offset=end,
                            lag=lag,
                            level=level,
                        )
                        lags.append(consumer_lag)
                        
                    except Exception as e:
                        logger.debug(f"Failed to get lag for {tp}: {e}")
                
                self._lag_cache[group_id] = lags
                
        except Exception as e:
            logger.error(f"Failed to collect lag: {e}")
    
    async def _check_thresholds(self) -> None:
        """检查阈值"""
        alerts = []
        
        for group_id, lags in self._lag_cache.items():
            for lag in lags:
                if lag.level != LagLevel.NORMAL:
                    alert = {
                        "type": "lag_threshold",
                        "group_id": group_id,
                        "topic": lag.topic,
                        "partition": lag.partition,
                        "lag": lag.lag,
                        "level": lag.level.value,
                        "timestamp": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
        
        if alerts:
            logger.warning(f"Lag alerts: {len(alerts)}")
            for callback in self._alert_callbacks:
                try:
                    await callback(alerts)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
    
    async def _record_snapshot(self) -> None:
        """记录快照"""
        snapshot = self.get_snapshot()
        self._history.append(snapshot)
    
    def _calculate_lag_level(self, lag: int) -> LagLevel:
        """计算 Lag 级别"""
        if lag >= self.thresholds.critical:
            return LagLevel.CRITICAL
        elif lag >= self.thresholds.warning:
            return LagLevel.WARNING
        return LagLevel.NORMAL
    
    def register_alert_callback(self, callback: callable) -> None:
        """注册告警回调"""
        self._alert_callbacks.append(callback)
    
    def get_lag_by_consumer(self, group_id: str) -> List[ConsumerLag]:
        """获取指定 Consumer 的 Lag"""
        return self._lag_cache.get(group_id, [])
    
    def get_all_lag(self) -> Dict[str, List[ConsumerLag]]:
        """获取所有 Lag 信息"""
        return self._lag_cache.copy()
    
    def get_snapshot(self) -> LagSnapshot:
        """获取当前快照"""
        all_lags = []
        for lags in self._lag_cache.values():
            all_lags.extend(lags)
        
        lag_by_consumer: Dict[str, int] = {}
        lag_by_topic: Dict[str, int] = {}
        
        for lag in all_lags:
            lag_by_consumer[lag.group_id] = lag_by_consumer.get(lag.group_id, 0) + lag.lag
            lag_by_topic[lag.topic] = lag_by_topic.get(lag.topic, 0) + lag.lag
        
        return LagSnapshot(
            timestamp=datetime.now(),
            total_lag=sum(l.lag for l in all_lags),
            max_lag=max((l.lag for l in all_lags), default=0),
            consumer_count=len(self._lag_cache),
            topic_count=len(lag_by_topic),
            lag_by_consumer=lag_by_consumer,
            lag_by_topic=lag_by_topic,
        )
    
    def get_history(self) -> List[LagSnapshot]:
        """获取历史快照"""
        return list(self._history)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        snapshot = self.get_snapshot()
        history = self.get_history()
        
        return {
            "current": snapshot.to_dict(),
            "history_size": len(history),
            "monitored_consumers": len(self._lag_cache),
            "alert_thresholds": {
                "warning": self.thresholds.warning,
                "critical": self.thresholds.critical,
            },
        }


_lag_monitor: Optional[ConsumerLagMonitor] = None


async def get_lag_monitor(
    bootstrap_servers: str = "localhost:9092",
) -> ConsumerLagMonitor:
    """获取 Lag Monitor 实例"""
    global _lag_monitor
    if _lag_monitor is None:
        _lag_monitor = ConsumerLagMonitor(bootstrap_servers=bootstrap_servers)
        await _lag_monitor.start()
    return _lag_monitor
