"""
Data Source Manager - 数据源管理器

统一管理所有实时数据源：
- QQ (NapCatQQ)
- Telegram (Telethon)
- Binance WebSocket

功能：
- 统一启动/停止
- 事件统一发布到 Kafka
- 状态监控
- 熔断保护
"""

import asyncio
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger
from engines.adapters.contracts import StandardEvent
from infrastructure.messaging.kafka_producer import kafka_producer

try:
    from engines.adapters.data.sources.qq_realtime import QQRealtimeSource
    from engines.adapters.data.sources.telegram_realtime import TelegramRealtimeSource
    SOURCES_AVAILABLE = True
except ImportError as e:
    SOURCES_AVAILABLE = False
    QQRealtimeSource = None
    TelegramRealtimeSource = None
    print(f"Warning: Real-time sources not available: {e}")


logger = get_logger("data_service.source_manager")


class SourceStatus(str, Enum):
    """数据源状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class SourceInfo:
    """数据源信息"""
    name: str
    source_type: str
    status: SourceStatus = SourceStatus.STOPPED
    instance: Any = None
    events_count: int = 0
    errors_count: int = 0
    last_event_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    error_message: Optional[str] = None


class DataSourceManager:
    """数据源管理器

    统一管理所有实时数据源：
    - 启动/停止所有数据源
    - 事件统一发布到 Kafka
    - 状态监控
    - 熔断保护
    """

    def __init__(self):
        self._sources: Dict[str, SourceInfo] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._kafka_connected = False

    def register_source(
        self,
        name: str,
        source_type: str,
        instance: Any
    ) -> None:
        """注册数据源"""
        info = SourceInfo(
            name=name,
            source_type=source_type,
            instance=instance,
            status=SourceStatus.STOPPED
        )
        self._sources[name] = info
        logger.info(f"Registered source: {name} ({source_type})")

    async def _publish_event(self, event: StandardEvent) -> None:
        try:
            from infrastructure.messaging.schema.base_event import RawDataEvent, EventSource

            if not self._kafka_connected:
                return

            raw_event = RawDataEvent(
                source=EventSource.DATA_SERVICE,
                symbol=event.symbols[0] if event.symbols else "BTCUSDT",
                event_time_ms=int(event.timestamp * 1000) if isinstance(event.timestamp, (int, float)) else event.timestamp,
                data_type="event",
                data={
                    "id": event.id,
                    "timestamp": event.timestamp,
                    "source": event.source,
                    "event_type": event.event_type,
                    "title": event.title,
                    "content": event.content,
                    "sentiment": event.sentiment,
                    "importance": event.importance,
                    "symbols": event.symbols,
                    "tags": event.tags,
                    "metadata": event.metadata,
                },
                data_source=event.source,
            )

            key = event.symbols[0] if event.symbols else event.source

            await kafka_producer.publish_raw_data(
                data=raw_event.to_dict(),
                symbol=key
            )

            logger.debug(f"Published event: {event.title[:50]}")

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    async def _setup_source(self, name: str) -> bool:
        """设置数据源回调"""
        if name not in self._sources:
            return False

        info = self._sources[name]
        instance = info.instance

        if not instance:
            return False

        # 设置事件回调
        async def on_event(event: StandardEvent):
            info.events_count += 1
            info.last_event_time = datetime.now()
            await self._publish_event(event)

        instance.on_event = on_event

        return True

    async def start_source(self, name: str) -> bool:
        """启动单个数据源"""
        if name not in self._sources:
            logger.error(f"Source not found: {name}")
            return False

        info = self._sources[name]

        if info.status == SourceStatus.RUNNING:
            logger.warning(f"Source already running: {name}")
            return True

        try:
            info.status = SourceStatus.STARTING
            logger.info(f"Starting source: {name}")

            # 设置回调
            await self._setup_source(name)

            # 启动监听
            task = asyncio.create_task(self._run_source(name))
            self._tasks.append(task)

            info.status = SourceStatus.RUNNING
            info.start_time = datetime.now()

            logger.info(f"Source started: {name}")
            return True

        except Exception as e:
            info.status = SourceStatus.ERROR
            info.error_message = str(e)
            logger.error(f"Failed to start source {name}: {e}")
            return False

    async def _run_source(self, name: str) -> None:
        """运行数据源"""
        if name not in self._sources:
            return

        info = self._sources[name]
        instance = info.instance

        try:
            if hasattr(instance, 'listen'):
                await instance.listen()
            else:
                logger.warning(f"Source {name} has no listen method")
                # 模拟运行
                while self._running:
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info(f"Source {name} cancelled")
        except Exception as e:
            info.errors_count += 1
            info.error_message = str(e)
            info.status = SourceStatus.ERROR
            logger.error(f"Source {name} error: {e}")

    async def stop_source(self, name: str) -> bool:
        """停止单个数据源"""
        if name not in self._sources:
            return False

        info = self._sources[name]

        try:
            if info.instance and hasattr(info.instance, 'stop'):
                await info.instance.stop()

            info.status = SourceStatus.STOPPED
            logger.info(f"Source stopped: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop source {name}: {e}")
            return False

    async def start_all(self) -> Dict[str, bool]:
        """启动所有数据源"""
        if not SOURCES_AVAILABLE:
            logger.warning("Real-time sources not available")
            return {}

        self._running = True

        # 连接 Kafka
        try:
            await kafka_producer.connect()
            self._kafka_connected = kafka_producer.is_connected
            if self._kafka_connected:
                logger.info("Connected to Kafka")
            else:
                logger.warning("Kafka not connected, events will not be published")
        except Exception as e:
            logger.warning(f"Failed to connect to Kafka: {e}")
            self._kafka_connected = False

        # 启动所有数据源
        results = {}
        for name in self._sources:
            results[name] = await self.start_source(name)

        return results

    async def stop_all(self) -> None:
        """停止所有数据源"""
        self._running = False

        # 停止所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待任务结束
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # 停止所有数据源
        for name in list(self._sources.keys()):
            await self.stop_source(name)

        # 断开 Kafka
        if self._kafka_connected:
            await kafka_producer.disconnect()
            self._kafka_connected = False

        logger.info("All sources stopped")

    def get_status(self) -> Dict[str, Any]:
        """获取所有数据源状态"""
        status = {}
        for name, info in self._sources.items():
            status[name] = {
                "type": info.source_type,
                "status": info.status.value,
                "events_count": info.events_count,
                "errors_count": info.errors_count,
                "last_event_time": info.last_event_time.isoformat() if info.last_event_time else None,
                "start_time": info.start_time.isoformat() if info.start_time else None,
                "error_message": info.error_message
            }
        return status

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_events = sum(info.events_count for info in self._sources.values())
        total_errors = sum(info.errors_count for info in self._sources.values())
        running_count = sum(1 for info in self._sources.values() if info.status == SourceStatus.RUNNING)

        return {
            "total_sources": len(self._sources),
            "running_sources": running_count,
            "total_events": total_events,
            "total_errors": total_errors,
            "kafka_connected": self._kafka_connected
        }


# 全局实例
_source_manager: Optional[DataSourceManager] = None


def get_source_manager() -> DataSourceManager:
    """获取数据源管理器单例"""
    global _source_manager
    if _source_manager is None:
        _source_manager = DataSourceManager()
        _init_sources()
    return _source_manager


def _init_sources() -> None:
    """初始化数据源"""
    global _source_manager

    if not SOURCES_AVAILABLE:
        return

    manager = _source_manager

    # QQ 数据源
    qq_use_mock = os.getenv("QQ_USE_MOCK", "true").lower() == "true"
    qq_groups = os.getenv("QQ_WATCH_GROUPS", "").split(",") if os.getenv("QQ_WATCH_GROUPS") else None

    if not os.getenv("QQ_DISABLE", "false").lower() == "true":
        try:
            qq_source = QQRealtimeSource(
                ws_url=os.getenv("QQ_WS_URL") or os.getenv("QQ_HTTP_WS_URL", "ws://127.0.0.1:3001"),
                watch_groups=qq_groups,
                use_mock=qq_use_mock
            )
            manager.register_source(
                name="qq",
                source_type="realtime",
                instance=qq_source
            )
        except Exception as e:
            logger.error(f"Failed to initialize QQ source: {e}")

    # Telegram 数据源
    tg_use_mock = os.getenv("TELEGRAM_USE_MOCK", "true").lower() == "true"
    tg_channels = os.getenv("TELEGRAM_CHANNELS", "").split(",") if os.getenv("TELEGRAM_CHANNELS") else None

    if not os.getenv("TELEGRAM_DISABLE", "false").lower() == "true":
        try:
            tg_source = TelegramRealtimeSource(
                api_id=int(os.getenv("TELEGRAM_API_ID", "0")) if os.getenv("TELEGRAM_API_ID") else None,
                api_hash=os.getenv("TELEGRAM_API_HASH", ""),
                phone=os.getenv("TELEGRAM_PHONE", ""),
                channels=tg_channels,
                use_mock=tg_use_mock
            )
            manager.register_source(
                name="telegram",
                source_type="realtime",
                instance=tg_source
            )
        except Exception as e:
            logger.error(f"Failed to initialize Telegram source: {e}")

    logger.info(f"Initialized {len(manager._sources)} data sources")


# 便捷函数
async def start_sources():
    """启动所有数据源"""
    manager = get_source_manager()
    return await manager.start_all()


async def stop_sources():
    """停止所有数据源"""
    manager = get_source_manager()
    await manager.stop_all()


def get_source_status():
    """获取数据源状态"""
    manager = get_source_manager()
    return manager.get_status()


def get_source_stats():
    """获取数据源统计"""
    manager = get_source_manager()
    return manager.get_stats()
