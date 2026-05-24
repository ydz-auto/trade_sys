"""
Orderbook Runtime - 订单簿运行时（事件驱动）

核心能力：
1. 实时订单簿状态维护
2. 订单簿特征计算（深度、价差、流动性等）
3. 事件驱动更新
4. Point-in-Time 存储

架构：
    Orderbook Event
         ↓
    OrderbookRuntime (单一入口)
         ↓
    FeatureRuntime
         ↓
    PIT Store

重点防护：
- 订单簿状态一致性
- 事件顺序保证
- 时间因果安全
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import (
    RuntimeClock,
    ClockMode,
    get_clock,
    set_clock_mode,
    now_ms
)
from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    get_point_in_time_store,
    FeatureSourceType
)


logger = get_logger("orderbook_runtime")


class OrderbookMode(Enum):
    LIVE = "live"
    REPLAY = "replay"
    PAPER = "paper"


@dataclass
class OrderbookLevel:
    """订单簿档位"""
    price: float
    volume: float
    count: int = 0


@dataclass
class OrderbookData:
    """订单簿数据"""
    symbol: str
    timestamp_ms: int
    bids: List[OrderbookLevel]
    asks: List[OrderbookLevel]
    update_id: int = 0


@dataclass
class OrderbookConfig:
    """订单簿运行时配置"""
    symbol: str = "BTCUSDT"
    mode: OrderbookMode = OrderbookMode.LIVE
    max_depth: int = 20
    snapshot_interval_ms: int = 1000


class OrderbookRuntime:
    """
    订单簿运行时（事件驱动）
    
    核心能力：
    - 实时订单簿状态维护
    - 订单簿特征计算
    - 事件驱动更新
    - Point-in-Time 存储
    
    订单簿特征：
    - bid_ask_spread: 买卖价差
    - bid_ask_ratio: 买卖量比
    - orderbook_imbalance: 订单簿失衡
    - depth_bid/ask: 买卖深度
    - liquidity_bid/ask: 买卖流动性
    - volume_weighted_price: 成交量加权价格
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[OrderbookConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.config = config or OrderbookConfig()
        
        # 1. 基础设施
        self._clock = get_clock()
        self._pit_store = get_point_in_time_store(f"orderbook_{self.config.symbol}")
        
        # 2. 订单簿状态
        self._bids: Dict[float, OrderbookLevel] = {}
        self._asks: Dict[float, OrderbookLevel] = {}
        self._last_update_id = 0
        
        # 3. 事件队列
        self._event_queue = asyncio.Queue(maxsize=10000)
        self._processing_task = None
        
        # 4. 回调
        self._on_update_callback = None
        self._on_snapshot_callback = None
        
        # 5. 设置模式
        self._setup_mode()
        
        self._initialized = True
        logger.info(f"OrderbookRuntime initialized: {self.config.symbol}, max_depth={self.config.max_depth}")
    
    def _setup_mode(self):
        """设置运行模式"""
        if self.config.mode == OrderbookMode.REPLAY:
            set_clock_mode(ClockMode.REPLAY)
        elif self.config.mode == OrderbookMode.PAPER:
            set_clock_mode(ClockMode.PAPER)
        else:
            set_clock_mode(ClockMode.LIVE)
    
    def set_callbacks(
        self,
        on_update: Optional[callable] = None,
        on_snapshot: Optional[callable] = None
    ):
        """设置回调"""
        self._on_update_callback = on_update
        self._on_snapshot_callback = on_snapshot
    
    async def start(self):
        """启动订单簿运行时"""
        if self._processing_task and not self._processing_task.done():
            return
        
        self._processing_task = asyncio.create_task(self._process_events())
        logger.info("OrderbookRuntime started")
    
    async def stop(self):
        """停止订单簿运行时"""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("OrderbookRuntime stopped")
    
    async def _process_events(self):
        """处理事件队列"""
        while True:
            try:
                event = await self._event_queue.get()
                await self._process_event(event)
                self._event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing orderbook event: {e}")
    
    async def _process_event(self, event: Dict[str, Any]):
        """处理单个订单簿事件"""
        event_type = event.get('type')
        timestamp_ms = event.get('timestamp_ms', now_ms())
        
        if event_type == "snapshot":
            await self._process_snapshot(event, timestamp_ms)
        elif event_type == "update":
            await self._process_update(event, timestamp_ms)
        
        # 推进时钟
        self._clock.advance_to(timestamp_ms)
    
    async def _process_snapshot(self, event: Dict[str, Any], timestamp_ms: int):
        """处理订单簿快照"""
        bids = event.get('bids', [])
        asks = event.get('asks', [])
        update_id = event.get('update_id', 0)
        
        # 清空并重建订单簿
        self._bids = {}
        self._asks = {}
        self._last_update_id = update_id
        
        # 处理卖盘（按价格降序）
        for price_str, volume_str, count in bids[:self.config.max_depth]:
            price = float(price_str)
            volume = float(volume_str)
            self._bids[price] = OrderbookLevel(price=price, volume=volume, count=count)
        
        # 处理买盘（按价格升序）
        for price_str, volume_str, count in asks[:self.config.max_depth]:
            price = float(price_str)
            volume = float(volume_str)
            self._asks[price] = OrderbookLevel(price=price, volume=volume, count=count)
        
        # 计算特征并存储
        await self._compute_and_store_features(timestamp_ms)
    
    async def _process_update(self, event: Dict[str, Any], timestamp_ms: int):
        """处理订单簿更新"""
        bids = event.get('bids', [])
        asks = event.get('asks', [])
        update_id = event.get('update_id', 0)
        
        # 更新ID验证
        if update_id <= self._last_update_id:
            logger.debug(f"Out of order update: {update_id} <= {self._last_update_id}")
            return
        
        self._last_update_id = update_id
        
        # 更新卖盘
        for price_str, volume_str in bids:
            price = float(price_str)
            volume = float(volume_str)
            
            if volume <= 0:
                self._bids.pop(price, None)
            else:
                self._bids[price] = OrderbookLevel(price=price, volume=volume)
        
        # 更新买盘
        for price_str, volume_str in asks:
            price = float(price_str)
            volume = float(volume_str)
            
            if volume <= 0:
                self._asks.pop(price, None)
            else:
                self._asks[price] = OrderbookLevel(price=price, volume=volume)
        
        # 计算特征并存储
        await self._compute_and_store_features(timestamp_ms)
    
    async def _compute_and_store_features(self, timestamp_ms: int):
        """计算订单簿特征并存储"""
        features = self._compute_features()
        
        # 存储到 PIT Store
        self._pit_store.store_features_batch(
            features=features,
            feature_timestamp=timestamp_ms,
            source_types={key: FeatureSourceType.CALCULATED for key in features}
        )
        
        # 触发回调
        if self._on_update_callback:
            await self._on_update_callback(timestamp_ms, features)
    
    def _compute_features(self) -> Dict[str, float]:
        """计算订单簿特征"""
        features = {}
        
        # 获取最优买卖价
        best_bid = max(self._bids.keys()) if self._bids else 0
        best_ask = min(self._asks.keys()) if self._asks else 0
        
        # 买卖价差
        if best_bid > 0 and best_ask > 0:
            features['bid_ask_spread'] = best_ask - best_bid
            features['bid_ask_spread_pct'] = (best_ask - best_bid) / best_bid
        else:
            features['bid_ask_spread'] = 0
            features['bid_ask_spread_pct'] = 0
        
        # 订单簿失衡
        bid_volume = sum(level.volume for level in self._bids.values())
        ask_volume = sum(level.volume for level in self._asks.values())
        
        if bid_volume + ask_volume > 0:
            features['orderbook_imbalance'] = (bid_volume - ask_volume) / (bid_volume + ask_volume)
            features['bid_ask_ratio'] = bid_volume / ask_volume if ask_volume > 0 else 0
        else:
            features['orderbook_imbalance'] = 0
            features['bid_ask_ratio'] = 0
        
        # 深度加权价格
        features['depth_weighted_bid'] = self._calculate_depth_weighted_price(list(self._bids.values())[:5])
        features['depth_weighted_ask'] = self._calculate_depth_weighted_price(list(self._asks.values())[:5])
        
        # 流动性（前N档）
        features['liquidity_bid_5'] = sum(level.volume for level in list(self._bids.values())[:5])
        features['liquidity_ask_5'] = sum(level.volume for level in list(self._asks.values())[:5])
        features['liquidity_bid_10'] = sum(level.volume for level in list(self._bids.values())[:10])
        features['liquidity_ask_10'] = sum(level.volume for level in list(self._asks.values())[:10])
        
        # 价格冲击估计
        features['price_impact_bid'] = self._estimate_price_impact(self._bids, 0.1)
        features['price_impact_ask'] = self._estimate_price_impact(self._asks, 0.1)
        
        # 最优价格
        features['best_bid'] = best_bid
        features['best_ask'] = best_ask
        features['mid_price'] = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
        
        return features
    
    def _calculate_depth_weighted_price(self, levels: List[OrderbookLevel]) -> float:
        """计算深度加权价格"""
        total_volume = sum(level.volume for level in levels)
        if total_volume == 0:
            return 0
        
        weighted_sum = sum(level.price * level.volume for level in levels)
        return weighted_sum / total_volume
    
    def _estimate_price_impact(self, orders: Dict[float, OrderbookLevel], target_volume: float) -> float:
        """估计价格冲击"""
        if not orders:
            return 0
        
        remaining = target_volume
        cumulative_price = 0
        cumulative_volume = 0
        
        # 按价格排序
        if orders == self._bids:
            sorted_levels = sorted(orders.values(), key=lambda x: -x.price)  # 卖盘降序
        else:
            sorted_levels = sorted(orders.values(), key=lambda x: x.price)  # 买盘升序
        
        for level in sorted_levels:
            if remaining <= 0:
                break
            
            take_volume = min(remaining, level.volume)
            cumulative_price += level.price * take_volume
            cumulative_volume += take_volume
            remaining -= take_volume
        
        if cumulative_volume > 0:
            avg_price = cumulative_price / cumulative_volume
            best_price = max(orders.keys()) if orders == self._bids else min(orders.keys())
            return abs(avg_price - best_price) / best_price
        
        return 0
    
    async def emit_event(self, event_type: str, data: Dict[str, Any], timestamp_ms: Optional[int] = None):
        """
        发射订单簿事件
        
        Args:
            event_type: "snapshot" 或 "update"
            data: 事件数据
            timestamp_ms: 时间戳（可选）
        """
        if timestamp_ms is None:
            timestamp_ms = now_ms()
        
        event = {
            'type': event_type,
            'timestamp_ms': timestamp_ms,
            **data
        }
        
        await self._event_queue.put(event)
    
    def get_orderbook(self) -> OrderbookData:
        """获取当前订单簿状态"""
        return OrderbookData(
            symbol=self.config.symbol,
            timestamp_ms=now_ms(),
            bids=sorted(self._bids.values(), key=lambda x: -x.price),
            asks=sorted(self._asks.values(), key=lambda x: x.price),
            update_id=self._last_update_id
        )
    
    def get_features(self) -> Dict[str, float]:
        """获取当前订单簿特征"""
        return self._compute_features()
    
    def get_features_at(self, timestamp_ms: int) -> Dict[str, float]:
        """获取指定时间的订单簿特征"""
        snapshot = self._pit_store.get_features_at_time(timestamp_ms)
        return snapshot.features if hasattr(snapshot, 'features') else snapshot


def get_orderbook_runtime(config: Optional[OrderbookConfig] = None) -> OrderbookRuntime:
    """获取订单簿运行时（单一实例）"""
    return OrderbookRuntime(config)


__all__ = ["OrderbookRuntime", "OrderbookConfig", "OrderbookData", "get_orderbook_runtime"]