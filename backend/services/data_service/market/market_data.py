"""
Market Data Layer - 市场数据层

功能：
- 价格数据
- 订单簿数据
- ETF 数据
- 链上数据
- 宏观数据

市场数据不需要经过 Skill Adapter，直接使用 StandardEvent 格式。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio

from standard_event import StandardEvent, EventType, Source
from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)

logger = get_logger("market_data")


class DataSource(Enum):
    """数据源"""
    BINANCE = "binance"
    OKX = "okx"
    COINGECKO = "coingecko"
    YAHOO = "yahoo"
    GLASSNODE = "glassnode"
    ETHEREUM = "ethereum"


@dataclass
class PriceData:
    """价格数据"""
    symbol: str
    price: float
    change_24h: float
    change_percent_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float
    timestamp: int


@dataclass
class OrderBookEntry:
    """订单簿条目"""
    price: float
    quantity: float


@dataclass
class OrderBook:
    """订单簿"""
    symbol: str
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    timestamp: int


@dataclass
class ETFFlow:
    """ETF 资金流"""
    symbol: str          # IBIT, FBTC 等
    inflows: float        # 流入（美元）
    outflows: float       # 流出（美元）
    net_flow: float       # 净流入
    total_aum: float      # 管理规模
    timestamp: int


class MarketDataCollector:
    """市场数据采集器
    
    采集：价格、订单簿、ETF、链上等数据
    """
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="market_data_circuit",
            failure_threshold=3,
            recovery_timeout=60.0
        ))
        
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=0.5
        ))
        
        logger.info("MarketDataCollector initialized")
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """获取价格"""
        try:
            # TODO: 接入真实 API
            return self._generate_mock_price(symbol)
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """获取订单簿"""
        try:
            # TODO: 接入真实 API
            return self._generate_mock_order_book(symbol)
        except Exception as e:
            logger.error(f"Failed to get order book for {symbol}: {e}")
            return None
    
    async def get_etf_flows(self) -> List[ETFFlow]:
        """获取 ETF 资金流"""
        try:
            # TODO: 接入真实 API
            return self._generate_mock_etf_flows()
        except Exception as e:
            logger.error(f"Failed to get ETF flows: {e}")
            return []
    
    def to_standard_event(self, data: Any) -> StandardEvent:
        """将市场数据转换为标准事件"""
        if isinstance(data, PriceData):
            return StandardEvent(
                source=Source.BINANCE.value,
                event_type=EventType.PRICE_UPDATE.value,
                title=f"{data.symbol} Price: ${data.price:,.2f}",
                content=f"24h Change: {data.change_percent_24h:+.2f}%",
                symbols=[data.symbol],
                importance=0.6,
                sentiment="bullish" if data.change_percent_24h > 0 else "bearish",
                metadata={
                    "price": data.price,
                    "change_24h": data.change_24h,
                    "change_percent_24h": data.change_percent_24h,
                    "volume_24h": data.volume_24h
                }
            )
        
        elif isinstance(data, ETFFlow):
            sentiment = "bullish" if data.net_flow > 0 else "bearish"
            importance = 0.7 if abs(data.net_flow) > 100_000_000 else 0.5
            
            return StandardEvent(
                source="etf",
                event_type=EventType.ETF_FLOW.value,
                title=f"{data.symbol} ETF: ${data.net_flow:,.0f} flow",
                content=f"Inflows: ${data.inflows:,.0f}, Outflows: ${data.outflows:,.0f}",
                sentiment=sentiment,
                importance=importance,
                symbols=[data.symbol],
                tags=["etf", "flow"],
                metadata={
                    "inflows": data.inflows,
                    "outflows": data.outflows,
                    "net_flow": data.net_flow,
                    "total_aum": data.total_aum
                }
            )
        
        else:
            return StandardEvent(
                source="market_data",
                event_type=EventType.UNKNOWN.value,
                title="Market Data Update"
            )
    
    def _generate_mock_price(self, symbol: str) -> PriceData:
        """生成模拟价格数据"""
        base_prices = {
            "BTC": 105000,
            "ETH": 3500,
            "SOL": 180
        }
        
        import random
        base = base_prices.get(symbol, 100)
        price = base * (1 + random.uniform(-0.05, 0.05))
        
        return PriceData(
            symbol=symbol,
            price=price,
            change_24h=price * random.uniform(-0.05, 0.05),
            change_percent_24h=random.uniform(-5, 5),
            volume_24h=random.uniform(1_000_000_000, 10_000_000_000),
            high_24h=price * 1.02,
            low_24h=price * 0.98,
            timestamp=int(datetime.now().timestamp())
        )
    
    def _generate_mock_order_book(self, symbol: str) -> OrderBook:
        """生成模拟订单簿"""
        import random
        price = self._generate_mock_price(symbol).price
        
        bids = [
            OrderBookEntry(price=price * (1 - 0.001 * i), quantity=random.uniform(0.1, 2))
            for i in range(10)
        ]
        
        asks = [
            OrderBookEntry(price=price * (1 + 0.001 * i), quantity=random.uniform(0.1, 2))
            for i in range(1, 11)
        ]
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=int(datetime.now().timestamp())
        )
    
    def _generate_mock_etf_flows(self) -> List[ETFFlow]:
        """生成模拟 ETF 数据"""
        import random
        now = int(datetime.now().timestamp())
        
        return [
            ETFFlow(
                symbol="IBIT",
                inflows=random.uniform(100_000_000, 500_000_000),
                outflows=random.uniform(0, 50_000_000),
                net_flow=0,
                total_aum=random.uniform(30_000_000_000, 50_000_000_000),
                timestamp=now
            ),
            ETFFlow(
                symbol="FBTC",
                inflows=random.uniform(50_000_000, 200_000_000),
                outflows=random.uniform(0, 30_000_000),
                net_flow=0,
                total_aum=random.uniform(10_000_000_000, 20_000_000_000),
                timestamp=now
            )
        ]


# 全局实例
_market_collector: Optional[MarketDataCollector] = None

def get_market_collector() -> MarketDataCollector:
    """获取市场数据采集器"""
    global _market_collector
    if _market_collector is None:
        _market_collector = MarketDataCollector()
    return _market_collector
