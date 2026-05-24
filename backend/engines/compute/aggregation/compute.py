from typing import Dict, Optional, List, Deque, Tuple, Any
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field

from infrastructure.logging import get_logger
from domain.event.base_event import Exchange, Timeframe, Candle, Trade

logger = get_logger("engines.compute.aggregation")


@dataclass
class CandleWindow:
    exchange: Exchange
    symbol: str
    timeframe: Timeframe
    bucket: int
    open: float = 0.0
    high: float = float("-inf")
    low: float = float("inf")
    close: float = 0.0
    volume: float = 0.0
    quote_volume: float = 0.0
    trade_count: int = 0
    first_trade_time: int = 0
    last_trade_time: int = 0
    is_closed: bool = False
    trades: list = field(default_factory=list)

    def update(self, price: float, quantity: float, quote: float, trade_time: int):
        if self.first_trade_time == 0:
            self.first_trade_time = trade_time
            self.open = price
            self.high = price
            self.low = price
        self.last_trade_time = trade_time
        self.close = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.volume += quantity
        self.quote_volume += quote
        self.trade_count += 1

    def reset(self):
        self.open = 0.0
        self.high = float("-inf")
        self.low = float("inf")
        self.close = 0.0
        self.volume = 0.0
        self.quote_volume = 0.0
        self.trade_count = 0
        self.first_trade_time = 0
        self.last_trade_time = 0
        self.is_closed = False
        self.trades = []


@dataclass
class OrderBookLevel:
    price: float
    quantity: float


@dataclass
class OrderBookSnapshot:
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
    trade_delta: float = 0.0
    cumulative_delta: float = 0.0
    aggressive_buy_volume: float = 0.0
    aggressive_sell_volume: float = 0.0
    large_trade_count: int = 0
    total_trade_count: int = 0
    trade_velocity: float = 0.0
    last_trade_timestamp: int = 0
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
    sweep_buy_score: float = 0.0
    sweep_sell_score: float = 0.0
    multi_level_fill: int = 0
    liquidity_vacuum: float = 0.0


