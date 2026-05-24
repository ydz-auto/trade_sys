"""
Webhook Receiver - Webhook接收器
支持：新闻、行情、预警等数据接收
"""

import hmac
import hashlib
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from infrastructure.logging import get_logger
logger = get_logger("webhook")


class WebhookSource(Enum):
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    CRYPTOPANIC = "cryptopanic"
    NEWSAPI = "newsapi"
    BINANCE = "binance"
    OKX = "okx"
    ALERT = "alert"
    CUSTOM = "custom"


@dataclass
class WebhookPayload:
    """Webhook载荷"""
    source: str
    event_type: str
    data: Dict[str, Any]
    timestamp: float
    signature: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class WebhookHandler:
    """Webhook处理器"""
    source: WebhookSource
    handler: Callable
    validator: Optional[Callable] = None
    enabled: bool = True


class WebhookValidator:
    """Webhook验证器"""

    @staticmethod
    def validate_signature(
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """验证签名"""
        if algorithm == "sha256":
            expected = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha512":
            expected = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha512
            ).hexdigest()
        else:
            return False

        return hmac.compare_digest(expected, signature)

    @staticmethod
    def validate_timestamp(timestamp: float, max_age: int = 300) -> bool:
        """验证时间戳（防止重放攻击）"""
        current = time.time()
        return abs(current - timestamp) < max_age


class WebhookRouter:
    """Webhook路由"""

    def __init__(self):
        self.handlers: Dict[WebhookSource, WebhookHandler] = {}
        self._default_handlers: List[Callable] = []

    def register(
        self,
        source: WebhookSource,
        handler: Callable,
        validator: Optional[Callable] = None
    ):
        """注册处理器"""
        self.handlers[source] = WebhookHandler(
            source=source,
            handler=handler,
            validator=validator,
            enabled=True
        )
        logger.info(f"Registered webhook handler for: {source.value}")

    def register_default(self, handler: Callable):
        """注册默认处理器"""
        self._default_handlers.append(handler)

    async def handle(self, payload: WebhookPayload) -> bool:
        """处理Webhook"""
        source = WebhookSource(payload.source)

        handler = self.handlers.get(source)
        if not handler or not handler.enabled:
            for default_handler in self._default_handlers:
                try:
                    await default_handler(payload)
                except Exception as e:
                    logger.error(f"Default handler error: {e}")
            return True

        if handler.validator:
            try:
                if not handler.validator(payload):
                    logger.warning(f"Validation failed for {payload.source}")
                    return False
            except Exception as e:
                logger.error(f"Validator error: {e}")
                return False

        try:
            await handler.handler(payload)
            return True
        except Exception as e:
            logger.error(f"Webhook handler error: {e}")
            return False


class WebhookReceiver:
    """Webhook接收器"""

    def __init__(self, router: WebhookRouter = None):
        self.router = router or WebhookRouter()
        self._init_default_handlers()

    def _init_default_handlers(self):
        self.router.register_default(self._log_handler)

    async def _log_handler(self, payload: WebhookPayload):
        """日志处理器"""
        logger.info(
            f"Webhook received: source={payload.source}, "
            f"type={payload.event_type}, timestamp={payload.timestamp}"
        )

    async def receive(
        self,
        source: str,
        event_type: str,
        data: Dict,
        headers: Dict[str, str] = None,
        signature: str = None,
        raw_body: bytes = None
    ) -> bool:
        """接收Webhook"""
        payload = WebhookPayload(
            source=source,
            event_type=event_type,
            data=data,
            timestamp=time.time(),
            signature=signature,
            headers=headers or {}
        )

        return await self.router.handle(payload)


