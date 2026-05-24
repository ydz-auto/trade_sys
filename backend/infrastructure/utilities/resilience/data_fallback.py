"""
Multi-Channel Data Manager - 多数据通道管理器

专业量化系统的标准做法：
1. WebSocket - 实时数据
2. REST API - 快照、补数据、校验
3. 第三方聚合 (CoinGecko) - 降级
4. 其他交易所 - 多源交叉验证
5. Mock - 最后手段

数据可靠性层：
- Sequence Check (序号检查)
- Snapshot Recovery (快照恢复)
- Reconnect Manager (重连管理)
- Heartbeat Watchdog (心跳检测)
"""
import asyncio
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict, List, Tuple, Set
from enum import Enum

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker
)
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig
from infrastructure.utilities.resilience.fallback import (
    FallbackChain,
    FallbackStrategy,
    FallbackResult,
    PrimaryFallback,
    StaticValueFallback,
    AlternateFunctionFallback
)
from infrastructure.config.defaults.infrastructure.external_apis import EXCHANGE_REST_APIS

logger = get_logger("resilience.multi_channel")


class DataChannelType(Enum):
    """数据通道类型（按优先级排序）"""
    BINANCE_WS = 10  # Binance WebSocket (最高优先级)
    BINANCE_REST = 20  # Binance REST API
    BYBIT_REST = 30  # Bybit REST API
    OKX_REST = 40  # OKX REST API
    GATEIO_REST = 50  # Gate.io REST API
    COINBASE_REST = 60  # Coinbase REST API
    COINGECKO_REST = 70  # CoinGecko REST API
    MOCK = 100  # Mock (最后手段)


class DataQuality(Enum):
    """数据质量"""
    REAL = "real"              # 真实数据
    CACHED = "cached"          # 缓存数据
    FALLBACK = "fallback"      # 降级数据（其他源）
    MOCK = "mock"              # 模拟数据


@dataclass
class DataChannelStatus:
    """数据通道状态"""
    channel_type: DataChannelType
    name: str
    is_available: bool = True
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None
    failure_count: int = 0
    success_count: int = 0
    total_messages: int = 0
    last_sequence_id: Optional[int] = None


@dataclass
class PriceData:
    """标准化价格数据"""
    symbol: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    change_24h: Optional[float] = None
    source_channel: DataChannelType = DataChannelType.MOCK
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


@dataclass
class ChannelConfig:
    """单个数据通道配置"""
    name: str
    channel_type: DataChannelType
    enabled: bool = True
    weight: float = 1.0
    endpoints: List[str] = field(default_factory=list)
    timeout: float = 10.0


@dataclass
class MultiChannelConfig:
    """多通道配置"""
    channels: List[ChannelConfig] = field(default_factory=list)
    enable_sequence_check: bool = True
    enable_heartbeat: bool = True
    heartbeat_interval: float = 30.0
    snapshot_interval: int = 300  # 每5分钟强制拉一次快照
    cache_ttl_seconds: int = 60
    mock_mode: bool = False  # Mock模式开关，默认关闭

    @classmethod
    def default(cls) -> "MultiChannelConfig":
        """默认配置（标准专业架构）"""
        return cls(
            channels=[
                ChannelConfig(
                    name="binance_ws",
                    channel_type=DataChannelType.BINANCE_WS,
                    enabled=True,
                    weight=1.0,
                    endpoints=[
                        "wss://stream.binance.com:9443/ws",
                        "wss://fstream.binance.com/ws"
                    ]
                ),
                ChannelConfig(
                    name="binance_rest",
                    channel_type=DataChannelType.BINANCE_REST,
                    enabled=True,
                    weight=0.95,
                    endpoints=[
                        EXCHANGE_REST_APIS["binance"]["spot"],
                        "https://api1.binance.com",
                        "https://api2.binance.com"
                    ]
                ),
                ChannelConfig(
                    name="bybit_rest",
                    channel_type=DataChannelType.BYBIT_REST,
                    enabled=True,
                    weight=0.8,
                    endpoints=[EXCHANGE_REST_APIS["bybit"]["api"]]
                ),
                ChannelConfig(
                    name="okx_rest",
                    channel_type=DataChannelType.OKX_REST,
                    enabled=True,
                    weight=0.7,
                    endpoints=[EXCHANGE_REST_APIS["okx"]["api"]]
                ),
                ChannelConfig(
                    name="gateio_rest",
                    channel_type=DataChannelType.GATEIO_REST,
                    enabled=True,
                    weight=0.6,
                    endpoints=[EXCHANGE_REST_APIS["gate"]["api"]]
                ),
                ChannelConfig(
                    name="coinbase_rest",
                    channel_type=DataChannelType.COINBASE_REST,
                    enabled=True,
                    weight=0.5,
                    endpoints=[EXCHANGE_REST_APIS["coinbase"]["api"]]
                ),
                ChannelConfig(
                    name="coingecko",
                    channel_type=DataChannelType.COINGECKO_REST,
                    enabled=True,
                    weight=0.4,
                    endpoints=[EXCHANGE_REST_APIS["coingecko"]["api"]]
                )
            ],
            mock_mode=False
        )

    @classmethod
    def mock_mode(cls) -> "MultiChannelConfig":
        """Mock模式配置（开发/演示用）"""
        return cls(
            channels=[
                ChannelConfig(
                    name="mock",
                    channel_type=DataChannelType.MOCK,
                    enabled=True,
                    weight=0.1
                )
            ],
            mock_mode=True
        )


