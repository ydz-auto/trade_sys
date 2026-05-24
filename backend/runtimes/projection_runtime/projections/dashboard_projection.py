import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .base import BaseProjection
from ..state_keys import ProjectionKeys, ProjectionChannels
from infrastructure.messaging.topics import Topics
from infrastructure.utilities.resilience.data_fallback import get_multi_channel_manager


class DashboardProjection(BaseProjection):
    def __init__(self):
        super().__init__("dashboard")

        self._prices: Dict[str, Dict[str, Any]] = {}
        self._factors: Dict[str, Dict[str, Any]] = {}
        self._regime: Dict[str, Dict[str, Any]] = {}
        self._signals: Dict[str, Dict[str, Any]] = {}
        self._news: List[Dict[str, Any]] = []
        self._composite_score: float = 0.5
        self._multi_channel = None
        self._snapshot_task: Optional[asyncio.Task] = None

    @property
    def topics(self) -> List[str]:
        return [
            Topics.RAW_DATA,
            Topics.SIGNALS,
            Topics.EVENTS,
            Topics.FACTORS,
        ]

    async def initialize(self) -> None:
        await super().initialize()

        state = await self.get_redis(ProjectionKeys.dashboard_state())
        if state:
            self._prices = state.get("prices", {})
            self._factors = state.get("factors", {})
            self._regime = state.get("regime", {})
            self._signals = state.get("signals", {})
            self._composite_score = state.get("compositeScore", 0.5)
            self.logger.info("Dashboard state loaded from Redis")

        try:
            self._multi_channel = get_multi_channel_manager()
            self.logger.info("Multi-channel manager initialized")

            self._snapshot_task = asyncio.create_task(self._periodic_price_snapshot())
            self.logger.info("Price snapshot task started")
        except Exception as e:
            self.logger.warning(f"Multi-channel manager init failed: {e}")
            self._multi_channel = None

    async def process_event(self, event: Dict[str, Any]) -> None:
        self.record_event()

        event_type = event.get("event_type", "")

        try:
            if event_type == "raw_data":
                await self._process_raw_data(event)
            elif event_type == "news":
                await self._process_news_event(event)
            elif event_type == "signal":
                await self._process_signal(event)
            elif event_type == "event":
                await self._process_analysis_event(event)
            elif event_type == "market":
                await self._process_market_event(event)
            elif event_type == "price_update":
                await self._process_price_update(event)
            elif event_type == "factors":
                await self._process_factors_event(event)

            await self._update_dashboard_state()

        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self._stats.errors += 1

    async def _process_factors_event(self, event: Dict[str, Any]) -> None:
        factors_list = event.get("factors", [])
        symbol = event.get("symbol", "BTC")

        if not factors_list:
            return

        for factor in factors_list:
            factor_type = factor.get("type", "")
            if factor_type:
                self._factors[factor_type] = {
                    "type": factor_type,
                    "name": factor.get("name", factor_type),
                    "nameEn": factor.get("nameEn", factor_type),
                    "weight": factor.get("weight", 0.2),
                    "value": factor.get("value", 0.5),
                    "confidence": factor.get("confidence", 50),
                    "color": factor.get("color", "blue"),
                    "symbol": symbol,
                    "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
                }

        self.logger.info(f"Updated {len(factors_list)} factors for {symbol}")

    async def _process_raw_data(self, event: Dict[str, Any]) -> None:
        data_type = event.get("data_type", "")
        data = event.get("data", {})
        symbol = event.get("symbol", "BTC")

        if data_type == "news":
            news_item = {
                "id": event.get("event_id", ""),
                "title": data.get("title", ""),
                "content": data.get("content", "")[:200] if data.get("content") else "",
                "source": data.get("source", "unknown"),
                "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
                "sentiment": data.get("sentiment", "neutral"),
                "symbols": data.get("affected_symbols", [symbol]),
            }
            self._news.insert(0, news_item)
            self._news = self._news[:50]

    async def _process_news_event(self, event: Dict[str, Any]) -> None:
        data = event.get("data", {})

        news_item = {
            "id": data.get("id", event.get("event_id", "")),
            "title": data.get("title", ""),
            "content": data.get("content", "")[:200] if data.get("content") else "",
            "source": data.get("source", "unknown"),
            "url": data.get("url", ""),
            "published": data.get("published", 0),
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
            "sentiment": data.get("sentiment", "neutral"),
            "sentiment_score": data.get("sentiment_score", 0.5),
            "symbols": data.get("affected_symbols", []),
        }

        self._news.insert(0, news_item)
        self._news = self._news[:50]

        self.logger.info(f"Processed news: {news_item['title'][:50]}")

    async def _process_signal(self, event: Dict[str, Any]) -> None:
        symbol = event.get("symbol", "BTC")

        self._signals[symbol] = {
            "signal_name": event.get("signal_name", ""),
            "direction": event.get("direction", "neutral"),
            "confidence": event.get("confidence", 0.5),
            "strength": event.get("strength", 0.5),
            "event_count": event.get("event_count", 0),
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
        }

        self._update_composite_score()

    async def _process_analysis_event(self, event: Dict[str, Any]) -> None:
        symbol = event.get("symbol", "BTC")
        event_category = event.get("event_category", "")
        direction = event.get("direction", "neutral")
        strength = event.get("strength", 0.5)

        if symbol not in self._regime:
            self._regime[symbol] = {
                "state": "neutral",
                "confidence": 0.5,
                "trendStrength": 0.5,
                "last_update": datetime.utcnow().isoformat(),
            }

        regime = self._regime[symbol]

        if direction == "bullish":
            regime["trendStrength"] = min(1.0, regime.get("trendStrength", 0.5) + strength * 0.1)
            if regime["trendStrength"] > 0.6:
                regime["state"] = "trending_up"
        elif direction == "bearish":
            regime["trendStrength"] = max(0.0, regime.get("trendStrength", 0.5) - strength * 0.1)
            if regime["trendStrength"] < 0.4:
                regime["state"] = "trending_down"

        regime["confidence"] = min(1.0, regime.get("confidence", 0.5) + 0.05)
        regime["last_update"] = datetime.utcnow().isoformat()

    async def _process_market_event(self, event: Dict[str, Any]) -> None:
        symbol = event.get("symbol", "BTC")

        price_data = {
            "symbol": symbol,
            "price": event.get("close") or event.get("price", 0),
            "change24h": 0,
            "volume_24h": event.get("volume", 0),
            "exchange": event.get("exchange", "binance"),
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
        }

        if symbol in self._prices:
            old_price = self._prices[symbol].get("price", 0)
            if old_price > 0:
                price_data["change24h"] = (price_data["price"] - old_price) / old_price * 100

        self._prices[symbol] = price_data

    async def _process_price_update(self, event: Dict[str, Any]) -> None:
        symbol = event.get("symbol", "BTC")
        if "/" not in symbol:
            symbol = f"{symbol}/USDT"

        price = event.get("price", 0)

        price_data = {
            "symbol": symbol,
            "price": price,
            "change24h": 0,
            "volume_24h": 0,
            "exchange": event.get("source", "binance"),
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
        }

        if symbol in self._prices:
            old_price = self._prices[symbol].get("price", 0)
            if old_price > 0:
                price_data["change24h"] = (price - old_price) / old_price * 100
                price_data["volume_24h"] = self._prices[symbol].get("volume_24h", 0)

        if self._multi_channel:
            try:
                base_symbol = symbol.replace("/USDT", "USDT")
                full_price = await self._multi_channel.get_price(base_symbol)

                if full_price:
                    price_data["change24h"] = full_price.change_24h or 0
                    price_data["volume_24h"] = full_price.volume_24h or 0
                    if full_price.price:
                        price_data["price"] = full_price.price
                    self.logger.debug(f"Got full price data for {symbol}: change={price_data['change24h']:.2f}%, vol={price_data['volume_24h']:.0f}")
            except Exception as e:
                self.logger.debug(f"Could not get full price data: {e}")

        self._prices[symbol] = price_data

        await self.push_websocket(ProjectionChannels.prices(), {
            "type": "price_update",
            "symbol": symbol,
            "data": price_data,
        })

        self.logger.debug(f"Price updated: {symbol} = {price}")

    async def _periodic_price_snapshot(self) -> None:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]

        while self._running:
            try:
                if self._multi_channel:
                    snapshot_prices = {}

                    for symbol in symbols:
                        try:
                            price_data = await self._multi_channel.get_price(symbol)

                            if price_data:
                                base = symbol.replace("USDT", "")
                                symbol_key = f"{base}/USDT"
                                snapshot_prices[symbol_key] = {
                                    "symbol": symbol_key,
                                    "price": price_data.price,
                                    "change24h": price_data.change_24h or 0,
                                    "volume_24h": price_data.volume_24h or 0,
                                    "exchange": "multi_channel",
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                                self._prices[symbol_key] = snapshot_prices[symbol_key]
                                self.logger.debug(f"Price snapshot: {symbol} = {price_data.price}, change={price_data.change_24h:.2f}%")
                        except Exception as e:
                            self.logger.warning(f"Failed to get price snapshot for {symbol}: {e}")

                    if snapshot_prices:
                        await self.push_websocket(ProjectionChannels.prices(), {
                            "type": "prices_snapshot",
                            "data": snapshot_prices,
                        })

                    await self._update_dashboard_state()

                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in price snapshot task: {e}")
                await asyncio.sleep(10)

    def _update_composite_score(self) -> None:
        if not self._signals:
            self._composite_score = 0.5
            return

        total_confidence = sum(s.get("confidence", 0.5) for s in self._signals.values())
        total_signals = len(self._signals)

        bullish_weight = sum(
            s.get("confidence", 0.5) for s in self._signals.values()
            if s.get("direction") == "bullish"
        )
        bearish_weight = sum(
            s.get("confidence", 0.5) for s in self._signals.values()
            if s.get("direction") == "bearish"
        )

        if total_signals > 0:
            net = bullish_weight - bearish_weight
            self._composite_score = 0.5 + (net / (total_signals * 2))
            self._composite_score = max(0, min(1, self._composite_score))

    async def _update_dashboard_state(self) -> None:
        state = {
            "prices": self._prices,
            "factors": self._factors,
            "regime": self._regime,
            "signals": self._signals,
            "news": self._news[:20],
            "compositeScore": self._composite_score,
            "last_update": datetime.utcnow().isoformat(),
        }

        await self.update_redis(ProjectionKeys.dashboard_state(), state)

        await self.push_websocket(ProjectionChannels.dashboard(), {
            "type": "state_update",
            "data": state,
        })

    def get_state(self) -> Dict[str, Any]:
        return {
            "prices": self._prices,
            "factors": self._factors,
            "regime": self._regime,
            "signals": self._signals,
            "news": self._news[:20],
            "compositeScore": self._composite_score,
        }

    async def shutdown(self) -> None:
        self.logger.info("Shutting down Dashboard projection...")

        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
            self._snapshot_task = None

        await super().shutdown()
        self.logger.info("Dashboard projection stopped")
