"""
OrderBook Aggregator - 订单簿聚合器（70G优化版）

从订单簿快照提取高价值特征：
- Top-of-Book / 流动性 Feature
- Imbalance（最重要）
- Depth Feature
- Trade Flow（极其重要）
- Sweep / 流动性冲击
- 波动 / 流动性恶化
"""

from typing import Dict, Optional, List, Deque
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
import time

from infrastructure.logging import get_logger
from services.aggregation_service.models.orderbook_model import (
    OrderBookSnapshot, 
    OrderBookFeature, 
    TradeFlowState,
    SweepState,
    TradeEvent
)

logger = get_logger("aggregation_service.orderbook_aggregator")


@dataclass
class SymbolState:
    """单个交易对的状态"""
    last_snapshot: Optional[OrderBookSnapshot] = None
    last_feature: Optional[OrderBookFeature] = None
    trade_flow: TradeFlowState = field(default_factory=TradeFlowState)
    sweep: SweepState = field(default_factory=SweepState)
    
    spread_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    imbalance_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    
    last_second_timestamp: int = 0
    trades_in_second: List[TradeEvent] = field(default_factory=list)
    
    prev_top5_depth: float = 0.0
    book_flips: int = 0
    last_imbalance_sign: int = 0


class TradeFlowCalculator:
    """交易流计算器"""
    
    LARGE_TRADE_THRESHOLD_USD = 10000
    
    @staticmethod
    def update_trade_flow(
        state: SymbolState, 
        trade: TradeEvent, 
        best_bid: float, 
        best_ask: float
    ) -> None:
        # 基础主动买卖流
        if trade.is_buyer_maker:
            state.trade_flow.aggressive_sell_volume += trade.quantity
            state.trade_flow.trade_delta -= trade.quantity
        else:
            state.trade_flow.aggressive_buy_volume += trade.quantity
            state.trade_flow.trade_delta += trade.quantity
        
        # 累积delta
        state.trade_flow.cumulative_delta += state.trade_flow.trade_delta
        
        # 交易计数
        state.trade_flow.total_trade_count += 1
        
        # 交易量和金额
        trade_value = trade.price * trade.quantity
        state.trade_flow.total_volume += trade.quantity
        state.trade_flow.total_value += trade_value
        
        # 平均单笔成交量
        state.trade_flow.avg_trade_size = (
            state.trade_flow.total_volume / state.trade_flow.total_trade_count
            if state.trade_flow.total_trade_count > 0 else 0.0
        )
        
        # 买卖比例
        total_buy = state.trade_flow.aggressive_buy_volume
        total_sell = state.trade_flow.aggressive_sell_volume
        if total_sell > 0:
            state.trade_flow.buy_sell_ratio = total_buy / total_sell
        elif total_buy > 0:
            state.trade_flow.buy_sell_ratio = float('inf')
        else:
            state.trade_flow.buy_sell_ratio = 1.0
        
        # VWAP计算
        if state.trade_flow.total_volume > 0:
            state.trade_flow.vwap = (
                state.trade_flow.total_value / state.trade_flow.total_volume
            )
        
        # 最大/最小单笔成交
        if trade.quantity > state.trade_flow.max_trade_size:
            state.trade_flow.max_trade_size = trade.quantity
        if trade.quantity < state.trade_flow.min_trade_size:
            state.trade_flow.min_trade_size = trade.quantity
        
        # 大单检测
        if trade_value >= TradeFlowCalculator.LARGE_TRADE_THRESHOLD_USD:
            state.trade_flow.large_trade_count += 1
        
        # 成交速度（每秒成交次数）
        if state.trade_flow.last_trade_timestamp > 0:
            time_diff = (trade.timestamp - state.trade_flow.last_trade_timestamp) / 1000.0
            if time_diff > 0:
                state.trade_flow.trade_velocity = 1.0 / time_diff
                # 交易强度 = 成交量 / 时间间隔
                state.trade_flow.trade_intensity = trade.quantity / time_diff
        
        # 价格冲击（相对于中间价的偏离）
        if best_bid > 0 and best_ask > 0:
            mid_price = (best_bid + best_ask) / 2
            if mid_price > 0:
                state.trade_flow.price_impact = abs(trade.price - mid_price) / mid_price
        
        state.trade_flow.last_trade_timestamp = trade.timestamp
    
    @staticmethod
    def reset_second_delta(state: SymbolState) -> None:
        state.trade_flow.trade_delta = 0.0
        state.trade_flow.aggressive_buy_volume = 0.0
        state.trade_flow.aggressive_sell_volume = 0.0
        state.trade_flow.large_trade_count = 0
        state.trade_flow.total_trade_count = 0
        state.trade_flow.total_volume = 0.0
        state.trade_flow.total_value = 0.0
        state.trade_flow.avg_trade_size = 0.0
        state.trade_flow.buy_sell_ratio = 0.0
        state.trade_flow.trade_intensity = 0.0
        state.trade_flow.vwap = 0.0
        state.trade_flow.max_trade_size = 0.0
        state.trade_flow.min_trade_size = float('inf')
        state.trade_flow.price_impact = 0.0


