"""
Ingestion Runtime - 数据采集运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集
- WebSocket 实时价格采集
- Twitter Push WebSocket 服务器
- Telegram 消息监听

业务逻辑：调用 services/data_service/ 和 services/aggregation_service/
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig
from runtime.shared import (
    RuntimeLifecycle,
    RuntimeMetrics,
    RuntimeConsumer,
    ConsumerConfig,
    RuntimePublisher,
    PublisherConfig,
    RuntimeHealthCheck,
)
from infrastructure.messaging import Topics
from shared.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS
from dataclasses import dataclass, field


@dataclass
class IngestionConfig(RuntimeConfig):
    """Ingestion Runtime 配置"""
    name: str = "ingestion_runtime"
    collection_interval: int = 300
    enable_websocket: bool = True
    websocket_symbols: list = None
    enable_twitter_push: bool = True
    twitter_push_host: str = "localhost"
    twitter_push_port: int = 8765
    enable_telegram: bool = False
    
    def __post_init__(self):
        if self.websocket_symbols is None:
            self.websocket_symbols = ["btcusdt", "ethusdt", "solusdt"]


class IngestionRuntime(BaseRuntime):
    """
    Ingestion Runtime - 数据采集运行时
    
    只负责运行时编排，业务逻辑在 services/data_service/
    """
    
    def __init__(self, config: IngestionConfig = None):
        config = config or IngestionConfig.from_env()
        super().__init__(config)
        self.config: IngestionConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.news_collector = None
        self.odaily_adapter = None
        self.odaily_consumer = None
        self.market_collector = None
        self.aggregator = None
        self.publisher: Optional[RuntimePublisher] = None
        self.ws_adapter = None
        self._ws_task: Optional[asyncio.Task] = None
        
        self.twitter_push_collector = None
        self.twitter_push_server = None
        self._twitter_push_task: Optional[asyncio.Task] = None
        
        self.telegram_adapter = None
        self._telegram_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> None:
        """初始化运行时组件"""
        self.logger.info("Initializing Ingestion Runtime...")
        
        self.lifecycle = RuntimeLifecycle("ingestion")
        self.metrics = RuntimeMetrics("ingestion")
        self.health_check = RuntimeHealthCheck("ingestion")
        
        try:
            from services.data_service.collectors.news_collector import NewsCollector
            self.news_collector = NewsCollector()
            self.logger.info("News collector initialized")
        except Exception as e:
            self.logger.warning(f"News collector init failed: {e}")
        
        try:
            from services.data_service.adapters.odaily_adapter import get_odaily_adapter
            self.odaily_adapter = get_odaily_adapter()
            self.logger.info("Odaily adapter initialized")
        except Exception as e:
            self.logger.warning(f"Odaily adapter init failed: {e}")
            self.odaily_adapter = None
        
        try:
            from services.event_service.consumers.odaily_consumer import get_odaily_consumer
            self.odaily_consumer = await get_odaily_consumer()
            self.logger.info("Odaily consumer initialized")
        except Exception as e:
            self.logger.warning(f"Odaily consumer init failed: {e}")
            self.odaily_consumer = None
        
        try:
            from services.aggregation_service.aggregators.candle.candle_aggregator import get_timeframe_aggregator
            self.aggregator = get_timeframe_aggregator()
            self.logger.info("Aggregator initialized")
        except Exception as e:
            self.logger.warning(f"Aggregator init failed: {e}")
        
        try:
            kafka_servers = KAFKA_BOOTSTRAP_SERVERS
            self.publisher = RuntimePublisher(PublisherConfig(
                bootstrap_servers=kafka_servers,
                topic=Topics.EVENTS,
            ))
            await self.publisher.start()
            self.logger.info("Kafka publisher initialized")
        except Exception as e:
            self.logger.warning(f"Kafka publisher init failed: {e}")
        
        if self.config.enable_websocket:
            await self._init_websocket()
        
        if self.config.enable_twitter_push:
            await self._init_twitter_push()
        
        if self.config.enable_telegram:
            await self._init_telegram()
        
        self.health_check.register_check("news_collector", self._check_news_collector)
        self.health_check.register_check("aggregator", self._check_aggregator)
        self.health_check.register_check("publisher", self._check_publisher)
        self.health_check.register_check("websocket", self._check_websocket)
        self.health_check.register_check("twitter_push", self._check_twitter_push)
        self.health_check.register_check("telegram", self._check_telegram)
        
        self.logger.info("Ingestion Runtime initialized successfully")
    
    async def _init_websocket(self):
        """初始化 WebSocket 价格采集"""
        try:
            from services.data_service.collectors.binance_websocket import (
                BinanceWebSocketAdapter,
                BinanceConfig,
                StreamType,
            )
            
            config = BinanceConfig(
                symbols=self.config.websocket_symbols,
                stream_types=[
                    StreamType.MARK_PRICE,
                    StreamType.AGG_TRADE,
                    StreamType.LIQUIDATION,
                ]
            )
            
            self.ws_adapter = BinanceWebSocketAdapter(config)
            
            self.ws_adapter.on_price_update = self._on_price_update
            self.ws_adapter.on_trade = self._on_trade
            self.ws_adapter.on_liquidation = self._on_liquidation
            
            self.logger.info(f"WebSocket adapter initialized for {self.config.websocket_symbols}")
            
        except Exception as e:
            self.logger.warning(f"WebSocket init failed: {e}")
    
    async def _init_twitter_push(self):
        """初始化 Twitter Push WebSocket 服务器"""
        try:
            from services.data_service.collectors.twitter_push_collector import (
                TwitterPushCollector,
                TwitterPushConfig,
            )
            
            self.twitter_push_collector = TwitterPushCollector(TwitterPushConfig(
                host=self.config.twitter_push_host,
                port=self.config.twitter_push_port,
            ))
            
            self.twitter_push_collector.register_callback(self._on_twitter_event)
            
            self.logger.info(f"Twitter Push collector initialized on {self.config.twitter_push_host}:{self.config.twitter_push_port}")
            
        except Exception as e:
            self.logger.warning(f"Twitter Push init failed: {e}")
    
    async def _init_telegram(self):
        """初始化 Telegram 适配器"""
        try:
            from services.data_service.collectors.telegram_adapter import (
                TelegramAdapter,
                TelegramConfig,
            )
            import os
            
            config = TelegramConfig(
                api_id=int(os.getenv("TG_API_ID", "0")) or None,
                api_hash=os.getenv("TG_API_HASH") or None,
            )
            
            self.telegram_adapter = TelegramAdapter(config)
            self.telegram_adapter.on_event = self._on_telegram_event
            
            self.logger.info("Telegram adapter initialized")
            
        except Exception as e:
            self.logger.warning(f"Telegram init failed: {e}")
    
    async def _on_twitter_event(self, event):
        """处理 Twitter 事件"""
        try:
            self.metrics.increment("twitter_events")
            
            if self.publisher:
                await self.publisher.publish(event.to_dict())
                self.logger.info(f"Twitter event published: {event.title[:50]}...")
                
        except Exception as e:
            self.logger.error(f"Error processing Twitter event: {e}")
    
    async def _on_telegram_event(self, event):
        """处理 Telegram 事件"""
        try:
            self.metrics.increment("telegram_events")
            
            if self.publisher:
                await self.publisher.publish(event.to_dict())
                self.logger.info(f"Telegram event published: {event.title[:50]}...")
                
        except Exception as e:
            self.logger.error(f"Error processing Telegram event: {e}")
    
    async def _on_price_update(self, event):
        """处理价格更新"""
        try:
            symbol = event.metadata.get("symbol", "").upper()
            price = event.metadata.get("mark_price", 0)
            
            self.metrics.increment("price_updates")
            
            if self.publisher:
                await self.publisher.publish({
                    "event_type": "price_update",
                    "symbol": symbol,
                    "price": price,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "binance_websocket",
                })
            
        except Exception as e:
            self.logger.error(f"Error processing price update: {e}")
    
    async def _on_trade(self, event):
        """处理成交"""
        try:
            self.metrics.increment("trades")
            
            if self.publisher:
                await self.publisher.publish(event.to_dict())
                
        except Exception as e:
            self.logger.error(f"Error processing trade: {e}")
    
    async def _on_liquidation(self, event):
        """处理强平"""
        try:
            self.metrics.increment("liquidations")
            
            if self.publisher:
                await self.publisher.publish(event.to_dict())
                
        except Exception as e:
            self.logger.error(f"Error processing liquidation: {e}")
    
    async def _check_news_collector(self) -> bool:
        """检查新闻采集器"""
        return self.news_collector is not None
    
    async def _check_aggregator(self) -> bool:
        """检查聚合器"""
        return self.aggregator is not None
    
    async def _check_publisher(self) -> bool:
        """检查Kafka发布者"""
        return self.publisher is not None and await self.publisher.is_healthy()
    
    async def _check_websocket(self) -> bool:
        """检查 WebSocket 连接"""
        return self.ws_adapter is not None and self.ws_adapter.is_connected
    
    async def _check_twitter_push(self) -> bool:
        """检查 Twitter Push"""
        return self.twitter_push_collector is not None
    
    async def _check_telegram(self) -> bool:
        """检查 Telegram"""
        return self.telegram_adapter is not None and self.telegram_adapter.is_running
    
    async def shutdown(self) -> None:
        """关闭运行时组件"""
        self.logger.info("Shutting down Ingestion Runtime...")
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        
        if self._twitter_push_task:
            self._twitter_push_task.cancel()
            try:
                await self._twitter_push_task
            except asyncio.CancelledError:
                pass
        
        if self._telegram_task:
            self._telegram_task.cancel()
            try:
                await self._telegram_task
            except asyncio.CancelledError:
                pass
        
        if self.ws_adapter:
            await self.ws_adapter.disconnect()
        
        if self.telegram_adapter:
            await self.telegram_adapter.stop()
        
        if self.publisher:
            await self.publisher.stop()
        
        await self.lifecycle.transition_to_stopped()
        
        self.logger.info(f"Ingestion Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Ingestion Runtime main loop...")
        
        await self.lifecycle.transition_to_running()
        
        if self.ws_adapter:
            self._ws_task = asyncio.create_task(self._run_websocket())
        
        if self.odaily_consumer:
            await self.odaily_consumer.connect()
            asyncio.create_task(self.odaily_consumer.start_consuming())
            self.logger.info("Odaily consumer started")
        
        if self.config.enable_twitter_push and self.twitter_push_collector:
            self._twitter_push_task = asyncio.create_task(self._run_twitter_push_server())
            self.logger.info(f"Twitter Push server started on port {self.config.twitter_push_port}")
        
        if self.config.enable_telegram and self.telegram_adapter:
            self._telegram_task = asyncio.create_task(self._run_telegram_listener())
            self.logger.info("Telegram listener started")
        
        while not self.context.is_shutdown_requested():
            try:
                with self.metrics.timing("collection_cycle"):
                    await self._collect_data()
                
                self.metrics.increment("collection_cycles")
                
                await asyncio.sleep(self.config.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)
                await asyncio.sleep(10)
    
    async def _run_twitter_push_server(self):
        """运行 Twitter Push WebSocket 服务器"""
        try:
            import websockets
            from websockets.server import WebSocketServerProtocol
            
            async def handle_connection(websocket: WebSocketServerProtocol, path: str):
                client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
                self.logger.info(f"Twitter Push client connected: {client_id}")
                
                try:
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type", "unknown")
                            
                            if msg_type == "ping":
                                await websocket.send(json.dumps({
                                    "type": "pong",
                                    "timestamp": datetime.now().timestamp()
                                }))
                            elif msg_type == "tweet":
                                tweet_data = data.get("data", {})
                                event = self.twitter_push_collector.process_tweet(tweet_data)
                                if event:
                                    await websocket.send(json.dumps({
                                        "type": "tweet_event",
                                        "event": event.to_dict()
                                    }))
                        except json.JSONDecodeError:
                            self.logger.error(f"Invalid JSON from {client_id}")
                except websockets.exceptions.ConnectionClosed:
                    self.logger.info(f"Twitter Push client disconnected: {client_id}")
            
            async with websockets.serve(
                handle_connection,
                self.config.twitter_push_host,
                self.config.twitter_push_port,
                ping_interval=30,
                ping_timeout=10
            ):
                self.logger.info(f"Twitter Push WebSocket server listening on ws://{self.config.twitter_push_host}:{self.config.twitter_push_port}")
                await asyncio.Future()
                
        except Exception as e:
            self.logger.error(f"Twitter Push server error: {e}")
    
    async def _run_telegram_listener(self):
        """运行 Telegram 监听器"""
        try:
            await self.telegram_adapter.listen()
        except Exception as e:
            self.logger.error(f"Telegram listener error: {e}")
    
    async def _run_websocket(self):
        """运行 WebSocket 连接"""
        while not self.context.is_shutdown_requested():
            try:
                await self.ws_adapter.connect()
                await self.ws_adapter.listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # REST fallback 模式下 listen() 会正常返回，不需要重试
                if self.ws_adapter._rest_fallback_mode:
                    self.logger.info("REST fallback mode active, waiting...")
                    await asyncio.sleep(60)
                    continue
                self.logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)
    
    async def _collect_data(self) -> None:
        """采集数据（运行时编排）"""
        if not self.news_collector and not self.odaily_adapter:
            self.logger.warning("No collectors available")
            return
        
        self.logger.info("Collecting news from all sources...")
        
        # Collect from standard news sources
        if self.news_collector:
            try:
                result = await self.news_collector.collect()
                
                if result.success and result.data:
                    self.logger.info(f"Collected {len(result.data)} standard news")
                    self.metrics.increment("news_collected", len(result.data))
                    
                    if self.publisher:
                        await self._publish_news_events(result.data[:10])
                        self.logger.info(f"Published {len(result.data[:10])} news events to Kafka")
                    
                    for news in result.data[:10]:
                        self.metrics.increment("news_processed")
                else:
                    self.logger.warning(f"News collection failed or no data: {result.error}")
            except Exception as e:
                self.logger.error(f"News collection error: {e}")
        
        # Collect from Odaily skill
        if self.odaily_adapter:
            try:
                self.logger.info("Collecting from Odaily skill...")
                raw_data = await self.odaily_adapter.fetch_raw_data()
                odaily_events = self.odaily_adapter.normalize(raw_data)
                
                if odaily_events:
                    self.logger.info(f"Collected {len(odaily_events)} Odaily events")
                    self.metrics.increment("odaily_collected", len(odaily_events))
                    
                    if self.publisher:
                        await self._publish_odaily_events(odaily_events)
                        self.logger.info(f"Published {len(odaily_events)} Odaily events to Kafka")
                else:
                    self.logger.warning("No Odaily events collected")
            except Exception as e:
                self.logger.error(f"Odaily collection error: {e}")
    
    async def _publish_news_events(self, news_items: list) -> None:
        """将新闻事件发布到Kafka"""
        from datetime import datetime
        import uuid
        
        for news in news_items:
            try:
                event = {
                    "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                    "trace_id": f"trc_{uuid.uuid4().hex[:16]}",
                    "event_type": "news",
                    "source": "ingestion_runtime",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "id": news.id,
                        "title": news.title,
                        "content": news.content,
                        "source": news.source,
                        "url": news.url,
                        "published": news.published,
                        "sentiment": news.sentiment,
                        "sentiment_score": news.sentiment_score,
                        "event_type": news.event_type,
                        "affected_symbols": news.affected_symbols,
                    }
                }
                
                await self.publisher.publish(event, key=news.id)
                
            except Exception as e:
                self.logger.error(f"Failed to publish news event: {e}")
    
    async def _publish_odaily_events(self, odaily_events: list) -> None:
        """将Odaily事件发布到Kafka (raw.odaily topic)
        
        数据流: 采集层 → Kafka(raw.odaily) → OdailyConsumer(LLM增强) → Redis → API
        """
        from datetime import datetime
        import uuid
        
        original_topic = self.publisher.config.topic
        self.publisher.config.topic = Topics.raw_odaily()
        
        try:
            for event in odaily_events:
                try:
                    event_dict = {
                        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
                        "trace_id": f"trc_{uuid.uuid4().hex[:16]}",
                        "event_type": "odaily_raw",
                        "source": "clawhub_odaily",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "id": event.id,
                            "title": event.title,
                            "content": event.content,
                            "source": event.source,
                            "sentiment": event.sentiment,
                            "importance": event.importance,
                            "symbols": event.symbols,
                            "tags": event.tags,
                            "metadata": event.metadata,
                        }
                    }
                    
                    await self.publisher.publish(event_dict, key=event.id)
                    
                except Exception as e:
                    self.logger.error(f"Failed to publish Odaily event: {e}")
                    
        finally:
            self.publisher.config.topic = original_topic
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "health_check": await self.health_check.to_dict() if self.health_check else {},
        })
        return health


_ingestion_runtime: Optional[IngestionRuntime] = None


def get_ingestion_runtime() -> IngestionRuntime:
    """获取 Ingestion Runtime 单例"""
    global _ingestion_runtime
    if _ingestion_runtime is None:
        _ingestion_runtime = IngestionRuntime()
    return _ingestion_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Ingestion Runtime - Data Collection")
    print("=" * 60)
    
    runtime = get_ingestion_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
