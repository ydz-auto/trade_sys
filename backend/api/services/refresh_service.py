"""
Refresh Service - 数据刷新服务

提供数据刷新功能，触发各数据源重新采集数据
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from domain.logging import get_logger
from application.queries.infrastructure_queries import get_redis_client_sync

logger = get_logger("api.refresh_service")


async def refresh_prices_data(symbol: Optional[str] = None) -> Dict[str, Any]:
    try:
        redis = get_redis_client_sync()

        refresh_event = {
            "type": "refresh_prices",
            "symbol": symbol or "all",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "api"
        }

        await redis.publish("refresh:prices", json.dumps(refresh_event))

        await redis.set(
            "refresh:prices:last_time",
            datetime.utcnow().isoformat()
        )

        logger.info(f"Published price refresh event: {symbol or 'all'}")

        return {
            "success": True,
            "count": 1,
            "symbol": symbol or "all"
        }

    except Exception as e:
        logger.error(f"Failed to refresh prices: {e}")
        raise


async def refresh_signals_data(symbol: Optional[str] = None) -> Dict[str, Any]:
    try:
        redis = get_redis_client_sync()

        refresh_event = {
            "type": "refresh_signals",
            "symbol": symbol or "all",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "api"
        }

        await redis.publish("refresh:signals", json.dumps(refresh_event))

        await redis.set(
            "refresh:signals:last_time",
            datetime.utcnow().isoformat()
        )

        logger.info(f"Published signal refresh event: {symbol or 'all'}")

        return {
            "success": True,
            "symbol": symbol or "all"
        }

    except Exception as e:
        logger.error(f"Failed to refresh signals: {e}")
        raise


async def refresh_factors_data() -> Dict[str, Any]:
    try:
        redis = get_redis_client_sync()

        refresh_event = {
            "type": "refresh_factors",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "api"
        }

        await redis.publish("refresh:factors", json.dumps(refresh_event))

        await redis.set(
            "refresh:factors:last_time",
            datetime.utcnow().isoformat()
        )

        factors_count = 5

        logger.info("Published factor refresh event")

        return {
            "success": True,
            "count": factors_count
        }

    except Exception as e:
        logger.error(f"Failed to refresh factors: {e}")
        raise


async def refresh_news_data() -> Dict[str, Any]:
    try:
        redis = get_redis_client_sync()

        refresh_event = {
            "type": "refresh_news",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "api"
        }

        await redis.publish("refresh:news", json.dumps(refresh_event))

        await redis.set(
            "refresh:news:last_time",
            datetime.utcnow().isoformat()
        )

        logger.info("Published news refresh event")

        return {
            "success": True,
            "count": 0
        }

    except Exception as e:
        logger.error(f"Failed to refresh news: {e}")
        raise


async def refresh_correlation_data(symbol: str, timeframe: str) -> Dict[str, Any]:
    try:
        from application.queries.service_queries import get_correlation_service

        worker = await get_correlation_service()
        result = await worker.run_analysis(symbol, timeframe)

        if "error" in result:
            raise Exception(result["error"])

        logger.info(f"Correlation analysis completed for {symbol} {timeframe}")

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "positive_signals": len(result.get("positive_signals", [])),
            "negative_signals": len(result.get("negative_signals", []))
        }

    except Exception as e:
        logger.error(f"Failed to refresh correlation: {e}")

        try:
            redis = get_redis_client_sync()
            refresh_event = {
                "type": "refresh_correlation",
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "api"
            }
            await redis.publish("refresh:correlation", json.dumps(refresh_event))
            return {"success": True, "symbol": symbol, "timeframe": timeframe}
        except Exception:
            raise


async def refresh_all_data() -> List[Dict[str, Any]]:
    results = []

    tasks = [
        ("prices", refresh_prices_data(None)),
        ("signals", refresh_signals_data(None)),
        ("factors", refresh_factors_data()),
        ("news", refresh_news_data()),
    ]

    for data_type, task in tasks:
        try:
            result = await task
            results.append({
                "success": True,
                "data_type": data_type,
                "message": f"{data_type} 刷新成功",
                **result
            })
        except Exception as e:
            results.append({
                "success": False,
                "data_type": data_type,
                "message": f"{data_type} 刷新失败: {str(e)}"
            })

    return results


async def get_refresh_status() -> Dict[str, Any]:
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "data_sources": {}
    }

    try:
        redis = get_redis_client_sync()

        data_types = ["prices", "signals", "factors", "news", "correlation"]

        for data_type in data_types:
            last_time = await redis.get(f"refresh:{data_type}:last_time")
            status["data_sources"][data_type] = {
                "last_refresh": last_time if last_time else "never",
                "status": "available" if last_time else "unavailable"
            }

    except Exception as e:
        logger.error(f"Failed to get refresh status: {e}")
        status["error"] = str(e)

    return status