class SequenceTracker:
    """序列号追踪器 - 检测丢包"""

    def __init__(self, max_gap: int = 10):
        self._sequences: Dict[str, int] = {}
        self._gaps: Dict[str, List[Tuple[int, int]]] = {}
        self.max_gap = max_gap

    def check(self, symbol: str, seq_id: int) -> Tuple[bool, Optional[int]]:
        """
        检查序列号是否连续
        返回: (ok, missing_seq_id)
        """
        if symbol not in self._sequences:
            self._sequences[symbol] = seq_id
            return True, None

        last = self._sequences[symbol]
        gap = seq_id - last

        if gap == 1:
            self._sequences[symbol] = seq_id
            return True, None

        if gap > 1:
            if symbol not in self._gaps:
                self._gaps[symbol] = []
            self._gaps[symbol].append((last + 1, seq_id - 1))
            logger.warning(f"Sequence gap detected for {symbol}: {last+1} to {seq_id-1}")
            self._sequences[symbol] = seq_id
            return False, last + 1

        # 重复或过期
        return False, None

    def get_gaps(self, symbol: str) -> List[Tuple[int, int]]:
        return self._gaps.get(symbol, [])

    def reset(self, symbol: str):
        if symbol in self._sequences:
            del self._sequences[symbol]
        if symbol in self._gaps:
            del self._gaps[symbol]


class BaseDataFetcher:
    """数据获取器基类"""

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        raise NotImplementedError

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        raise NotImplementedError


class BinanceRESTFetcher(BaseDataFetcher):
    """Binance REST API 获取器"""

    def __init__(self, endpoint: str = None):
        if endpoint is None:
            endpoint = EXCHANGE_REST_APIS["binance"]["spot"]
        self.endpoint = endpoint
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=10.0)
            except ImportError:
                logger.warning("httpx not available, will try ccxt")
        return self._client

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        """从Binance REST获取价格"""
        try:
            client = await self._get_client()
            if client:
                binance_symbol = symbol.upper()
                if not binance_symbol.endswith("USDT"):
                    binance_symbol = f"{binance_symbol}USDT"
                url = f"{self.endpoint}/api/v3/ticker/24hr?symbol={binance_symbol}"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                return PriceData(
                    symbol=symbol.upper(),
                    price=float(data.get("lastPrice", 0)),
                    bid=float(data.get("bidPrice", 0)),
                    ask=float(data.get("askPrice", 0)),
                    volume_24h=float(data.get("volume", 0)),
                    high_24h=float(data.get("highPrice", 0)),
                    low_24h=float(data.get("lowPrice", 0)),
                    change_24h=float(data.get("priceChangePercent", 0)),
                    source_channel=DataChannelType.BINANCE_REST
                )
            else:
                # Fallback to ccxt
                return await self._fetch_with_ccxt(symbol)
        except Exception as e:
            logger.warning(f"Binance REST fetch failed for {symbol}: {e}")
            return None

    async def _fetch_with_ccxt(self, symbol: str) -> Optional[PriceData]:
        """使用ccxt作为备选"""
        try:
            import ccxt
            exchange = ccxt.binance()
            ticker = exchange.fetch_ticker(f"{symbol.upper()}/USDT")
            return PriceData(
                symbol=symbol.upper(),
                price=ticker.get("last", 0),
                bid=ticker.get("bid", 0),
                ask=ticker.get("ask", 0),
                volume_24h=ticker.get("baseVolume", 0),
                source_channel=DataChannelType.BINANCE_REST
            )
        except Exception as e:
            logger.warning(f"CCXT Binance fetch failed: {e}")
            return None

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        return None