@dataclass
class OrderBookFeature:
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
        top5_bid = snapshot.get_bid_volume(5)
        top5_ask = snapshot.get_ask_volume(5)
        top10_bid = snapshot.get_bid_volume(10)
        top10_ask = snapshot.get_ask_volume(10)
        imbalance_1 = snapshot.get_imbalance(1)
        imbalance_5 = snapshot.get_imbalance(5)
        imbalance_10 = snapshot.get_imbalance(10)
        imbalance_slope = 0.0
        depth_change = 0.0
        if prev_feature:
            imbalance_slope = imbalance_10 - prev_feature.imbalance_10
            prev_depth = prev_feature.top5_bid_volume + prev_feature.top5_ask_volume
            curr_depth = top5_bid + top5_ask
            if prev_depth > 0:
                depth_change = (curr_depth - prev_depth) / prev_depth
        book_pressure = imbalance_10 * (top10_bid + top10_ask)
        return cls(
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


@dataclass
class TradeEvent:
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


@dataclass
class SymbolState:
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


def compute_target_timeframes(source_tf: Timeframe) -> list[Timeframe]:
    mapping = {
        Timeframe.M1: [Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1],
    }
    return mapping.get(source_tf, [])


def compute_bucket(open_time_ms: int, target_tf_seconds: int) -> int:
    bucket_size = target_tf_seconds * 1000
    return (open_time_ms // bucket_size) * bucket_size


def build_candle_from_window(window: CandleWindow) -> Candle:
    return Candle(
        exchange=window.exchange,
        symbol=window.symbol,
        timeframe=window.timeframe,
        open_time=window.bucket,
        close_time=window.bucket + window.timeframe.seconds * 1000 - 1,
        open=window.open,
        high=window.high if window.high != float("-inf") else window.open,
        low=window.low if window.low != float("inf") else window.open,
        close=window.close,
        volume=window.volume,
        quote_volume=window.quote_volume,
        trade_count=window.trade_count,
        is_closed=True,
        source="aggregated",
        event_time=int(datetime.now().timestamp() * 1000),
    )


def apply_candle_to_window(window: CandleWindow, source: Candle, target_tf: Timeframe) -> Optional[Candle]:
    bucket_size = target_tf.seconds * 1000
    target_bucket = compute_bucket(source.open_time, target_tf.seconds)

    if window.bucket == 0:
        window.bucket = target_bucket
        window.open = source.open
        window.high = source.high
        window.low = source.low
        window.close = source.close
        window.volume = source.volume
        window.quote_volume = source.quote_volume
        window.trade_count = source.trade_count
        return None

    if source.open_time < window.bucket:
        logger.warning(f"Out of order candle: {source.open_time} < {window.bucket}")
        return None

    if source.open_time >= window.bucket + bucket_size:
        closed_candle = build_candle_from_window(window)
        window.reset()
        window.bucket = target_bucket
        window.open = source.open
        window.high = source.high
        window.low = source.low
        window.close = source.close
        window.volume = source.volume
        window.quote_volume = source.quote_volume
        window.trade_count = source.trade_count
        return closed_candle

    window.high = max(window.high, source.high)
    window.low = min(window.low, source.low)
    window.close = source.close
    window.volume += source.volume
    window.quote_volume += source.quote_volume
    window.trade_count += source.trade_count
    return None


def build_candle_from_trade_window(window: CandleWindow) -> Candle:
    return Candle(
        exchange=window.exchange,
        symbol=window.symbol,
        timeframe=Timeframe.S1,
        open_time=window.bucket,
        close_time=window.bucket + 999,
        open=window.open,
        high=window.high,
        low=window.low,
        close=window.close,
        volume=window.volume,
        quote_volume=window.quote_volume,
        trade_count=window.trade_count,
        is_closed=True,
        source="aggregated",
        event_time=int(datetime.now().timestamp() * 1000),
    )


def apply_trade_to_window(window: CandleWindow, trade: Trade) -> Optional[Candle]:
    bucket_size = 1000
    trade_bucket = (trade.timestamp // bucket_size) * bucket_size

    if window.bucket == 0:
        window.bucket = trade_bucket
        window.open = trade.price
        window.high = trade.price
        window.low = trade.price
        window.close = trade.price
        window.volume = trade.quantity
        window.quote_volume = trade.quote_quantity
        window.trade_count = 1
        window.trades = [trade]
        return None

    if trade_bucket < window.bucket:
        logger.warning(f"Out of order trade: {trade.timestamp} < {window.bucket}")
        return None

    if trade_bucket > window.bucket:
        closed_candle = build_candle_from_trade_window(window)
        window.reset()
        window.bucket = trade_bucket
        window.open = trade.price
        window.high = trade.price
        window.low = trade.price
        window.close = trade.price
        window.volume = trade.quantity
        window.quote_volume = trade.quote_quantity
        window.trade_count = 1
        window.trades = [trade]
        return closed_candle

    window.high = max(window.high, trade.price)
    window.low = min(window.low, trade.price)
    window.close = trade.price
    window.volume += trade.quantity
    window.quote_volume += trade.quote_quantity
    window.trade_count += 1
    window.trades.append(trade)
    return None


LARGE_TRADE_THRESHOLD_USD = 10000


def update_trade_flow(state: SymbolState, trade: TradeEvent, best_bid: float, best_ask: float) -> None:
    if trade.is_buyer_maker:
        state.trade_flow.aggressive_sell_volume += trade.quantity
        state.trade_flow.trade_delta -= trade.quantity
    else:
        state.trade_flow.aggressive_buy_volume += trade.quantity
        state.trade_flow.trade_delta += trade.quantity

    state.trade_flow.cumulative_delta += state.trade_flow.trade_delta
    state.trade_flow.total_trade_count += 1

    trade_value = trade.price * trade.quantity
    state.trade_flow.total_volume += trade.quantity
    state.trade_flow.total_value += trade_value

    state.trade_flow.avg_trade_size = (
        state.trade_flow.total_volume / state.trade_flow.total_trade_count
        if state.trade_flow.total_trade_count > 0 else 0.0
    )

    total_buy = state.trade_flow.aggressive_buy_volume
    total_sell = state.trade_flow.aggressive_sell_volume
    if total_sell > 0:
        state.trade_flow.buy_sell_ratio = total_buy / total_sell
    elif total_buy > 0:
        state.trade_flow.buy_sell_ratio = float('inf')
    else:
        state.trade_flow.buy_sell_ratio = 1.0

    if state.trade_flow.total_volume > 0:
        state.trade_flow.vwap = state.trade_flow.total_value / state.trade_flow.total_volume

    if trade.quantity > state.trade_flow.max_trade_size:
        state.trade_flow.max_trade_size = trade.quantity
    if trade.quantity < state.trade_flow.min_trade_size:
        state.trade_flow.min_trade_size = trade.quantity

    if trade_value >= LARGE_TRADE_THRESHOLD_USD:
        state.trade_flow.large_trade_count += 1

    if state.trade_flow.last_trade_timestamp > 0:
        time_diff = (trade.timestamp - state.trade_flow.last_trade_timestamp) / 1000.0
        if time_diff > 0:
            state.trade_flow.trade_velocity = 1.0 / time_diff
            state.trade_flow.trade_intensity = trade.quantity / time_diff

    if best_bid > 0 and best_ask > 0:
        mid_price = (best_bid + best_ask) / 2
        if mid_price > 0:
            state.trade_flow.price_impact = abs(trade.price - mid_price) / mid_price

    state.trade_flow.last_trade_timestamp = trade.timestamp


def reset_trade_flow_second_delta(state: SymbolState) -> None:
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


SWEEP_THRESHOLD_LEVELS = 3


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

    if buy_levels_consumed >= SWEEP_THRESHOLD_LEVELS:
        sweep.sweep_buy_score = min(buy_levels_consumed / 10.0, 1.0) * total_buy_volume
        sweep.multi_level_fill = buy_levels_consumed

    if sell_levels_consumed >= SWEEP_THRESHOLD_LEVELS:
        sweep.sweep_sell_score = min(sell_levels_consumed / 10.0, 1.0) * total_sell_volume
        sweep.multi_level_fill = max(sweep.multi_level_fill, sell_levels_consumed)

    top5_ask_vol = sum(a.quantity for a in snapshot.asks[:5])
    if top5_ask_vol < state.prev_top5_depth * 0.3:
        sweep.liquidity_vacuum = (state.prev_top5_depth - top5_ask_vol) / state.prev_top5_depth if state.prev_top5_depth > 0 else 0

    state.sweep = sweep
    return sweep


def compute_orderbook_feature(state: SymbolState, snapshot: OrderBookSnapshot) -> OrderBookFeature:
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
