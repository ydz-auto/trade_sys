"""
MarketContext Schema - 固定结构定义

核心设计原则：
1. 固定周期：1m/5m/15m/1h/4h
2. 分层结构：TimeframeContext + 跨周期上下文
3. 策略只读，不修改
4. 保留标准化数值，不只有结论标签
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Optional, Tuple


# ============== 基础枚举类型 ==============

class TrendState(Enum):
    STRONG_UP = auto()
    WEAK_UP = auto()
    SIDEWAYS = auto()
    WEAK_DOWN = auto()
    STRONG_DOWN = auto()


class MomentumDirection(Enum):
    BUY = auto()
    SELL = auto()
    NEUTRAL = auto()


class VolatilityState(Enum):
    LOW = auto()
    NORMAL = auto()
    ELEVATED = auto()
    EXTREME = auto()


class VolumeState(Enum):
    DRY = auto()
    NORMAL = auto()
    CLIMAX = auto()


class FlowPressure(Enum):
    BUY = auto()
    SELL = auto()
    NEUTRAL = auto()


class LiquidityState(Enum):
    NORMAL = auto()
    THIN = auto()
    VACUUM = auto()
    FLOODED = auto()


class FundingBias(Enum):
    EXTREME_POSITIVE = auto()
    POSITIVE = auto()
    NEUTRAL = auto()
    NEGATIVE = auto()
    EXTREME_NEGATIVE = auto()


# ============== 时间周期上下文 ==============

@dataclass(frozen=True)
class PriceState:
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    
    # 收益
    return_1h: float = 0.0
    return_24h: float = 0.0
    
    # 价格变化
    change: float = 0.0
    change_percent: float = 0.0
    
    # 价格序列
    closes: Tuple[float, ...] = ()
    highs: Tuple[float, ...] = ()
    lows: Tuple[float, ...] = ()
    
    # 支撑阻力
    support: Optional[float] = None
    resistance: Optional[float] = None


@dataclass(frozen=True)
class TrendStateData:
    state: TrendState = TrendState.SIDEWAYS
    ema_20: float = 0.0
    ema_50: float = 0.0
    slope: float = 0.0  # 趋势斜率
    structure: str = "unknown"  # higher_highs, lower_lows, etc.
    strength: float = 0.0  # 0 ~ 1


@dataclass(frozen=True)
class MomentumState:
    direction: MomentumDirection = MomentumDirection.NEUTRAL
    score: float = 0.0  # -1 ~ +1
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0


@dataclass(frozen=True)
class VolatilityStateData:
    state: VolatilityState = VolatilityState.NORMAL
    atr: float = 0.0
    atr_pct: float = 0.0  # ATR / Price
    bb_width: float = 0.0
    bb_width_pct: float = 0.0
    realized_vol: float = 0.0
    realized_vol_zscore: float = 0.0


@dataclass(frozen=True)
class VolumeStateData:
    state: VolumeState = VolumeState.NORMAL
    volume: float = 0.0
    volume_ma: float = 0.0
    volume_zscore: float = 0.0
    volume_ratio: float = 1.0


@dataclass(frozen=True)
class FlowState:
    pressure: FlowPressure = FlowPressure.NEUTRAL
    score: float = 0.0  # -1 ~ +1
    
    # CVD
    cvd: float = 0.0
    cvd_slope: float = 0.0
    cumulative_delta: float = 0.0
    
    # 主动交易
    aggressive_buy: float = 0.0
    aggressive_sell: float = 0.0
    aggressive_ratio: float = 1.0
    
    # 大单
    whale_buy_count: int = 0
    whale_sell_count: int = 0
    whale_buy_volume: float = 0.0
    whale_sell_volume: float = 0.0
    
    # 不平衡
    imbalance_5: float = 0.0


@dataclass(frozen=True)
class LiquidityStateData:
    state: LiquidityState = LiquidityState.NORMAL
    spread: float = 0.0
    spread_bps: float = 0.0  # 基点
    
    # 深度
    depth_ratio: float = 1.0
    top5_bid_depth: float = 0.0
    top5_ask_depth: float = 0.0
    
    # 微观价格
    microprice: float = 0.0
    
    # 真空检测
    is_vacuum: bool = False
    vacuum_score: float = 0.0
    
    # 撤单率
    cancel_rate: float = 0.0


@dataclass(frozen=True)
class TimeframeContext:
    timeframe: str  # "1m", "5m", "15m", "1h", "4h"
    
    price: PriceState = field(default_factory=PriceState)
    trend: TrendStateData = field(default_factory=TrendStateData)
    momentum: MomentumState = field(default_factory=MomentumState)
    volatility: VolatilityStateData = field(default_factory=VolatilityStateData)
    volume: VolumeStateData = field(default_factory=VolumeStateData)
    flow: FlowState = field(default_factory=FlowState)
    liquidity: LiquidityStateData = field(default_factory=LiquidityStateData)


# ============== 跨周期上下文 ==============

@dataclass(frozen=True)
class OIData:
    value: float = 0.0
    delta: float = 0.0
    zscore: float = 0.0
    history: Tuple[float, ...] = ()
    trend: str = "neutral"  # rising, falling, spike


@dataclass(frozen=True)
class FundingData:
    rate: float = 0.0
    zscore: float = 0.0
    bias: FundingBias = FundingBias.NEUTRAL
    history: Tuple[float, ...] = ()


@dataclass(frozen=True)
class LiquidationData:
    long: float = 0.0
    short: float = 0.0
    total: float = 0.0
    long_zscore: float = 0.0
    short_zscore: float = 0.0
    reversal_signal: bool = False


@dataclass(frozen=True)
class DerivativesContext:
    oi: OIData = field(default_factory=OIData)
    funding: FundingData = field(default_factory=FundingData)
    liquidation: LiquidationData = field(default_factory=LiquidationData)


@dataclass(frozen=True)
class CrossMarketData:
    binance_return: float = 0.0
    okx_return: float = 0.0
    bybit_return: float = 0.0
    
    basis: float = 0.0
    premium: float = 0.0
    spread: float = 0.0
    
    lead_exchange: str = ""
    lag_exchange: str = ""
    lead_lag_score: float = 0.0


@dataclass(frozen=True)
class RiskContext:
    high_volatility: bool = False
    low_liquidity: bool = False
    news_event: bool = False
    overtrading: bool = False
    drawdown_exceeded: bool = False
    slippage_warning: bool = False
    execution_paused: bool = False
    regime_change: bool = False
    extreme_move: bool = False
    
    # 风险乘数（由 4h 决定）
    multiplier: float = 1.0


# ============== 主上下文 ==============

STANDARD_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"]


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    timestamp: int  # 毫秒时间戳
    
    # 时间周期上下文（核心）
    tf: Dict[str, TimeframeContext] = field(default_factory=dict)
    
    # 跨周期上下文
    derivatives: DerivativesContext = field(default_factory=DerivativesContext)
    cross_market: CrossMarketData = field(default_factory=CrossMarketData)
    risk: RiskContext = field(default_factory=RiskContext)
    
    # ============== 快捷方法 ==============
    
    def tf_1m(self) -> TimeframeContext:
        return self.tf.get("1m", TimeframeContext(timeframe="1m"))
    
    def tf_5m(self) -> TimeframeContext:
        return self.tf.get("5m", TimeframeContext(timeframe="5m"))
    
    def tf_15m(self) -> TimeframeContext:
        return self.tf.get("15m", TimeframeContext(timeframe="15m"))
    
    def tf_1h(self) -> TimeframeContext:
        return self.tf.get("1h", TimeframeContext(timeframe="1h"))
    
    def tf_4h(self) -> TimeframeContext:
        return self.tf.get("4h", TimeframeContext(timeframe="4h"))
    
    def calculate_signal_confidence(
        self,
        base_confidence: float,
        primary_tf: str = "15m",
    ) -> float:
        """
        计算最终信号置信度
        
        规则：大周期定方向，中周期给信号，小周期找入场
        final_confidence = base * risk_multiplier_4h * trend_filter_1h * confirmation_5m * execution_quality_1m
        """
        # 4h 风险乘数
        risk_multiplier = self.risk.multiplier
        
        # 1h 趋势过滤
        h1 = self.tf_1h()
        trend_filter = 1.0
        if h1.trend.state == TrendState.SIDEWAYS:
            trend_filter = 0.8
        
        # 5m 确认
        m5 = self.tf_5m()
        confirmation = 1.0
        if primary_tf == "15m":
            if m5.flow.pressure == FlowPressure.NEUTRAL:
                confirmation = 0.7
            else:
                confirmation = 1.2
        
        # 1m 执行质量
        m1 = self.tf_1m()
        execution_quality = 1.0
        if m1.liquidity.state == LiquidityState.VACUUM:
            execution_quality = 0.6
        
        # 综合计算
        final = base_confidence * risk_multiplier * trend_filter * confirmation * execution_quality
        return max(0.0, min(1.0, final))


# ============== 导出接口 ==============

__all__ = [
    # 枚举类型
    "TrendState",
    "MomentumDirection",
    "VolatilityState",
    "VolumeState",
    "FlowPressure",
    "LiquidityState",
    "FundingBias",
    
    # 状态类
    "PriceState",
    "TrendStateData",
    "MomentumState",
    "VolatilityStateData",
    "VolumeStateData",
    "FlowState",
    "LiquidityStateData",
    "TimeframeContext",
    
    # 跨周期上下文
    "OIData",
    "FundingData",
    "LiquidationData",
    "DerivativesContext",
    "CrossMarketData",
    "RiskContext",
    
    # 主上下文
    "STANDARD_TIMEFRAMES",
    "MarketContext",
]