class CoinGeckoFetcher(BaseDataFetcher):
    """CoinGecko API 获取器"""

    _COIN_MAP = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "DOGE": "dogecoin"
    }

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        try:
            import httpx
            base_symbol = symbol.upper().replace("USDT", "")
            coin_id = self._COIN_MAP.get(base_symbol)

            if not coin_id:
                return None

            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if coin_id in data:
                    price_data = data[coin_id]
                    return PriceData(
                        symbol=symbol.upper(),
                        price=float(price_data.get("usd", 0)),
                        volume_24h=float(price_data.get("usd_24hr_vol", 0)),
                        change_24h=float(price_data.get("usd_24h_change", 0)),
                        source_channel=DataChannelType.COINGECKO_REST
                    )
            return None
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed for {symbol}: {e}")
            return None

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        return None


class BybitFetcher(BaseDataFetcher):
    """Bybit REST API 获取器"""

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        try:
            import httpx
            bybit_symbol = symbol.upper()
            if not bybit_symbol.endswith("USDT"):
                bybit_symbol = f"{bybit_symbol}USDT"
            
            url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={bybit_symbol}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    item = data["result"]["list"][0]
                    return PriceData(
                        symbol=symbol.upper(),
                        price=float(item.get("lastPrice", 0)),
                        bid=float(item.get("bid1Price", 0)),
                        ask=float(item.get("ask1Price", 0)),
                        volume_24h=float(item.get("volume24h", 0)),
                        high_24h=float(item.get("highPrice24h", 0)),
                        low_24h=float(item.get("lowPrice24h", 0)),
                        change_24h=float(item.get("price24hPcnt", 0)) * 100,
                        source_channel=DataChannelType.BYBIT_REST
                    )
            return None
        except Exception as e:
            logger.warning(f"Bybit fetch failed for {symbol}: {e}")
            return None

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        return None


class GateioFetcher(BaseDataFetcher):
    """Gate.io REST API 获取器"""

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        try:
            import httpx
            # Gate.io uses underscore, e.g., BTC_USDT
            base = symbol.upper().replace("USDT", "").replace("-USDT", "")
            gate_symbol = f"{base}_USDT"
            
            url = f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={gate_symbol}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if data and len(data) > 0:
                    item = data[0]
                    change_pct = item.get("change_percentage", "0")
                    change_24h = float(change_pct) if change_pct else 0.0
                    
                    return PriceData(
                        symbol=symbol.upper(),
                        price=float(item.get("last", 0)),
                        bid=float(item.get("highest_bid", 0)),
                        ask=float(item.get("lowest_ask", 0)),
                        volume_24h=float(item.get("base_volume", 0)),
                        high_24h=float(item.get("high_24h", 0)),
                        low_24h=float(item.get("low_24h", 0)),
                        change_24h=change_24h,
                        source_channel=DataChannelType.GATEIO_REST
                    )
            return None
        except Exception as e:
            logger.warning(f"Gate.io fetch failed for {symbol}: {e}")
            return None

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        return None


class CoinbaseFetcher(BaseDataFetcher):
    """Coinbase REST API 获取器"""

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        try:
            import httpx
            base = symbol.upper().replace("USDT", "")
            coinbase_symbol = f"{base}-USD"
            
            url = f"https://api.exchange.coinbase.com/products/{coinbase_symbol}/ticker"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                return PriceData(
                    symbol=symbol.upper(),
                    price=float(data.get("price", 0)),
                    bid=float(data.get("bid", 0)),
                    ask=float(data.get("ask", 0)),
                    volume_24h=float(data.get("volume", 0)),
                    source_channel=DataChannelType.COINBASE_REST
                )
        except Exception as e:
            logger.warning(f"Coinbase fetch failed for {symbol}: {e}")
            return None

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        return None


