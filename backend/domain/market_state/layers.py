"""
Market Context Layers - 分层上下文定义

按照用户定义的固定 schema 实现：
- TimeframeContext: 每个时间周期的上下文
- RegimeContext: 市场状态
- PriceContext: 价格信息
- VolatilityContext: 波动率状态
- LiquidityContext: 流动性状态
- FlowContext: 资金流状态
- DerivativesContext: 衍生品数据
- CrossMarketContext: 跨市场数据
- RiskFlags: 风险标志
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Optional, Tuple


# ============== 基础枚举类型 ==============

class TrendState(Enum):
    UP = auto()
    DOWN = auto()
    RANGE = auto()


class MomentumDirection(Enum):
    BUY = auto()
    SELL = auto()
    NEUTRAL = auto()


class VolatilityState(Enum):
    COMPRESSED = auto()
    NORMAL = auto()
    EXPANDED = auto()


class VolumeState(Enum):
    DRY = auto()
    NORMAL = auto()
    CLIMAX = auto()


class FlowPressure(Enum):
    BUY = auto()
    SELL = auto()
    NEUTRAL = auto()


class LiquidityLevel(Enum):
    NORMAL = auto()
    THIN = auto()
    VACUUM = auto()


# ============== 分层 Context 类 ==============

@dataclass(frozen=True)
class TimeframeContext:
    """
    单个时间周期的上下文
    
    固定包含：趋势、动量、波动率、成交量、资金流、流动性、支撑阻力
    """
    timeframe: str  # "1m", "5m", "15m", "1h", "4h"
    
    # 趋势状态
    trend_state: TrendState = TrendState.RANGE
    momentum_score: float = 0.0  # -1 ~ +1
    momentum_direction: MomentumDirection = MomentumDirection.NEUTRAL
    
    # 波动率状态
    volatility_state: VolatilityState = VolatilityState.NORMAL
    volatility_value: float = 0.0
    
    # 成交量状态
    volume_state: VolumeState = VolumeState.NORMAL
    volume_ratio: float = 1.0
    
    # 资金流状态
    flow_pressure: FlowPressure = FlowPressure.NEUTRAL
    flow_score: float = 0.0  # -1 ~ +1
    aggressive_flow: float = 0.0
    cvd_value: float = 0.0
    
    # 流动性状态
    liquidity_state: LiquidityLevel = LiquidityLevel.NORMAL
    spread: float = 0.0
    microprice: float = 0.0
    sweep_score: float = 0.0
    liquidity_vacuum: bool = False
    
    # 支撑阻力
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    
    # 技术指标（作为参考，不直接用于决策）
    technical: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RegimeContext:
    """市场状态上下文"""
    state: str = "unknown"  # trending_up, trending_down, mean_reverting, breakout, quiet
    confidence: float = 0.0
    duration: int = 0  # 持续时间（秒）
    strength: float = 0.0  # 0 ~ 1


@dataclass(frozen=True)
class PriceContext:
    """价格上下文"""
    close: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    
    # 收益
    return_1h: float = 0.0
    return_4h: float = 0.0
    return_24h: float = 0.0
    
    # 价格变化
    price_change: float = 0.0
    price_change_percent: float = 0.0
    
    # 价格序列
    close_prices: Tuple[float, ...] = ()
    high_prices: Tuple[float, ...] = ()
    low_prices: Tuple[float, ...] = ()


@dataclass(frozen=True)
class VolatilityContext:
    """波动率上下文"""
    current: float = 0.0
    historical: float = 0.0
    implied: Optional[float] = None
    
    # 波动率状态
    state: VolatilityState = VolatilityState.NORMAL
    
    # 波动率比率
    realized_vol_ratio: float = 1.0
    implied_vol_ratio: float = 1.0


@dataclass(frozen=True)
class LiquidityContext:
    """流动性上下文"""
    state: LiquidityLevel = LiquidityLevel.NORMAL
    
    # 订单簿数据
    top_bid: float = 0.0
    top_ask: float = 0.0
    spread: float = 0.0
    spread_ratio: float = 0.0
    
    # 深度数据
    top5_bid_depth: float = 0.0
    top5_ask_depth: float = 0.0
    depth_ratio: float = 0.0
    
    # 微观价格
    microprice: float = 0.0
    
    # 撤单率
    cancel_rate: float = 0.0
    
    # 流动性真空
    is_vacuum: bool = False
    vacuum_score: float = 0.0


@dataclass(frozen=True)
class FlowContext:
    """资金流上下文"""
    pressure: FlowPressure = FlowPressure.NEUTRAL
    score: float = 0.0  # -1 ~ +1
    
    # 交易数据
    trade_delta: float = 0.0
    cumulative_delta: float = 0.0
    aggressive_buy_volume: float = 0.0
    aggressive_sell_volume: float = 0.0
    
    # CVD (Cumulative Volume Delta)
    cvd: float = 0.0
    cvd_history: Tuple[float, ...] = ()
    
    # 大单数据
    whale_buy_count: int = 0
    whale_sell_count: int = 0
    whale_buy_volume: float = 0.0
    whale_sell_volume: float = 0.0
    
    # 主动流
    aggressive_flow: float = 0.0
    sweep_score: float = 0.0
    
    # 不平衡
    imbalance_5: float = 0.0


@dataclass(frozen=True)
class DerivativesContext:
    """衍生品上下文"""
    # 持仓量
    oi: float = 0.0
    oi_delta: float = 0.0
    oi_zscore: float = 0.0
    oi_history: Tuple[float, ...] = ()
    
    # 资金费率
    funding_rate: float = 0.0
    funding_zscore: float = 0.0
    funding_history: Tuple[float, ...] = ()
    
    # OI与资金费率背离
    oi_funding_divergence: float = 0.0
    
    # 资金费率极端反转
    funding_extreme_reversal: bool = False
    funding_extreme_side: str = "none"  # long/short/none
    
    # 强平数据
    liquidation_long: float = 0.0
    liquidation_short: float = 0.0
    liquidation_total: float = 0.0
    liquidation_reversal_signal: bool = False


@dataclass(frozen=True)
class CrossMarketContext:
    """跨市场上下文"""
    # 其他交易所
    binance_return: float = 0.0
    okx_return: float = 0.0
    bybit_return: float = 0.0
    
    # 基差/溢价
    basis: float = 0.0
    premium: float = 0.0
    spread: float = 0.0
    
    # 领先滞后关系
    lead_exchange: str = ""
    lag_exchange: str = ""
    lead_lag_score: float = 0.0


@dataclass(frozen=True)
class RiskFlags:
    """风险标志"""
    # 基础风险
    high_volatility: bool = False
    low_liquidity: bool = False
    news_event: bool = False
    
    # 策略风险
    overtrading: bool = False
    drawdown_exceeded: bool = False
    correlation_risk: bool = False
    
    # 执行风险
    slippage_warning: bool = False
    execution_paused: bool = False
    
    # 市场风险
    regime_change: bool = False
    extreme_move: bool = False


# ============== 导出接口 ==============

__all__ = [
    # 枚举类型
    "TrendState",
    "MomentumDirection",
    "VolatilityState",
    "VolumeState",
    "FlowPressure",
    "LiquidityLevel",
    
    # Context 类
    "TimeframeContext",
    "RegimeContext",
    "PriceContext",
    "VolatilityContext",
    "LiquidityContext",
    "FlowContext",
    "DerivativesContext",
    "CrossMarketContext",
    "RiskFlags",
]
