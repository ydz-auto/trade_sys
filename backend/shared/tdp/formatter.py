"""
TDP 消息格式化器
"""

import time
from typing import Dict, Any, Optional


class TDPFormatter:
    VERSION = "1.0"

    @staticmethod
    def format_market_data(
        symbol: str,
        price: float,
        volume: float,
        exchange: str,
        high: Optional[float] = None,
        low: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = int(time.time())

        return {
            "meta": {
                "version": TDPFormatter.VERSION,
                "type": "market",
                "timestamp": timestamp,
                "source": exchange,
                "status": "OK"
            },
            "market": {
                "crypto": {
                    symbol: {
                        "price": price,
                        "volume_24h": volume,
                        "high_24h": high,
                        "low_24h": low,
                        "bid": bid,
                        "ask": ask,
                        "timestamp": timestamp
                    }
                }
            }
        }

    @staticmethod
    def format_etf_flow(
        symbol: str,
        inflow: float,
        outflow: float,
        aum: Optional[float] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = int(time.time())

        return {
            "meta": {
                "version": TDPFormatter.VERSION,
                "type": "etf_flow",
                "timestamp": timestamp,
                "status": "OK"
            },
            "market": {
                "etf": {
                    symbol: {
                        "inflow": inflow,
                        "outflow": outflow,
                        "net_flow": inflow - outflow,
                        "aum": aum,
                        "timestamp": timestamp
                    }
                }
            }
        }

    @staticmethod
    def format_macro_data(
        gold: Optional[float] = None,
        oil: Optional[float] = None,
        dxy: Optional[float] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = int(time.time())

        data = {}
        if gold is not None:
            data["gold"] = {"price": gold, "timestamp": timestamp}
        if oil is not None:
            data["oil"] = {"price": oil, "timestamp": timestamp}
        if dxy is not None:
            data["dxy"] = {"price": dxy, "timestamp": timestamp}

        return {
            "meta": {
                "version": TDPFormatter.VERSION,
                "type": "macro",
                "timestamp": timestamp,
                "status": "OK"
            },
            "market": {
                "commodities": data
            }
        }

    @staticmethod
    def format_news(
        title: str,
        content: str,
        source: str,
        url: str,
        sentiment: Optional[float] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = int(time.time())

        return {
            "meta": {
                "version": TDPFormatter.VERSION,
                "type": "news",
                "timestamp": timestamp,
                "source": source,
                "status": "OK"
            },
            "events": [{
                "type": "news",
                "title": title,
                "content": content,
                "source": source,
                "url": url,
                "sentiment_score": sentiment,
                "timestamp": timestamp
            }]
        }

    @staticmethod
    def format_social(
        platform: str,
        author: str,
        content: str,
        sentiment: Optional[float] = None,
        engagement: Optional[Dict] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = int(time.time())

        return {
            "meta": {
                "version": TDPFormatter.VERSION,
                "type": "social",
                "timestamp": timestamp,
                "platform": platform,
                "status": "OK"
            },
            "events": [{
                "type": "social",
                "platform": platform,
                "author": author,
                "content": content,
                "sentiment_score": sentiment,
                "engagement": engagement or {},
                "timestamp": timestamp
            }]
        }

    @staticmethod
    def format_error(error_type: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        return {
            "meta": {
                "version": TDPFormatter.VERSION,
                "type": "error",
                "timestamp": int(time.time()),
                "status": "ERROR",
                "error_type": error_type,
                "message": message
            },
            "details": details or {}
        }