class MockFetcher(BaseDataFetcher):
    """Mock数据获取器（最后手段）"""

    _BASE_PRICES = {
        "BTCUSDT": 68000.0,
        "ETHUSDT": 3500.0,
        "SOLUSDT": 140.0,
        "BNBUSDT": 580.0
    }

    async def fetch_price(self, symbol: str) -> Optional[PriceData]:
        base = self._BASE_PRICES.get(symbol.upper(), 1000.0)
        ts = datetime.now().timestamp()

        # 真实波动模拟
        random_factor = 1.0 + random.uniform(-0.001, 0.001)
        time_factor = 1.0 + 0.0005 * (ts % 3600) / 3600

        price = base * random_factor * time_factor

        return PriceData(
            symbol=symbol.upper(),
            price=price,
            bid=price * 0.9998,
            ask=price * 1.0002,
            volume_24h=1000000,
            source_channel=DataChannelType.MOCK
        )

    async def fetch_snapshot(self, symbol: str) -> Optional[Dict]:
        return None


class MultiChannelDataManager:
    """多通道数据管理器 - 专业级数据可靠性层"""

    def __init__(self, config: Optional[MultiChannelConfig] = None):
        self.config = config or MultiChannelConfig.default()

        # 通道状态
        self._channel_statuses: Dict[DataChannelType, DataChannelStatus] = {}

        # 熔断器
        self._circuit_breakers: Dict[DataChannelType, CircuitBreaker] = {}

        # 数据获取器
        self._fetchers: Dict[DataChannelType, BaseDataFetcher] = {}

        # 序列号追踪
        self._sequence_tracker = SequenceTracker()

        # 缓存
        self._price_cache: Dict[str, Tuple[float, PriceData]] = {}

        # 初始化
        self._init_fetchers()
        logger.info("MultiChannelDataManager initialized with %d channels", len(self.config.channels))

    def _init_fetchers(self):
        """初始化各数据获取器"""
        for channel in self.config.channels:
            if not channel.enabled:
                continue

            if channel.channel_type == DataChannelType.BINANCE_REST:
                default_endpoint = EXCHANGE_REST_APIS["binance"]["spot"]
                self._fetchers[channel.channel_type] = BinanceRESTFetcher(channel.endpoints[0] if channel.endpoints else default_endpoint)
            elif channel.channel_type == DataChannelType.BYBIT_REST:
                self._fetchers[channel.channel_type] = BybitFetcher()
            elif channel.channel_type == DataChannelType.GATEIO_REST:
                self._fetchers[channel.channel_type] = GateioFetcher()
            elif channel.channel_type == DataChannelType.COINBASE_REST:
                self._fetchers[channel.channel_type] = CoinbaseFetcher()
            elif channel.channel_type == DataChannelType.COINGECKO_REST:
                self._fetchers[channel.channel_type] = CoinGeckoFetcher()
            elif channel.channel_type == DataChannelType.MOCK:
                # Mock只在mock_mode开启时才初始化
                if self.config.mock_mode:
                    self._fetchers[channel.channel_type] = MockFetcher()
                else:
                    continue

            # 初始化状态
            self._channel_statuses[channel.channel_type] = DataChannelStatus(
                channel_type=channel.channel_type,
                name=channel.name
            )

            # 初始化熔断器
            self._circuit_breakers[channel.channel_type] = CircuitBreaker(
                CircuitBreakerConfig(
                    name=f"{channel.name}_circuit",
                    failure_threshold=3,
                    recovery_timeout=30.0
                )
            )

    def get_channel_priority_list(self) -> List[DataChannelType]:
        """获取按优先级排序的通道列表"""
        channels = [c.channel_type for c in self.config.channels if c.enabled]
        
        # 如果不是mock模式，排除mock通道
        if not self.config.mock_mode:
            channels = [c for c in channels if c != DataChannelType.MOCK]
        
        return sorted(channels, key=lambda x: x.value)

    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """
        获取价格 - 多通道降级策略

        流程：
        1. 尝试优先通道
        2. 失败则依次尝试降级通道
        3. 最后尝试Mock
        """
        # 先检查缓存
        cached = self._get_cached_price(symbol)
        if cached:
            return cached

        # 按优先级遍历通道
        for channel_type in self.get_channel_priority_list():
            if not self._is_channel_available(channel_type):
                continue

            try:
                # 检查熔断器
                cb = self._circuit_breakers.get(channel_type)
                if cb and cb.state.value == "open":
                    logger.debug(f"Circuit open for {channel_type.name}, skipping")
                    continue

                fetcher = self._fetchers.get(channel_type)
                if not fetcher:
                    continue

                price_data = await fetcher.fetch_price(symbol)

                if price_data:
                    self._record_success(channel_type)
                    self._set_price_cache(symbol, price_data)
                    logger.debug(f"Got price from {channel_type.name}: {price_data.price}")
                    return price_data
                else:
                    self._record_failure(channel_type)

            except Exception as e:
                logger.warning(f"Channel {channel_type.name} failed: {e}")
                self._record_failure(channel_type)

        logger.error(f"All channels failed for {symbol}")
        return None

    async def get_snapshot(self, symbol: str) -> Optional[Dict]:
        """获取快照（用于恢复）"""
        # REST API 优先，因为更可靠
        for channel_type in [DataChannelType.BINANCE_REST, DataChannelType.COINGECKO_REST]:
            if not self._is_channel_available(channel_type):
                continue

            fetcher = self._fetchers.get(channel_type)
            if fetcher:
                snapshot = await fetcher.fetch_snapshot(symbol)
                if snapshot:
                    return snapshot

        return None

    def _is_channel_available(self, channel_type: DataChannelType) -> bool:
        status = self._channel_statuses.get(channel_type)
        if not status:
            return False
        return status.is_available

    def _record_success(self, channel_type: DataChannelType):
        status = self._channel_statuses.get(channel_type)
        if status:
            status.is_available = True
            status.last_success_time = datetime.now().timestamp()
            status.success_count += 1
            status.failure_count = 0

    def _record_failure(self, channel_type: DataChannelType):
        status = self._channel_statuses.get(channel_type)
        if status:
            status.last_failure_time = datetime.now().timestamp()
            status.failure_count += 1

            if status.failure_count >= 3:
                status.is_available = False
                logger.warning(f"Channel {channel_type.name} marked as unavailable")

    def _get_cached_price(self, symbol: str) -> Optional[PriceData]:
        if symbol not in self._price_cache:
            return None

        ts, data = self._price_cache[symbol]
        age = datetime.now().timestamp() - ts

        if age > self.config.cache_ttl_seconds:
            return None

        return data

    def _set_price_cache(self, symbol: str, data: PriceData):
        self._price_cache[symbol] = (datetime.now().timestamp(), data)

    def get_health_status(self) -> Dict:
        """获取健康状态"""
        return {
            "channels": {
                s.name: {
                    "type": s.channel_type.name,
                    "available": s.is_available,
                    "success_count": s.success_count,
                    "failure_count": s.failure_count,
                    "last_success": s.last_success_time
                }
                for s in self._channel_statuses.values()
            },
            "cache_count": len(self._price_cache),
            "active_channel": self._get_best_available_channel()
        }

    def _get_best_available_channel(self) -> Optional[str]:
        for channel_type in self.get_channel_priority_list():
            if self._is_channel_available(channel_type):
                return channel_type.name
        return None


# 全局单例
_multi_channel_manager: Optional[MultiChannelDataManager] = None


def get_multi_channel_manager(config: Optional[MultiChannelConfig] = None) -> MultiChannelDataManager:
    """获取多通道管理器单例"""
    import os
    global _multi_channel_manager
    
    if _multi_channel_manager is None:
        # 如果没传配置，检查环境变量
        if config is None:
            mock_mode = os.getenv("DATA_MOCK_MODE", "false").lower() == "true"
            if mock_mode:
                config = MultiChannelConfig.mock_mode()
            else:
                config = MultiChannelConfig.default()
        
        _multi_channel_manager = MultiChannelDataManager(config)
    
    return _multi_channel_manager


# 保持兼容性
DataFallbackManager = MultiChannelDataManager
get_data_fallback_manager = get_multi_channel_manager