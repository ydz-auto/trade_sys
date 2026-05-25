"""
Binance Open Interest REST Collector

Binance Futures 的 Open Interest 不走标准 WS stream，
需要通过 REST API 定时拉取：
  /fapi/v1/openInterest        — 当前 OI
  /futures/data/openInterestHist — 历史 OI

本采集器定时轮询并发布 StandardEvent，
由 IngestionRuntime 统一调度。
"""
import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from engines.adapters.contracts import StandardEvent, Source, EventType
from infrastructure.logging import get_logger
from infrastructure.config.defaults.infrastructure.external_apis import EXCHANGE_REST_APIS

logger = get_logger("collectors.binance_oi")


@dataclass
class OICollectorConfig:
    symbols: List[str] = None
    poll_interval_seconds: int = 60
    testnet: bool = False
    timeout: float = 10.0

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


class BinanceOICollector:
    """
    Binance Open Interest REST 轮询采集器

    用法：
        collector = BinanceOICollector(config)
        collector.on_event = my_callback
        await collector.start()   # 启动后台轮询
        ...
        await collector.stop()
    """

    def __init__(self, config: OICollectorConfig = None):
        self.config = config or OICollectorConfig()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._session = None
        self.on_event: Optional[Callable] = None

        if self.config.testnet:
            self._base_url = EXCHANGE_REST_APIS["binance"]["testnet_futures"]
        else:
            self._base_url = EXCHANGE_REST_APIS["binance"]["futures"]

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"OICollector started, interval={self.config.poll_interval_seconds}s")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("OICollector stopped")

    async def _ensure_session(self):
        if self._session is None:
            try:
                import aiohttp
                self._session = aiohttp.ClientSession()
            except ImportError:
                import httpx
                self._session = httpx.AsyncClient(timeout=self.config.timeout)

    async def _poll_loop(self):
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error(f"OICollector poll error: {e}")
            await asyncio.sleep(self.config.poll_interval_seconds)

    async def _poll_once(self):
        await self._ensure_session()
        for symbol in self.config.symbols:
            try:
                oi_data = await self._fetch_open_interest(symbol)
                if oi_data and self.on_event:
                    event = self._make_event(symbol, oi_data)
                    if asyncio.iscoroutinefunction(self.on_event):
                        await self.on_event(event)
                    else:
                        self.on_event(event)
            except Exception as e:
                logger.warning(f"OICollector fetch failed for {symbol}: {e}")

    async def _fetch_open_interest(self, symbol: str) -> Optional[Dict]:
        url = f"{self._base_url}/fapi/v1/openInterest"
        params = {"symbol": symbol.upper()}

        try:
            import aiohttp
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except (AttributeError, TypeError):
            pass

        try:
            import httpx
            resp = await self._session.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except (AttributeError, TypeError):
            pass

        return None

    def _make_event(self, symbol: str, data: Dict) -> StandardEvent:
        oi = float(data.get("openInterest", 0))
        event_time = int(data.get("time", time.time() * 1000))

        return StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.OPEN_INTEREST.value,
            timestamp=event_time,
            title=f"Open Interest: {symbol}",
            content=f"OI: {oi}",
            importance=0.35,
            symbols=[symbol],
            tags=["open_interest", "oi"],
            metadata={
                "symbol": symbol.lower(),
                "open_interest": oi,
                "timestamp": event_time,
            },
        )

    async def fetch_open_interest_hist(self, symbol: str, period: str = "5m", limit: int = 30) -> List[Dict]:
        """拉取历史 OI 数据"""
        await self._ensure_session()
        url = f"{self._base_url}/futures/data/openInterestHist"
        params = {"symbol": symbol.upper(), "period": period, "limit": limit}

        try:
            import aiohttp
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except (AttributeError, TypeError):
            pass

        try:
            import httpx
            resp = await self._session.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except (AttributeError, TypeError):
            pass

        return []
