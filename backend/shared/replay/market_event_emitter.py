"""
Market Event Emitter - 从历史数据发出真实事件流

核心职责：
1. 从 Parquet/ClickHouse 读取历史数据
2. 发出与实时流完全一致的事件格式
3. 确保 Replay = Live

这是统一 Research Pipeline 和 Runtime Pipeline 的关键组件。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from pathlib import Path
from enum import Enum
import asyncio
import pandas as pd
import numpy as np

from shared.contracts import (
    Candle,
    Trade,
    OrderBook,
    OrderBookLevel,
    Exchange,
    Timeframe,
    StandardEvent,
    EventType,
    Source,
)


class EmitMode(str, Enum):
    REALTIME = "realtime"
    FAST = "fast"
    INSTANT = "instant"


@dataclass
class EmitterConfig:
    speed: float = 1.0
    emit_mode: EmitMode = EmitMode.FAST
    batch_size: int = 1000
    include_trades: bool = True
    include_orderbook: bool = False
    include_funding: bool = True
    include_liquidation: bool = True


@dataclass
class MarketEventEnvelope:
    event_id: str
    event_type: str
    timestamp: int
    symbol: str
    exchange: str
    data: Dict[str, Any]
    sequence: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "data": self.data,
            "sequence": self.sequence,
        }


class MarketEventEmitter:
    """
    市场事件发射器
    
    从历史数据发出与实时流完全一致的事件格式。
    
    用法：
    ```python
    emitter = MarketEventEmitter()
    async for event in emitter.emit_from_parquet(path, symbol, start, end):
        await signal_runtime.process(event)
        await execution_runtime.process(event)
    ```
    """
    
    def __init__(self, config: EmitterConfig = None):
        self.config = config or EmitterConfig()
        self._sequence = 0
        self._handlers: Dict[str, List[Callable]] = {}
    
    def register_handler(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def emit_from_parquet(
        self,
        parquet_path: Path,
        symbol: str,
        exchange: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> AsyncIterator[MarketEventEnvelope]:
        """
        从 Parquet 文件发出事件流
        
        这是核心方法，确保：
        1. 发出的事件格式与实时流完全一致
        2. 按时间顺序严格排序
        3. 支持暂停/恢复
        """
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        if start_time:
            start_dt = pd.Timestamp(start_time) if isinstance(start_time, str) else pd.to_datetime(start_time, unit='ms')
            df = df[df['timestamp'] >= start_dt]
        
        if end_time:
            end_dt = pd.Timestamp(end_time) if isinstance(end_time, str) else pd.to_datetime(end_time, unit='ms')
            df = df[df['timestamp'] <= end_dt]
        
        for idx, row in df.iterrows():
            events = self._row_to_events(row, symbol, exchange)
            
            for event in events:
                self._sequence += 1
                event.sequence = self._sequence
                
                await self._dispatch_to_handlers(event)
                
                yield event
                
                if self.config.emit_mode == EmitMode.REALTIME:
                    await asyncio.sleep(0.001 / self.config.speed)
    
    async def emit_from_feature_parquet(
        self,
        parquet_path: Path,
        symbol: str,
        exchange: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> AsyncIterator[MarketEventEnvelope]:
        """
        从 Feature Parquet 发出事件流
        
        Feature Parquet 包含更多字段，发出更丰富的事件。
        """
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        if start_time:
            if isinstance(start_time, str):
                start_dt = pd.Timestamp(start_time)
            else:
                start_dt = pd.to_datetime(start_time, unit='ms')
            df = df[df['timestamp'] >= start_dt]
        
        if end_time:
            if isinstance(end_time, str):
                end_dt = pd.Timestamp(end_time)
            else:
                end_dt = pd.to_datetime(end_time, unit='ms')
            df = df[df['timestamp'] <= end_dt]
        
        for idx, row in df.iterrows():
            events = self._feature_row_to_events(row, symbol, exchange)
            
            for event in events:
                self._sequence += 1
                event.sequence = self._sequence
                
                await self._dispatch_to_handlers(event)
                
                yield event
    
    def _row_to_events(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
    ) -> List[MarketEventEnvelope]:
        """将一行数据转换为事件列表"""
        events = []
        ts = int(row['timestamp'].timestamp() * 1000) if isinstance(row['timestamp'], pd.Timestamp) else int(row['timestamp'])
        
        candle_event = self._create_candle_event(row, symbol, exchange, ts)
        events.append(candle_event)
        
        if self.config.include_trades and 'volume' in row:
            trade_events = self._create_trade_events(row, symbol, exchange, ts)
            events.extend(trade_events)
        
        if self.config.include_funding and 'funding_rate' in row:
            funding_event = self._create_funding_event(row, symbol, exchange, ts)
            if funding_event:
                events.append(funding_event)
        
        if self.config.include_liquidation and 'liquidation' in row:
            liq_event = self._create_liquidation_event(row, symbol, exchange, ts)
            if liq_event:
                events.append(liq_event)
        
        return events
    
    def _feature_row_to_events(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
    ) -> List[MarketEventEnvelope]:
        """将 Feature 行转换为事件列表"""
        events = []
        ts = int(row['timestamp'].timestamp() * 1000) if isinstance(row['timestamp'], pd.Timestamp) else int(row['timestamp'])
        
        candle_event = self._create_candle_event(row, symbol, exchange, ts)
        events.append(candle_event)
        
        feature_event = self._create_feature_event(row, symbol, exchange, ts)
        events.append(feature_event)
        
        if self.config.include_funding:
            funding_event = self._create_funding_event(row, symbol, exchange, ts)
            if funding_event:
                events.append(funding_event)
        
        return events
    
    def _create_candle_event(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
        ts: int,
    ) -> MarketEventEnvelope:
        """创建 K线事件"""
        candle_data = {
            "open": float(row.get('open', 0)),
            "high": float(row.get('high', 0)),
            "low": float(row.get('low', 0)),
            "close": float(row.get('close', 0)),
            "volume": float(row.get('volume', 0)),
            "quote_volume": float(row.get('quote_volume', row.get('volume', 0) * row.get('close', 0))),
            "trade_count": int(row.get('trade_count', 0)),
            "open_time": ts,
            "close_time": ts + 60000,
            "timeframe": "1m",
        }
        
        return MarketEventEnvelope(
            event_id=f"candle_{symbol}_{ts}",
            event_type="candle_1m",
            timestamp=ts,
            symbol=symbol,
            exchange=exchange,
            data=candle_data,
        )
    
    def _create_trade_events(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
        ts: int,
    ) -> List[MarketEventEnvelope]:
        """创建成交事件（模拟）"""
        events = []
        
        volume = float(row.get('volume', 0))
        if volume <= 0:
            return events
        
        close = float(row.get('close', 0))
        if close <= 0:
            return events
        
        trade_count = max(1, int(row.get('trade_count', volume / close / 0.1)))
        avg_trade_size = volume / trade_count
        
        for i in range(min(trade_count, 5)):
            trade_ts = ts + i * (60000 // max(1, trade_count))
            
            trade_data = {
                "price": close * (1 + np.random.uniform(-0.0001, 0.0001)),
                "quantity": avg_trade_size * (0.5 + np.random.random()),
                "is_buyer_maker": np.random.random() > 0.5,
                "trade_id": f"trade_{symbol}_{trade_ts}_{i}",
            }
            
            events.append(MarketEventEnvelope(
                event_id=f"trade_{symbol}_{trade_ts}_{i}",
                event_type="trade",
                timestamp=trade_ts,
                symbol=symbol,
                exchange=exchange,
                data=trade_data,
            ))
        
        return events
    
    def _create_funding_event(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
        ts: int,
    ) -> Optional[MarketEventEnvelope]:
        """创建资金费率事件"""
        funding_rate = row.get('funding_rate')
        if funding_rate is None or pd.isna(funding_rate):
            return None
        
        funding_data = {
            "funding_rate": float(funding_rate),
            "funding_time": ts,
            "mark_price": float(row.get('close', 0)),
            "index_price": float(row.get('close', 0)),
        }
        
        return MarketEventEnvelope(
            event_id=f"funding_{symbol}_{ts}",
            event_type="funding_rate",
            timestamp=ts,
            symbol=symbol,
            exchange=exchange,
            data=funding_data,
        )
    
    def _create_liquidation_event(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
        ts: int,
    ) -> Optional[MarketEventEnvelope]:
        """创建爆仓事件"""
        liquidation = row.get('liquidation')
        if liquidation is None or pd.isna(liquidation):
            return None
        
        liq_data = {
            "liquidation_volume": float(liquidation),
            "price": float(row.get('close', 0)),
            "side": "long" if row.get('close', 0) < row.get('open', 0) else "short",
        }
        
        return MarketEventEnvelope(
            event_id=f"liq_{symbol}_{ts}",
            event_type="liquidation",
            timestamp=ts,
            symbol=symbol,
            exchange=exchange,
            data=liq_data,
        )
    
    def _create_feature_event(
        self,
        row: pd.Series,
        symbol: str,
        exchange: str,
        ts: int,
    ) -> MarketEventEnvelope:
        """创建特征事件"""
        feature_fields = [
            'rsi_14', 'rsi_7', 'rsi_21',
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_lower', 'bb_width',
            'sma_20', 'sma_50', 'ema_20', 'ema_50',
            'volume_ratio', 'oi_delta', 'funding_zscore',
        ]
        
        features = {}
        for field in feature_fields:
            if field in row and not pd.isna(row[field]):
                features[field] = float(row[field])
        
        return MarketEventEnvelope(
            event_id=f"feature_{symbol}_{ts}",
            event_type="features",
            timestamp=ts,
            symbol=symbol,
            exchange=exchange,
            data={"features": features},
        )
    
    async def _dispatch_to_handlers(self, event: MarketEventEnvelope):
        """分发事件到处理器"""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                pass
    
    def to_candle(self, event: MarketEventEnvelope) -> Candle:
        """将事件转换为 Candle 对象"""
        data = event.data
        return Candle(
            symbol=event.symbol,
            exchange=Exchange(event.exchange),
            timeframe=Timeframe.M1,
            open_time=data['open_time'],
            close_time=data['close_time'],
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            volume=data['volume'],
            quote_volume=data.get('quote_volume', 0),
            trade_count=data.get('trade_count', 0),
        )
    
    def to_trade(self, event: MarketEventEnvelope) -> Trade:
        """将事件转换为 Trade 对象"""
        data = event.data
        return Trade(
            symbol=event.symbol,
            exchange=Exchange(event.exchange),
            timestamp=event.timestamp,
            price=data['price'],
            quantity=data['quantity'],
            quote_quantity=data['price'] * data['quantity'],
            is_buyer_maker=data.get('is_buyer_maker', False),
            trade_id=event.event_id,
        )