class SweepDetector:
    """扫单检测器"""
    
    SWEEP_THRESHOLD_LEVELS = 3
    SWEEP_VOLUME_THRESHOLD = 5.0
    
    @staticmethod
    def detect_sweep(
        state: SymbolState,
        snapshot: OrderBookSnapshot,
        trades: List[TradeEvent]
    ) -> SweepState:
        if not trades:
            return state.sweep
        
        sweep = SweepState()
        
        buy_levels_consumed = 0
        sell_levels_consumed = 0
        total_buy_volume = 0.0
        total_sell_volume = 0.0
        
        best_ask = snapshot.asks[0].price if snapshot.asks else 0
        best_bid = snapshot.bids[0].price if snapshot.bids else 0
        
        for trade in trades:
            if not trade.is_buyer_maker:
                total_buy_volume += trade.quantity
                if trade.price >= best_ask:
                    buy_levels_consumed += 1
            else:
                total_sell_volume += trade.quantity
                if trade.price <= best_bid:
                    sell_levels_consumed += 1
        
        if buy_levels_consumed >= SweepDetector.SWEEP_THRESHOLD_LEVELS:
            sweep.sweep_buy_score = min(buy_levels_consumed / 10.0, 1.0) * total_buy_volume
            sweep.multi_level_fill = buy_levels_consumed
        
        if sell_levels_consumed >= SweepDetector.SWEEP_THRESHOLD_LEVELS:
            sweep.sweep_sell_score = min(sell_levels_consumed / 10.0, 1.0) * total_sell_volume
            sweep.multi_level_fill = max(sweep.multi_level_fill, sell_levels_consumed)
        
        top5_ask_vol = sum(a.quantity for a in snapshot.asks[:5])
        if top5_ask_vol < state.prev_top5_depth * 0.3:
            sweep.liquidity_vacuum = (state.prev_top5_depth - top5_ask_vol) / state.prev_top5_depth if state.prev_top5_depth > 0 else 0
        
        state.sweep = sweep
        return sweep


