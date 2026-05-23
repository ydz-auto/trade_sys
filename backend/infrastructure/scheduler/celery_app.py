"""
Celery Scheduler - 定时任务调度
"""

import os
from typing import Optional
from kombu import Queue
from celery import Celery
from celery.schedules import crontab

from infrastructure.logging import get_logger
logger = get_logger("scheduler")


def get_celery_app(name: str = "tradeagent") -> Celery:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    broker_url = os.getenv("CELERY_BROKER_URL", redis_url)
    result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_url)

    app = Celery(name)
    app.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,
        task_soft_time_limit=240,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
    )

    app.conf.task_queues = (
        Queue("collectors", routing_key="collector.#"),
        Queue("data", routing_key="data.#"),
        Queue("alerts", routing_key="alert.#"),
        Queue("default"),
    )

    return app


celery_app = get_celery_app()


celery_app.conf.beat_schedule = {
    "collect-prices-every-minute": {
        "task": "tasks.collect_prices",
        "schedule": 60.0,
        "options": {"queue": "collectors"}
    },
    "collect-etf-hourly": {
        "task": "tasks.collect_etf",
        "schedule": 3600.0,
        "options": {"queue": "collectors"}
    },
    "collect-news-every-5-min": {
        "task": "tasks.collect_news",
        "schedule": 300.0,
        "options": {"queue": "collectors"}
    },
    "collect-macro-hourly": {
        "task": "tasks.collect_macro",
        "schedule": 3600.0,
        "options": {"queue": "collectors"}
    },
    "collect-social-every-5-min": {
        "task": "tasks.collect_social",
        "schedule": 300.0,
        "options": {"queue": "collectors"}
    },
    "collect-trader-every-5-min": {
        "task": "tasks.collect_trader",
        "schedule": 300.0,
        "options": {"queue": "collectors"}
    },
    "analyze-news-hourly": {
        "task": "tasks.analyze_news",
        "schedule": 3600.0,
        "options": {"queue": "data"}
    },
    "check-black-swan-every-minute": {
        "task": "tasks.check_black_swan",
        "schedule": 60.0,
        "options": {"queue": "alerts"}
    },
    "publish-ws-data-every-10s": {
        "task": "tasks.publish_ws_data",
        "schedule": 10.0,
        "options": {"queue": "data"}
    },
}


@celery_app.task(name="tasks.collect_prices", bind=True, max_retries=3)
def collect_prices(self):
    from application.commands.data_commands import collect_exchange_data

    try:
        import asyncio
        result = asyncio.run(collect_exchange_data(
            symbols=["BTC", "ETH", "SOL", "DOGE"],
        ))

        return {"success": True, "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=60)


@celery_app.task(name="tasks.collect_etf", bind=True, max_retries=3)
def collect_etf(self):
    from application.commands.data_commands import collect_etf_data

    try:
        import asyncio
        result = asyncio.run(collect_etf_data())

        return {"success": True, "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=300)


@celery_app.task(name="tasks.collect_news", bind=True, max_retries=3)
def collect_news(self):
    from application.commands.data_commands import collect_news_data

    try:
        import asyncio
        result = asyncio.run(collect_news_data())

        return {"success": True, "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=120)


@celery_app.task(name="tasks.collect_macro", bind=True, max_retries=3)
def collect_macro(self):
    from application.commands.data_commands import collect_macro_data

    try:
        import asyncio
        result = asyncio.run(collect_macro_data())

        return {"success": True, "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=300)


@celery_app.task(name="tasks.collect_social", bind=True, max_retries=2)
def collect_social(self):
    from application.commands.data_commands import collect_social_media_data

    try:
        import asyncio
        result = asyncio.run(collect_social_media_data())

        return {"success": True, "count": len(result)}
    except Exception as e:
        self.retry(exc=e, countdown=180)


@celery_app.task(name="tasks.collect_trader", bind=True, max_retries=2)
def collect_trader(self):
    from application.commands.data_commands import collect_trader_data

    try:
        import asyncio
        result = asyncio.run(collect_trader_data())

        return {"success": True, "count": len(result.get("statements", []))}
    except Exception as e:
        self.retry(exc=e, countdown=180)


@celery_app.task(name="tasks.analyze_news")
def analyze_news():
    pass


@celery_app.task(name="tasks.check_black_swan")
def check_black_swan():
    from application.commands.data_commands import check_black_swan as check_swan

    try:
        import asyncio
        black_swan = asyncio.run(check_swan())

        if black_swan:
            from infrastructure.alerting import AlertManager
            alert_manager = AlertManager()

            for news in black_swan:
                alert_manager.send_alert(
                    title=f"黑天鹅预警: {news.get('title', '')[:50]}",
                    message=news.get("content", ""),
                    severity="critical"
                )

        return {"success": True, "black_swan_count": len(black_swan)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task(name="tasks.publish_ws_data")
def publish_ws_data():
    from infrastructure.websocket import get_ws_server

    try:
        ws_server = get_ws_server()

        import asyncio
        asyncio.run(_publish_data(ws_server))

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _publish_data(ws_server):
    from application.commands.data_commands import publish_exchange_prices

    prices = await publish_exchange_prices(
        symbols=["BTC", "ETH", "SOL", "DOGE"],
        exchanges=["binance", "okx"],
    )

    for symbol, multi_prices in prices.items():
        if "binance" in multi_prices.prices:
            price = multi_prices.prices["binance"]
            await ws_server.publish_price(symbol, {
                "price": price.price,
                "change_24h": price.change_24h,
                "volume_24h": price.volume_24h
            })