class NewsWebhookHandler:
    """新闻Webhook处理器"""

    def __init__(self):
        self.llm_client = None
        self.ws_server = None

    async def handle(self, payload: WebhookPayload):
        """处理新闻数据"""
        news_data = self._parse_news_payload(payload)

        if not news_data:
            logger.warning(f"Failed to parse news from {payload.source}")
            return

        analysis = await self._analyze_news(news_data)

        await self._store_news(news_data, analysis)

        if analysis.get("is_black_swan"):
            await self._trigger_black_swan_alert(news_data, analysis)

        await self._publish_to_websocket(news_data, analysis)

    def _parse_news_payload(self, payload: WebhookPayload) -> Optional[Dict]:
        """解析新闻载荷"""
        if payload.source == WebhookSource.COINDESK.value:
            return self._parse_coindesk(payload.data)
        elif payload.source == WebhookSource.COINTELEGRAPH.value:
            return self._parse_cointelegraph(payload.data)
        elif payload.source == WebhookSource.CRYPTOPANIC.value:
            return self._parse_cryptopanic(payload.data)
        else:
            return payload.data

    def _parse_coindesk(self, data: Dict) -> Dict:
        return {
            "title": data.get("headline", ""),
            "content": data.get("body", ""),
            "url": data.get("url", ""),
            "source": "coindesk",
            "published": data.get("published_at", int(time.time()))
        }

    def _parse_cointelegraph(self, data: Dict) -> Dict:
        return {
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "url": data.get("link", ""),
            "source": "cointelegraph",
            "published": data.get("pubDate", int(time.time()))
        }

    def _parse_cryptopanic(self, data: Dict) -> Dict:
        return {
            "title": data.get("title", ""),
            "content": data.get("text", ""),
            "url": data.get("url", ""),
            "source": "cryptopanic",
            "published": data.get("published_at", int(time.time()))
        }

    async def _analyze_news(self, news_data: Dict) -> Dict:
        """分析新闻"""
        try:
            from infrastructure.utilities.llm import LLMServiceClient

            if not self.llm_client:
                self.llm_client = LLMServiceClient()

            result = await self.llm_client.news_analysis(
                title=news_data.get("title", ""),
                content=news_data.get("content", "")
            )

            result["is_black_swan"] = result.get("black_swan_score", 0) > 0.5

            return result

        except Exception as e:
            logger.error(f"News analysis error: {e}")
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "is_black_swan": False
            }

    async def _store_news(self, news_data: Dict, analysis: Dict):
        """存储新闻"""
        try:
            from infrastructure.persistence.database import get_clickhouse_client

            client = get_clickhouse_client()

            client.execute(
                """
                INSERT INTO news (title, content, url, source, published, sentiment, sentiment_score, event_type, black_swan_score, created_at)
                VALUES
                """,
                [
                    {
                        "title": news_data.get("title", ""),
                        "content": news_data.get("content", ""),
                        "url": news_data.get("url", ""),
                        "source": news_data.get("source", ""),
                        "published": news_data.get("published", int(time.time())),
                        "sentiment": analysis.get("sentiment", "neutral"),
                        "sentiment_score": analysis.get("score", 0),
                        "event_type": analysis.get("event_type", "normal"),
                        "black_swan_score": analysis.get("black_swan_score", 0),
                        "created_at": datetime.now()
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to store news: {e}")

    async def _trigger_black_swan_alert(self, news_data: Dict, analysis: Dict):
        """触发黑天鹅预警"""
        try:
            from infrastructure.monitoring.alerting.sender import AlertManager

            alert_manager = AlertManager()
            alert_manager.send_alert(
                title=f"黑天鹅预警: {news_data.get('title', '')[:80]}",
                message=f"置信度: {analysis.get('confidence', 0):.2f}\n"
                        f"事件类型: {analysis.get('event_type', 'unknown')}\n"
                        f"影响市场: {', '.join(analysis.get('affected_markets', []))}",
                severity="critical",
                channels=["telegram", "webhook"]
            )
        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")

    async def _publish_to_websocket(self, news_data: Dict, analysis: Dict):
        """发布到WebSocket"""
        try:
            from infrastructure.messaging.websocket import get_ws_server

            ws_server = get_ws_server()

            import asyncio
            asyncio.create_task(
                ws_server.publish_news({
                    **news_data,
                    **analysis
                })
            )
        except Exception as e:
            logger.error(f"Failed to publish to WS: {e}")


class PriceWebhookHandler:
    """价格Webhook处理器"""

    async def handle(self, payload: WebhookPayload):
        """处理价格数据"""
        price_data = payload.data

        await self._store_price(price_data)
        await self._check_price_alerts(price_data)
        await self._publish_to_websocket(price_data)

    async def _store_price(self, price_data: Dict):
        """存储价格"""
        try:
            from infrastructure.persistence.database import get_clickhouse_client

            client = get_clickhouse_client()

            client.execute(
                """
                INSERT INTO prices (symbol, exchange, price, volume, bid, ask, timestamp)
                VALUES
                """,
                [
                    {
                        "symbol": price_data.get("symbol", ""),
                        "exchange": price_data.get("exchange", ""),
                        "price": price_data.get("price", 0),
                        "volume": price_data.get("volume", 0),
                        "bid": price_data.get("bid", 0),
                        "ask": price_data.get("ask", 0),
                        "timestamp": datetime.now()
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to store price: {e}")

    async def _check_price_alerts(self, price_data: Dict):
        """检查价格预警"""
        try:
            from infrastructure.monitoring.alerting.sender import AlertManager

            symbol = price_data.get("symbol", "")
            price = price_data.get("price", 0)

            alert_manager = AlertManager()

            alert_manager.check_price_threshold(symbol, price)

        except Exception as e:
            logger.error(f"Failed to check price alerts: {e}")

    async def _publish_to_websocket(self, price_data: Dict):
        """发布到WebSocket"""
        try:
            from infrastructure.messaging.websocket import get_ws_server

            ws_server = get_ws_server()

            import asyncio
            asyncio.create_task(
                ws_server.publish_price(
                    price_data.get("symbol", ""),
                    price_data
                )
            )
        except Exception as e:
            logger.error(f"Failed to publish to WS: {e}")


def get_webhook_receiver() -> WebhookReceiver:
    """获取Webhook接收器实例"""
    receiver = WebhookReceiver()
    receiver.router.register(
        WebhookSource.COINDESK,
        NewsWebhookHandler().handle
    )
    receiver.router.register(
        WebhookSource.COINTELEGRAPH,
        NewsWebhookHandler().handle
    )
    receiver.router.register(
        WebhookSource.CRYPTOPANIC,
        NewsWebhookHandler().handle
    )
    receiver.router.register(
        WebhookSource.BINANCE,
        PriceWebhookHandler().handle
    )
    return receiver