class OrderBookAggregator:
    """订单簿聚合器（70G优化版）

    从订单簿快照提取高价值特征：
    - Spread / Mid Price / Microprice
    - Imbalance (1/5/10档)
    - Depth (top5/top10)
    - Trade Flow (delta/累积delta/大单)
    - Sweep (扫单检测)
    - Volatility (点差波动/深度变化)
    """

    def __init__(self, snapshot_interval_ms: int = 1000):
        self.snapshot_interval_ms = snapshot_interval_ms
        self.states: Dict[str, SymbolState] = {}
        self.pending_features: List[OrderBookFeature] = []

    def _get_state(self, exchange: str, symbol: str) -> SymbolState:
        key = f"{exchange}:{symbol}"
        if key not in self.states:
            self.states[key] = SymbolState()
        return self.states[key]

    def process_snapshot(self, snapshot: OrderBookSnapshot) -> Optional[OrderBookFeature]:
        """处理订单簿快照，返回特征（1秒间隔）"""
        state = self._get_state(snapshot.exchange, snapshot.symbol)
        key = f"{snapshot.exchange}:{snapshot.symbol}"
        
        current_second = snapshot.timestamp // self.snapshot_interval_ms
        
        if state.last_second_timestamp == 0:
            state.last_second_timestamp = current_second
            state.last_snapshot = snapshot
            return None
        
        if current_second == state.last_second_timestamp:
            state.last_snapshot = snapshot
            return None
        
        feature = self._generate_feature(state, snapshot)
        
        state.last_snapshot = snapshot
        state.last_feature = feature
        state.last_second_timestamp = current_second
        
        TradeFlowCalculator.reset_second_delta(state)
        
        state.prev_top5_depth = (
            sum(b.quantity for b in snapshot.bids[:5]) +
            sum(a.quantity for a in snapshot.asks[:5])
        )
        
        return feature

    def _generate_feature(
        self, 
        state: SymbolState, 
        snapshot: OrderBookSnapshot
    ) -> OrderBookFeature:
        """生成特征"""
        state.spread_history.append(snapshot.get_spread())
        state.imbalance_history.append(snapshot.get_imbalance(10))
        
        spread_volatility = 0.0
        if len(state.spread_history) >= 10:
            spreads = list(state.spread_history)[-10:]
            mean_spread = sum(spreads) / len(spreads)
            if mean_spread > 0:
                variance = sum((s - mean_spread) ** 2 for s in spreads) / len(spreads)
                spread_volatility = (variance ** 0.5) / mean_spread
        
        current_imbalance = snapshot.get_imbalance(10)
        current_sign = 1 if current_imbalance > 0 else (-1 if current_imbalance < 0 else 0)
        if state.last_imbalance_sign != 0 and current_sign != 0 and current_sign != state.last_imbalance_sign:
            state.book_flips += 1
        state.last_imbalance_sign = current_sign
        
        feature = OrderBookFeature.from_snapshot(
            snapshot=snapshot,
            trade_flow=state.trade_flow,
            sweep=state.sweep,
            prev_feature=state.last_feature
        )
        
        feature.spread_volatility = spread_volatility
        feature.book_flip_rate = state.book_flips / max(len(state.imbalance_history), 1)
        
        return feature

    def process_trade(self, trade: TradeEvent) -> None:
        """处理交易事件，更新交易流状态"""
        state = self._get_state(trade.exchange, trade.symbol)
        
        if state.last_snapshot:
            best_bid = state.last_snapshot.bids[0].price if state.last_snapshot.bids else 0
            best_ask = state.last_snapshot.asks[0].price if state.last_snapshot.asks else 0
            
            TradeFlowCalculator.update_trade_flow(state, trade, best_bid, best_ask)
            
            state.trades_in_second.append(trade)
            
            if len(state.trades_in_second) >= 10:
                SweepDetector.detect_sweep(state, state.last_snapshot, state.trades_in_second)
                state.trades_in_second = []

    def get_last_feature(self, exchange: str, symbol: str) -> Optional[OrderBookFeature]:
        """获取最新的订单簿特征"""
        state = self._get_state(exchange, symbol)
        return state.last_feature

    def get_state(self, exchange: str, symbol: str) -> Optional[SymbolState]:
        """获取交易对状态"""
        return self._get_state(exchange, symbol)


_aggregator: Optional[OrderBookAggregator] = None


def get_orderbook_aggregator() -> OrderBookAggregator:
    """获取全局订单簿聚合器"""
    global _aggregator
    if _aggregator is None:
        _aggregator = OrderBookAggregator()
    return _aggregator
