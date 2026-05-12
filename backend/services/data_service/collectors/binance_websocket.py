"""
Binance WebSocket Adapter - 核心市场数据源

这是系统最核心的数据源，提供：
- 实时成交 (aggTrade)
- 订单簿 (depth)
- 清算是 (liquidation)
- 标记价格 (markPrice)
- 资金费率 (fundingRate)
- 持仓量 (openInterest)

免费、实时、稳定
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum
import websockets
from websockets.client import connect

from shared.contracts import StandardEvent, Source, EventType
from infrastructure.logging import get_logger

logger = get_logger("binance_ws.adapter")


class StreamType(Enum):
    """流类型"""
    AGG_TRADE = "aggTrade"        # 聚合成交
    BOOK_TICKER = "bookTicker"    # 最优买卖价
    DEPTH = "depth"              # 订单簿
    LIQUIDATION = "forceOrder"   # 强平
    MARK_PRICE = "markPrice"      # 标记价格
    FUNDING_RATE = "fundingRate"  # 资金费率
    KLINE = "kline"              # K线
    OPEN_INTEREST = "openInterest"  # 持仓量


@dataclass
class BinanceConfig:
    """Binance 配置"""
    # 基础配置
    testnet: bool = False
    stream_types: List[StreamType] = None
    
    # 交易对
    symbols: List[str] = None  # 如 ["btcusdt", "ethusdt"]
    
    # 限流
    max_speed: bool = False  # True = 启用最大速度流
    
    def __post_init__(self):
        if self.stream_types is None:
            self.stream_types = [
                StreamType.AGG_TRADE,
                StreamType.LIQUIDATION,
                StreamType.MARK_PRICE
            ]
        if self.symbols is None:
            self.symbols = ["btcusdt", "ethusdt", "bnbusdt", "solusdt"]


class BinanceWebSocketAdapter:
    """Binance WebSocket 适配器
    
    使用官方 Binance WebSocket Streams API
    文档: https://developers.binance.com/docs/simple-earn/history/Get-Flexible-Rewards-History
    """
    
    BASE_URL = "wss://stream.binance.com:9443/ws"
    TESTNET_URL = "wss://testnet.binance.vision/ws"
    
    def __init__(self, config: BinanceConfig = None):
        self.config = config or BinanceConfig()
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        
        # 事件回调
        self.on_trade: Optional[Callable] = None
        self.on_liquidation: Optional[Callable] = None
        self.on_price_update: Optional[Callable] = None
        self.on_event: Optional[Callable] = None
        
        # 统计
        self.stats = {
            "total_messages": 0,
            "trades": 0,
            "liquidations": 0,
            "price_updates": 0,
            "errors": 0
        }
        
        # 最近事件（用于去重）
        self.recent_events: Dict[str, int] = {}  # event_id -> timestamp
        
    def _build_stream_url(self) -> str:
        """构建流 URL"""
        streams = []
        
        for symbol in self.config.symbols:
            for stream_type in self.config.stream_types:
                if stream_type == StreamType.LIQUIDATION:
                    # 强平使用不同的端点
                    streams.append(f"{symbol}@forceOrder")
                elif stream_type == StreamType.MARK_PRICE:
                    streams.append(f"{symbol}@markPrice@1s")
                elif stream_type == StreamType.AGG_TRADE:
                    streams.append(f"{symbol}@aggTrade")
                elif stream_type == StreamType.BOOK_TICKER:
                    streams.append(f"{symbol}@bookTicker")
        
        return f"{self.BASE_URL}/{'/'.join(streams)}"
    
    async def connect(self):
        """连接 WebSocket"""
        if self.is_connected:
            return
        
        url = self._build_stream_url()
        logger.info(f"Connecting to Binance WebSocket: {url[:100]}...")
        
        try:
            self.websocket = await connect(
                url,
                ping_interval=20,
                ping_timeout=10
            )
            self.is_connected = True
            logger.info("Binance WebSocket connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """断开连接"""
        self.is_running = False
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.is_connected = False
        logger.info("Binance WebSocket disconnected")
    
    async def listen(self):
        """监听消息"""
        if not self.is_connected:
            await self.connect()
        
        self.is_running = True
        logger.info("Binance WebSocket listening...")
        
        try:
            async for message in self.websocket:
                if not self.is_running:
                    break
                
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {message[:100]}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.stats["errors"] += 1
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Binance WebSocket connection closed")
            self.is_connected = False
            
            # 自动重连
            if self.is_running:
                await self._reconnect()
    
    async def _reconnect(self, delay: int = 5):
        """自动重连"""
        logger.info(f"Reconnecting in {delay}s...")
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
            await self.listen()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            await self._reconnect(delay=min(delay * 2, 60))
    
    async def _process_message(self, data: Dict):
        """处理消息"""
        self.stats["total_messages"] += 1
        
        # 根据流类型处理
        event_type = data.get("e", "")
        
        if event_type == "aggTrade":
            await self._handle_trade(data)
        elif event_type == "forceOrder":
            await self._handle_liquidation(data)
        elif event_type == "markPriceUpdate":
            await self._handle_mark_price(data)
        elif "bookTicker" in data:
            await self._handle_book_ticker(data)
    
    async def _handle_trade(self, data: Dict):
        """处理成交"""
        self.stats["trades"] += 1
        
        symbol = data.get("s", "").lower()
        price = float(data.get("p", 0))
        quantity = float(data.get("q", 0))
        trade_time = data.get("T", 0)
        is_buyer_maker = data.get("m", True)
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.TRADE.value,
            timestamp=trade_time,
            title=f"Trade: {symbol.upper()} {quantity} @ {price}",
            content=f" Binance {symbol.upper()}成交: {quantity} @ {price}, Maker={is_buyer_maker}",
            importance=0.6 if quantity > 1 else 0.3,
            symbols=[symbol.upper()],
            metadata={
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "value_usd": price * quantity,
                "is_buyer_maker": is_buyer_maker,
                "trade_id": data.get("a", "")
            }
        )
        
        # 设置情绪
        if is_buyer_maker:
            event.sentiment = "bearish"  # 卖方主动，看空
        else:
            event.sentiment = "bullish"  # 买方主动，看多
        
        # 回调
        if self.on_trade:
            await self.on_trade(event)
        if self.on_event:
            await self.on_event(event)
    
    async def _handle_liquidation(self, data: Dict):
        """处理强平"""
        self.stats["liquidations"] += 1
        
        # 强平数据在 o 字段中
        liquidation = data.get("o", {})
        
        symbol = liquidation.get("s", "").lower()
        side = liquidation.get("S", "")  # BUY or SELL
        price = float(liquidation.get("p", 0))
        quantity = float(liquidation.get("q", 0))
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.TECHNICAL.value,  # 用 TECHNICAL 表示技术性事件
            timestamp=data.get("E", 0),
            title=f"Liquidation: {symbol.upper()} {side} {quantity} @ {price}",
            content=f" Binance 强平: {symbol.upper()} {side} {quantity} @ ${price:.2f}",
            importance=0.85,
            sentiment="bearish" if side == "BUY" else "bullish",  # 多头被强平=看空
            symbols=[symbol.upper()],
            tags=["liquidation", "force_order", side.lower()],
            metadata={
                "symbol": symbol,
                "side": side,
                "price": price,
                "quantity": quantity,
                "value_usd": price * quantity,
                "original_quantity": liquidation.get("q", ""),
                "order_type": liquidation.get("o", "")
            }
        )
        
        if self.on_liquidation:
            await self.on_liquidation(event)
        if self.on_event:
            await self.on_event(event)
    
    async def _handle_mark_price(self, data: Dict):
        """处理标记价格更新"""
        self.stats["price_updates"] += 1
        
        symbol = data.get("s", "").lower()
        mark_price = float(data.get("p", 0))
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.PRICE_UPDATE.value,
            timestamp=data.get("E", 0),
            title=f"Mark Price: {symbol.upper()} = ${mark_price}",
            content=f" Binance 标记价格更新: {symbol.upper()} = ${mark_price}",
            importance=0.3,
            symbols=[symbol.upper()],
            metadata={
                "symbol": symbol,
                "mark_price": mark_price,
                "index_price": float(data.get("i", 0)),
                "settle_price": float(data.get("P", 0))
            }
        )
        
        if self.on_price_update:
            await self.on_price_update(event)
        if self.on_event:
            await self.on_event(event)
    
    async def _handle_book_ticker(self, data: Dict):
        """处理最优买卖价"""
        symbol = data.get("s", "").lower()
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.ORDER_BOOK_UPDATE.value,
            timestamp=datetime.now().timestamp(),
            title=f"Book Ticker: {symbol.upper()}",
            content=f"Bid: {data.get('b', 0)} / Ask: {data.get('a', 0)}",
            importance=0.2,
            symbols=[symbol.upper()],
            metadata={
                "symbol": symbol,
                "bid_price": float(data.get("b", 0)),
                "ask_price": float(data.get("a", 0)),
                "bid_quantity": float(data.get("B", 0)),
                "ask_quantity": float(data.get("A", 0))
            }
        )
        
        if self.on_event:
            await self.on_event(event)
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "is_connected": self.is_connected,
            "is_running": self.is_running
        }
    
    async def start(self):
        """启动（异步入口）"""
        await self.connect()
        await self.listen()
    
    async def stop(self):
        """停止"""
        await self.disconnect()


async def demo():
    """演示"""
    print("=" * 70)
    print("Binance WebSocket 演示")
    print("=" * 70)
    
    config = BinanceConfig(
        symbols=["btcusdt", "ethusdt"],
        stream_types=[
            StreamType.AGG_TRADE,
            StreamType.LIQUIDATION,
            StreamType.MARK_PRICE
        ]
    )
    
    adapter = BinanceWebSocketAdapter(config)
    
    # 设置回调
    async def on_event(event: StandardEvent):
        print(f"\n📊 {event.title}")
        print(f"   Symbol: {event.symbols}")
        print(f"   Sentiment: {event.sentiment}")
        print(f"   Importance: {event.importance}")
    
    adapter.on_event = on_event
    
    try:
        await adapter.start()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        await adapter.stop()
        print(f"\nStats: {adapter.get_stats()}")


if __name__ == "__main__":
    asyncio.run(demo())
