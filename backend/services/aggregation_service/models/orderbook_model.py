"""
OrderBook Model - 订单簿数据模型

70G硬盘优化版：只存高价值特征，不存全量盘口
适合：50x行为策略 / 爆仓结构 / 微观行为
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class OrderBookLevel:
    """订单簿级别"""
    price: float
    quantity: float


@dataclass
class OrderBookSnapshot:
    """订单簿快照"""
    exchange: str
    symbol: str
    timestamp: int

    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    last_update_id: int = 0

    def get_mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2

    def get_spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price

    def get_spread_pct(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        mid = self.get_mid_price()
        if mid == 0:
            return 0.0
        return (self.asks[0].price - self.bids[0].price) / mid

    def get_microprice(self) -> float:
        """Microprice: 考虑流动性的价格
        买盘越大 -> 偏向买方 -> 价格更低
        卖盘越大 -> 偏向卖方 -> 价格更高
        """
        if not self.bids or not self.asks:
            return 0.0
        bid_vol = self.bids[0].quantity
        ask_vol = self.asks[0].quantity
        if bid_vol + ask_vol == 0:
            return self.get_mid_price()
        return (self.bids[0].price * bid_vol + self.asks[0].price * ask_vol) / (bid_vol + ask_vol)

    def get_bid_volume(self, depth: int = 10) -> float:
        return sum(b.quantity for b in self.bids[:depth])

    def get_ask_volume(self, depth: int = 10) -> float:
        return sum(a.quantity for a in self.asks[:depth])

    def get_imbalance(self, depth: int = 10) -> float:
        bid_vol = self.get_bid_volume(depth)
        ask_vol = self.get_ask_volume(depth)
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total

    def get_depth_ratio(self, depth: int = 10) -> float:
        bid_vol = self.get_bid_volume(depth)
        ask_vol = self.get_ask_volume(depth)
        if ask_vol == 0:
            return float('inf') if bid_vol > 0 else 0.0
        return bid_vol / ask_vol

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "bids": [(b.price, b.quantity) for b in self.bids],
            "asks": [(a.price, a.quantity) for a in self.asks],
            "last_update_id": self.last_update_id,
        }


@dataclass
class TradeFlowState:
    """交易流状态（需要累积）"""
    trade_delta: float = 0.0
    cumulative_delta: float = 0.0
    aggressive_buy_volume: float = 0.0
    aggressive_sell_volume: float = 0.0
    large_trade_count: int = 0
    total_trade_count: int = 0
    trade_velocity: float = 0.0
    last_trade_timestamp: int = 0
    
    # 新增Trade特征
    total_volume: float = 0.0
    total_value: float = 0.0
    avg_trade_size: float = 0.0
    buy_sell_ratio: float = 0.0
    trade_intensity: float = 0.0
    vwap: float = 0.0
    max_trade_size: float = 0.0
    min_trade_size: float = float('inf')
    price_impact: float = 0.0


@dataclass
class SweepState:
    """扫单状态"""
    sweep_buy_score: float = 0.0
    sweep_sell_score: float = 0.0
    multi_level_fill: int = 0
    liquidity_vacuum: float = 0.0


@dataclass
class OrderBookFeature:
    """订单簿特征（70G优化版 - 高价值特征集合）
    
    包含：
    - Top-of-Book / 流动性 Feature
    - Imbalance（最重要）
    - Depth Feature
    - Trade Flow（极其重要）
    - Sweep / 流动性冲击
    - 波动 / 流动性恶化
    """
    exchange: str
    symbol: str
    timestamp: int

    spread: float
    spread_pct: float
    mid_price: float
    microprice: float
    best_bid_size: float
    best_ask_size: float

    imbalance_1: float
    imbalance_5: float
    imbalance_10: float

    top5_bid_volume: float
    top5_ask_volume: float
    top10_bid_volume: float
    top10_ask_volume: float
    depth_ratio: float

    trade_delta: float
    cumulative_delta: float
    aggressive_buy_volume: float
    aggressive_sell_volume: float
    large_trade_ratio: float
    trade_velocity: float
    total_volume: float
    total_value: float
    avg_trade_size: float
    buy_sell_ratio: float
    trade_intensity: float
    vwap: float
    max_trade_size: float
    min_trade_size: float
    price_impact: float

    sweep_buy_score: float
    sweep_sell_score: float
    multi_level_fill: int
    liquidity_vacuum: float

    book_pressure: float

    imbalance_slope: float = 0.0
    depth_change: float = 0.0
    quote_update_rate: float = 0.0
    cancel_rate: float = 0.0
    book_flip_rate: float = 0.0
    spread_volatility: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "mid_price": self.mid_price,
            "microprice": self.microprice,
            "best_bid_size": self.best_bid_size,
            "best_ask_size": self.best_ask_size,
            "imbalance_1": self.imbalance_1,
            "imbalance_5": self.imbalance_5,
            "imbalance_10": self.imbalance_10,
            "imbalance_slope": self.imbalance_slope,
            "top5_bid_volume": self.top5_bid_volume,
            "top5_ask_volume": self.top5_ask_volume,
            "top10_bid_volume": self.top10_bid_volume,
            "top10_ask_volume": self.top10_ask_volume,
            "depth_ratio": self.depth_ratio,
            "depth_change": self.depth_change,
            "trade_delta": self.trade_delta,
            "cumulative_delta": self.cumulative_delta,
            "aggressive_buy_volume": self.aggressive_buy_volume,
            "aggressive_sell_volume": self.aggressive_sell_volume,
            "large_trade_ratio": self.large_trade_ratio,
            "trade_velocity": self.trade_velocity,
            "total_volume": self.total_volume,
            "total_value": self.total_value,
            "avg_trade_size": self.avg_trade_size,
            "buy_sell_ratio": self.buy_sell_ratio,
            "trade_intensity": self.trade_intensity,
            "vwap": self.vwap,
            "max_trade_size": self.max_trade_size,
            "min_trade_size": self.min_trade_size,
            "price_impact": self.price_impact,
            "sweep_buy_score": self.sweep_buy_score,
            "sweep_sell_score": self.sweep_sell_score,
            "multi_level_fill": self.multi_level_fill,
            "liquidity_vacuum": self.liquidity_vacuum,
            "spread_volatility": self.spread_volatility,
            "quote_update_rate": self.quote_update_rate,
            "cancel_rate": self.cancel_rate,
            "book_flip_rate": self.book_flip_rate,
            "book_pressure": self.book_pressure,
        }

    def to_parquet_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["datetime"] = datetime.fromtimestamp(self.timestamp / 1000)
        return d

    @classmethod
    def from_snapshot(
        cls, 
        snapshot: OrderBookSnapshot,
        trade_flow: Optional[TradeFlowState] = None,
        sweep: Optional[SweepState] = None,
        prev_feature: Optional["OrderBookFeature"] = None
    ) -> "OrderBookFeature":
        """从快照计算特征"""
        top5_bid = snapshot.get_bid_volume(5)
        top5_ask = snapshot.get_ask_volume(5)
        top10_bid = snapshot.get_bid_volume(10)
        top10_ask = snapshot.get_ask_volume(10)

        imbalance_1 = snapshot.get_imbalance(1)
        imbalance_5 = snapshot.get_imbalance(5)
        imbalance_10 = snapshot.get_imbalance(10)

        imbalance_slope = 0.0
        if prev_feature:
            imbalance_slope = imbalance_10 - prev_feature.imbalance_10

            depth_change = 0.0
            prev_depth = prev_feature.top5_bid_volume + prev_feature.top5_ask_volume
            curr_depth = top5_bid + top5_ask
            if prev_depth > 0:
                depth_change = (curr_depth - prev_depth) / prev_depth
        else:
            depth_change = 0.0

        book_pressure = imbalance_10 * (top10_bid + top10_ask)

        feature = cls(
            exchange=snapshot.exchange,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            spread=snapshot.get_spread(),
            spread_pct=snapshot.get_spread_pct(),
            mid_price=snapshot.get_mid_price(),
            microprice=snapshot.get_microprice(),
            best_bid_size=snapshot.bids[0].quantity if snapshot.bids else 0.0,
            best_ask_size=snapshot.asks[0].quantity if snapshot.asks else 0.0,
            imbalance_1=imbalance_1,
            imbalance_5=imbalance_5,
            imbalance_10=imbalance_10,
            top5_bid_volume=top5_bid,
            top5_ask_volume=top5_ask,
            top10_bid_volume=top10_bid,
            top10_ask_volume=top10_ask,
            depth_ratio=snapshot.get_depth_ratio(10),
            trade_delta=trade_flow.trade_delta if trade_flow else 0.0,
            cumulative_delta=trade_flow.cumulative_delta if trade_flow else 0.0,
            aggressive_buy_volume=trade_flow.aggressive_buy_volume if trade_flow else 0.0,
            aggressive_sell_volume=trade_flow.aggressive_sell_volume if trade_flow else 0.0,
            large_trade_ratio=(
                trade_flow.large_trade_count / trade_flow.total_trade_count
                if trade_flow and trade_flow.total_trade_count > 0 else 0.0
            ),
            trade_velocity=trade_flow.trade_velocity if trade_flow else 0.0,
            total_volume=trade_flow.total_volume if trade_flow else 0.0,
            total_value=trade_flow.total_value if trade_flow else 0.0,
            avg_trade_size=trade_flow.avg_trade_size if trade_flow else 0.0,
            buy_sell_ratio=trade_flow.buy_sell_ratio if trade_flow else 0.0,
            trade_intensity=trade_flow.trade_intensity if trade_flow else 0.0,
            vwap=trade_flow.vwap if trade_flow else 0.0,
            max_trade_size=trade_flow.max_trade_size if trade_flow else 0.0,
            min_trade_size=trade_flow.min_trade_size if trade_flow else 0.0,
            price_impact=trade_flow.price_impact if trade_flow else 0.0,
            sweep_buy_score=sweep.sweep_buy_score if sweep else 0.0,
            sweep_sell_score=sweep.sweep_sell_score if sweep else 0.0,
            multi_level_fill=sweep.multi_level_fill if sweep else 0,
            liquidity_vacuum=sweep.liquidity_vacuum if sweep else 0.0,
            spread_volatility=0.0,
            book_pressure=book_pressure,
            imbalance_slope=imbalance_slope,
            depth_change=depth_change,
            quote_update_rate=0.0,
            cancel_rate=0.0,
            book_flip_rate=0.0,
        )

        return feature


@dataclass
class TradeEvent:
    """交易事件"""
    exchange: str
    symbol: str
    timestamp: int
    trade_id: str
    price: float
    quantity: float
    side: str
    is_buyer_maker: bool = False

    def is_aggressive_buy(self, best_ask: float) -> bool:
        return not self.is_buyer_maker

    def is_aggressive_sell(self, best_bid: float) -> bool:
        return self.is_buyer_maker


@dataclass
class OrderBookFeatureSnapshot:
    """1秒特征快照（用于Parquet存储）"""
    timestamp: int
    datetime: datetime
    exchange: str
    symbol: str

    best_bid: float
    best_ask: float
    spread: float
    spread_pct: float
    mid_price: float
    microprice: float

    imbalance_1: float
    imbalance_5: float
    imbalance_10: float

    top5_bid_volume: float
    top5_ask_volume: float
    top10_bid_volume: float
    top10_ask_volume: float
    depth_ratio: float

    trade_delta: float
    cumulative_delta: float

    sweep_buy_score: float
    sweep_sell_score: float

    spread_volatility: float
    book_pressure: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "datetime": self.datetime,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "mid_price": self.mid_price,
            "microprice": self.microprice,
            "imbalance_1": self.imbalance_1,
            "imbalance_5": self.imbalance_5,
            "imbalance_10": self.imbalance_10,
            "top5_bid_volume": self.top5_bid_volume,
            "top5_ask_volume": self.top5_ask_volume,
            "top10_bid_volume": self.top10_bid_volume,
            "top10_ask_volume": self.top10_ask_volume,
            "depth_ratio": self.depth_ratio,
            "trade_delta": self.trade_delta,
            "cumulative_delta": self.cumulative_delta,
            "sweep_buy_score": self.sweep_buy_score,
            "sweep_sell_score": self.sweep_sell_score,
            "spread_volatility": self.spread_volatility,
            "book_pressure": self.book_pressure,
        }
