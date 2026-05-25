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

同时集成：
- 多端点自动切换
- 熔断机制
- 降级机制
- Mock数据生成
"""
import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import websockets
from websockets.client import connect

from engines.adapters.contracts import StandardEvent, Source, EventType
from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.data_fallback import (
    get_multi_channel_manager,
    get_data_fallback_manager,
    DataChannelType,
    PriceData
)
from infrastructure.config.defaults.infrastructure.external_apis import EXCHANGE_WS_APIS

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
    
    # K线周期
    kline_interval: str = "1m"  # 1分钟K线
    
    def __post_init__(self):
        if self.stream_types is None:
            self.stream_types = [
                StreamType.AGG_TRADE,
                StreamType.LIQUIDATION,
                StreamType.MARK_PRICE,
                StreamType.KLINE,
                StreamType.FUNDING_RATE,
            ]
        if self.symbols is None:
            self.symbols = ["btcusdt", "ethusdt", "bnbusdt", "solusdt"]


class BinanceWebSocketAdapter:
    """Binance WebSocket 适配器
    
    使用官方 Binance WebSocket Streams API
    文档: https://developers.binance.com/docs/simple-earn/history/Get-Flexible-Rewards-History
    
    集成：
    - 多端点自动切换
    - 熔断机制
    - 降级机制
    - Mock数据生成
    """
    
    BASE_URL = EXCHANGE_WS_APIS["binance"]["futures"]
    TESTNET_URL = EXCHANGE_WS_APIS["binance"]["testnet_futures"]
    
    def __init__(self, config: BinanceConfig = None):
        self.config = config or BinanceConfig()
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        
        # 多通道管理器（用于REST回退）
        self._multi_channel = get_multi_channel_manager()
        self._fallback_manager = get_data_fallback_manager()
        
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
            "errors": 0,
            "fallback_used": 0,
            "rest_data_used": 0
        }
        
        # 最近事件（用于去重）
        self.recent_events: Dict[str, int] = {}  # event_id -> timestamp
        
        # REST回退模式（WebSocket断开时使用）
        self._rest_fallback_mode = False
        self._rest_fallback_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None
    
    def _build_stream_url(self) -> str:
        """构建流 URL - 支持多端点切换"""
        streams = []
        
        for symbol in self.config.symbols:
            for stream_type in self.config.stream_types:
                if stream_type == StreamType.LIQUIDATION:
                    streams.append(f"{symbol}@forceOrder")
                elif stream_type == StreamType.MARK_PRICE:
                    streams.append(f"{symbol}@markPrice@1s")
                elif stream_type == StreamType.AGG_TRADE:
                    streams.append(f"{symbol}@aggTrade")
                elif stream_type == StreamType.BOOK_TICKER:
                    streams.append(f"{symbol}@bookTicker")
                elif stream_type == StreamType.KLINE:
                    streams.append(f"{symbol}@kline_{self.config.kline_interval}")
                elif stream_type == StreamType.FUNDING_RATE:
                    streams.append(f"{symbol}@markPrice@1s")
                # openInterest 已移除，改为通过 REST collector 获取
        
        # 获取可用端点
        try:
            base_url = self._fallback_manager.get_current_endpoint(DataChannelType.BINANCE_WS)
        except:
            base_url = None
            
        if not base_url:
            base_url = self.BASE_URL
        
        return f"{base_url}/{'/'.join(streams)}"
    
    async def connect(self):
        """连接 WebSocket - 支持熔断和REST降级"""
        if self.is_connected:
            return
        
        # 检查熔断器
        try:
            cb = self._fallback_manager.get_circuit_breaker(DataChannelType.BINANCE_WS)
            if cb.state.value == "open":
                logger.warning("Circuit breaker is OPEN, switching to REST fallback mode")
                await self._start_rest_fallback_mode()
                return
        except:
            pass
        
        url = self._build_stream_url()
        logger.info(f"Connecting to Binance WebSocket: {url[:100]}...")
        
        try:
            self.websocket = await connect(
                url,
                ping_interval=20,
                ping_timeout=10
            )
            self.is_connected = True
            try:
                self._fallback_manager.record_success(DataChannelType.BINANCE_WS)
            except:
                pass
            logger.info("Binance WebSocket connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            try:
                self._fallback_manager.record_failure(DataChannelType.BINANCE_WS)
            except:
                pass
            self.is_connected = False
            
            # 切换端点
            try:
                self._fallback_manager.switch_endpoint(DataChannelType.BINANCE_WS)
            except:
                pass
            
            # 检查是否需要启用REST回退
            try:
                status = self._fallback_manager.get_source_status(DataChannelType.BINANCE_WS)
                if status.failure_count >= 3:
                    logger.warning("Too many failures, switching to REST fallback mode")
                    await self._start_rest_fallback_mode()
                else:
                    raise
            except:
                logger.warning("Switching to REST fallback mode")
                await self._start_rest_fallback_mode()
    
    async def _start_rest_fallback_mode(self):
        """启动REST回退模式 - WebSocket断开时使用真实数据"""
        if self._rest_fallback_mode:
            return
        
        logger.warning("Switching to REST FALLBACK mode (real data from other exchanges)")
        self._rest_fallback_mode = True
        self.is_running = True
        self.is_connected = True
        
        logger.info("Starting REST fallback tasks...")
        
        # 启动REST数据拉取任务
        self._rest_fallback_task = asyncio.create_task(self._poll_rest_fallback())
        
        # 启动定期快照任务（每5分钟一次）
        self._snapshot_task = asyncio.create_task(self._periodic_snapshot())
        
        logger.info("REST fallback tasks started")
    
    async def _stop_rest_fallback_mode(self):
        """停止REST回退模式"""
        self._rest_fallback_mode = False
        if self._rest_fallback_task:
            self._rest_fallback_task.cancel()
            try:
                await self._rest_fallback_task
            except asyncio.CancelledError:
                pass
            self._rest_fallback_task = None
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
            self._snapshot_task = None
    
    async def _poll_rest_fallback(self):
        """轮询REST API作为回退数据"""
        logger.info("Starting REST fallback data poller")
        
        while self._rest_fallback_mode and self.is_running:
            try:
                # 为每个交易对拉取价格
                for symbol in self.config.symbols:
                    # 从多通道管理器获取价格
                    price_data = await self._multi_channel.get_price(symbol)
                    
                    if price_data:
                        # 转换为mark price格式并触发回调
                        await self._handle_price_from_rest(price_data)
                        self.stats["rest_data_used"] += 1
                        self.stats["fallback_used"] += 1
                        logger.info(f"Got price from REST fallback: {symbol} = {price_data.price}")
                    else:
                        logger.warning(f"No price data for {symbol} from any channel")
                
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error polling REST fallback: {e}", exc_info=True)
                await asyncio.sleep(1.0)
    
    async def _periodic_snapshot(self):
        """定期拉取快照 - 确保数据一致性"""
        logger.info("Starting periodic snapshot task")
        
        while self._rest_fallback_mode and self.is_running:
            try:
                # 每5分钟拉取一次完整快照
                for symbol in self.config.symbols:
                    snapshot = await self._multi_channel.get_snapshot(symbol)
                    if snapshot:
                        logger.debug(f"Received snapshot for {symbol}")
                
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in periodic snapshot: {e}")
                await asyncio.sleep(60)
    
    async def _handle_price_from_rest(self, price_data: PriceData):
        """将REST获取的价格转换为事件"""
        symbol = price_data.symbol.lower()
        
        # 构建类似mark price的数据格式
        data = {
            "s": price_data.symbol.upper(),
            "p": str(price_data.price),
            "i": str(price_data.bid) if price_data.bid else str(price_data.price),
            "P": str(price_data.ask) if price_data.ask else str(price_data.price),
            "E": price_data.timestamp
        }
        
        await self._handle_mark_price(data)
    
    async def disconnect(self):
        """断开连接"""
        self.is_running = False
        await self._stop_rest_fallback_mode()
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.is_connected = False
        logger.info("Binance WebSocket disconnected")
    
    async def listen(self):
        """监听消息"""
        if not self.is_connected:
            await self.connect()
        
        # 如果是REST回退模式，不需要监听真实ws
        if self._rest_fallback_mode:
            logger.info("Running in REST FALLBACK mode")
            while self.is_running and self._rest_fallback_mode:
                await asyncio.sleep(1.0)
            return
        
        self.is_running = True
        logger.info("Binance WebSocket listening...")
        
        try:
            async for message in self.websocket:
                if not self.is_running:
                    break
                
                try:
                    data = json.loads(message)
                    try:
                        self._fallback_manager.record_success(DataChannelType.BINANCE_WS)
                    except:
                        pass
                    await self._process_message(data)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {message[:100]}")
                    self.stats["errors"] += 1
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.stats["errors"] += 1
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Binance WebSocket connection closed: {e}")
            self.is_connected = False
            try:
                self._fallback_manager.record_failure(DataChannelType.BINANCE_WS)
            except:
                pass
            
            # 自动重连或降级
            if self.is_running:
                await self._reconnect()
    
    async def _reconnect(self, delay: int = 5):
        """自动重连 - 支持多端点和REST降级"""
        logger.info(f"Reconnecting in {delay}s...")
        await asyncio.sleep(delay)
        
        # 切换到下一个端点
        try:
            self._fallback_manager.switch_endpoint(DataChannelType.BINANCE_WS)
        except:
            pass
        
        try:
            await self.connect()
            await self.listen()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            
            # 检查是否需要启用REST回退
            try:
                status = self._fallback_manager.get_source_status(DataChannelType.BINANCE_WS)
                if status.failure_count >= 3:
                    logger.warning("Too many failures, switching to REST fallback mode")
                    await self._start_rest_fallback_mode()
                else:
                    await self._reconnect(delay=min(delay * 2, 60))
            except:
                logger.warning("Switching to REST fallback mode")
                await self._start_rest_fallback_mode()
    
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
        elif event_type == "kline":
            await self._handle_kline(data)
        elif event_type == "24hrTicker":
            await self._handle_ticker(data)
        elif event_type == "openInterest":
            await self._handle_open_interest(data)
        elif "bookTicker" in data or (data.get("u") and "b" in data and "a" in data):
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
            event_type=EventType.LIQUIDATION.value,
            timestamp=data.get("E", 0),
            title=f"Liquidation: {symbol.upper()} {side} {quantity} @ {price}",
            content=f" Binance 强平: {symbol.upper()} {side} {quantity} @ ${price:.2f}",
            importance=0.85,
            sentiment="bearish" if side == "BUY" else "bullish",
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
        """处理标记价格更新 — 同时提取 funding rate"""
        self.stats["price_updates"] += 1
        
        symbol = data.get("s", "").lower()
        mark_price = float(data.get("p", 0))
        funding_rate = float(data.get("r", 0))
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.MARK_PRICE.value,
            timestamp=data.get("E", 0),
            title=f"Mark Price: {symbol.upper()} = ${mark_price}",
            content=f" Binance 标记价格更新: {symbol.upper()} = ${mark_price}",
            importance=0.3,
            symbols=[symbol.upper()],
            metadata={
                "symbol": symbol,
                "mark_price": mark_price,
                "index_price": float(data.get("i", 0)),
                "settle_price": float(data.get("P", 0)),
                "funding_rate": funding_rate,
                "funding_time": data.get("T", 0),
            }
        )
        
        if self.on_price_update:
            await self.on_price_update(event)
        if self.on_event:
            await self.on_event(event)
        
        if StreamType.FUNDING_RATE in self.config.stream_types and funding_rate != 0:
            funding_event = StandardEvent(
                source=Source.BINANCE.value,
                event_type=EventType.FUNDING.value,
                timestamp=data.get("E", 0),
                title=f"Funding: {symbol.upper()} rate={funding_rate}",
                content=f"Funding rate: {funding_rate}",
                importance=0.4,
                symbols=[symbol.upper()],
                tags=["funding"],
                metadata={
                    "symbol": symbol,
                    "funding_rate": funding_rate,
                    "mark_price": mark_price,
                    "index_price": float(data.get("i", 0)),
                    "funding_time": data.get("T", 0),
                }
            )
            if self.on_event:
                await self.on_event(funding_event)
    
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
    
    async def _handle_kline(self, data: Dict):
        """处理K线数据"""
        if "klines" not in self.stats:
            self.stats["klines"] = 0
        self.stats["klines"] += 1
        
        kline_data = data.get("k", {})
        symbol = data.get("s", "").lower()
        is_closed = kline_data.get("x", False)
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.KLINE.value,
            timestamp=data.get("E", 0),
            title=f"Kline: {symbol.upper()} {kline_data.get('i', '')} - {'Closed' if is_closed else 'Open'}",
            content=f"O: {kline_data.get('o')} H: {kline_data.get('h')} L: {kline_data.get('l')} C: {kline_data.get('c')} V: {kline_data.get('v')}",
            importance=0.4 if is_closed else 0.1,
            symbols=[symbol.upper()],
            tags=["kline", "candle"],
            metadata={
                "symbol": symbol,
                "interval": kline_data.get("i", ""),
                "open": float(kline_data.get("o", 0)),
                "high": float(kline_data.get("h", 0)),
                "low": float(kline_data.get("l", 0)),
                "close": float(kline_data.get("c", 0)),
                "volume": float(kline_data.get("v", 0)),
                "is_closed": is_closed,
                "start_time": kline_data.get("t", 0),
                "end_time": kline_data.get("T", 0)
            }
        )
        
        if self.on_event:
            await self.on_event(event)
    
    async def _handle_ticker(self, data: Dict):
        """处理24hr行情数据"""
        if "tickers" not in self.stats:
            self.stats["tickers"] = 0
        self.stats["tickers"] += 1
        
        symbol = data.get("s", "").lower()
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.PRICE_UPDATE.value,
            timestamp=data.get("E", 0),
            title=f"24h Ticker: {symbol.upper()}",
            content=f"Change: {data.get('P', 0)}% | High: {data.get('h', 0)} | Low: {data.get('l', 0)}",
            importance=0.3,
            symbols=[symbol.upper()],
            metadata={
                "symbol": symbol,
                "price_change": float(data.get("p", 0)),
                "price_change_percent": float(data.get("P", 0)),
                "open": float(data.get("o", 0)),
                "high": float(data.get("h", 0)),
                "low": float(data.get("l", 0)),
                "close": float(data.get("c", 0)),
                "volume": float(data.get("v", 0)),
                "quote_volume": float(data.get("q", 0))
            }
        )
        
        if self.on_event:
            await self.on_event(event)
    
    async def _handle_open_interest(self, data: Dict):
        """处理持仓量数据"""
        if "open_interests" not in self.stats:
            self.stats["open_interests"] = 0
        self.stats["open_interests"] += 1
        
        symbol = data.get("s", "").lower()
        oi = float(data.get("o", 0))
        time = data.get("E", 0)
        
        event = StandardEvent(
            source=Source.BINANCE.value,
            event_type=EventType.OPEN_INTEREST.value,
            timestamp=time,
            title=f"Open Interest: {symbol.upper()}",
            content=f"OI: {oi}",
            importance=0.35,
            symbols=[symbol.upper()],
            tags=["open_interest", "oi"],
            metadata={
                "symbol": symbol,
                "open_interest": oi,
                "timestamp": time
            }
        )
        
        if self.on_event:
            await self.on_event(event)
    
    def get_stats(self) -> Dict:
        """获取统计"""
        try:
            fallback_stats = self._fallback_manager.get_stats()
        except:
            fallback_stats = {}
            
        try:
            multi_channel_health = self._multi_channel.get_health_status()
        except:
            multi_channel_health = {}
            
        return {
            **self.stats,
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "rest_fallback_mode": self._rest_fallback_mode,
            "fallback_manager": fallback_stats,
            "multi_channel": multi_channel_health
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
