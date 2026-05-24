"""
Strategy Registry - 策略注册中心

提供统一的策略加载接口，供 ReplayRuntime 使用。
"""

from typing import Dict, Any, Optional, Type, List
from dataclasses import dataclass, field
from infrastructure.logging import get_logger

logger = get_logger("strategy_registry")


@dataclass
class StrategyInfo:
    """策略信息"""
    strategy_id: str
    name: str
    description: str
    direction: str
    default_params: Dict[str, Any] = field(default_factory=dict)
    required_features: List[str] = field(default_factory=list)


class BaseStrategy:
    """策略基类"""

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """生成信号"""
        raise NotImplementedError


class RSIOversoldStrategy(BaseStrategy):
    """RSI 超卖策略"""

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rsi = features.get('rsi_14', 50)
        oversold = self.params.get('oversold', 30)

        if rsi < oversold:
            return {
                'signal_type': 'buy',
                'confidence': 1.0 - rsi / 100,
                'reason': f"RSI {rsi:.1f} < {oversold}"
            }
        return None


class RSIOverboughtStrategy(BaseStrategy):
    """RSI 超买策略"""

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rsi = features.get('rsi_14', 50)
        overbought = self.params.get('overbought', 70)

        if rsi > overbought:
            return {
                'signal_type': 'sell',
                'confidence': (rsi - 50) / 50,
                'reason': f"RSI {rsi:.1f} > {overbought}"
            }
        return None


class MACDCrossStrategy(BaseStrategy):
    """MACD 交叉策略"""

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        macd = features.get('macd', 0)
        signal = features.get('macd_signal', 0)

        if macd > signal and signal < 0:
            return {
                'signal_type': 'buy',
                'confidence': min(macd - signal, 1.0),
                'reason': "MACD 金叉"
            }
        elif macd < signal and signal > 0:
            return {
                'signal_type': 'sell',
                'confidence': min(signal - macd, 1.0),
                'reason': "MACD 死叉"
            }
        return None


class SMACrossStrategy(BaseStrategy):
    """SMA 交叉策略"""

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fast = self.params.get('fast', 10)
        slow = self.params.get('slow', 50)

        sma_fast = features.get(f'sma_{fast}')
        sma_slow = features.get(f'sma_{slow}')

        if sma_fast is None or sma_slow is None:
            return None

        if sma_fast > sma_slow:
            return {
                'signal_type': 'buy',
                'confidence': min((sma_fast - sma_slow) / sma_slow, 1.0),
                'reason': f"SMA{fast} 上穿 SMA{slow}"
            }
        elif sma_fast < sma_slow:
            return {
                'signal_type': 'sell',
                'confidence': min((sma_slow - sma_fast) / sma_slow, 1.0),
                'reason': f"SMA{fast} 下穿 SMA{slow}"
            }
        return None


class EMACrossStrategy(BaseStrategy):
    """EMA 交叉策略"""

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fast = self.params.get('fast', 10)
        slow = self.params.get('slow', 50)

        ema_fast = features.get(f'ema_{fast}')
        ema_slow = features.get(f'ema_{slow}')

        if ema_fast is None or ema_slow is None:
            return None

        if ema_fast > ema_slow:
            return {
                'signal_type': 'buy',
                'confidence': min((ema_fast - ema_slow) / ema_slow, 1.0),
                'reason': f"EMA{fast} 上穿 EMA{slow}"
            }
        elif ema_fast < ema_slow:
            return {
                'signal_type': 'sell',
                'confidence': min((ema_slow - ema_fast) / ema_slow, 1.0),
                'reason': f"EMA{fast} 下穿 EMA{slow}"
            }
        return None


class BollingerBandsStrategy(BaseStrategy):
    """布林带策略"""

    def generate_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        close = features.get('close', 0)
        bb_upper = features.get('bb_upper', 0)
        bb_lower = features.get('bb_lower', 0)

        if bb_upper == 0 or bb_lower == 0:
            return None

        if close < bb_lower:
            return {
                'signal_type': 'buy',
                'confidence': min((bb_lower - close) / (bb_upper - bb_lower), 1.0),
                'reason': "价格跌破布林带下轨"
            }
        elif close > bb_upper:
            return {
                'signal_type': 'sell',
                'confidence': min((close - bb_upper) / (bb_upper - bb_lower), 1.0),
                'reason': "价格突破布林带上轨"
            }
        return None


_STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "rsi_oversold": RSIOversoldStrategy,
    "rsi_overbought": RSIOverboughtStrategy,
    "macd_cross": MACDCrossStrategy,
    "sma_cross": SMACrossStrategy,
    "ema_cross": EMACrossStrategy,
    "bollinger_bands": BollingerBandsStrategy,
}

_STRATEGY_INFO: Dict[str, StrategyInfo] = {
    "rsi_oversold": StrategyInfo(
        strategy_id="rsi_oversold",
        name="RSI Oversold",
        description="RSI 超卖策略",
        direction="long",
        default_params={"period": 14, "oversold": 30},
        required_features=["rsi_14"]
    ),
    "rsi_overbought": StrategyInfo(
        strategy_id="rsi_overbought",
        name="RSI Overbought",
        description="RSI 超买策略",
        direction="short",
        default_params={"period": 14, "overbought": 70},
        required_features=["rsi_14"]
    ),
    "macd_cross": StrategyInfo(
        strategy_id="macd_cross",
        name="MACD Cross",
        description="MACD 交叉策略",
        direction="both",
        default_params={},
        required_features=["macd", "macd_signal"]
    ),
    "sma_cross": StrategyInfo(
        strategy_id="sma_cross",
        name="SMA Cross",
        description="SMA 交叉策略",
        direction="both",
        default_params={"fast": 10, "slow": 50},
        required_features=["sma_10", "sma_50"]
    ),
    "ema_cross": StrategyInfo(
        strategy_id="ema_cross",
        name="EMA Cross",
        description="EMA 交叉策略",
        direction="both",
        default_params={"fast": 10, "slow": 50},
        required_features=["ema_10", "ema_50"]
    ),
    "bollinger_bands": StrategyInfo(
        strategy_id="bollinger_bands",
        name="Bollinger Bands",
        description="布林带策略",
        direction="both",
        default_params={},
        required_features=["bb_upper", "bb_lower", "close"]
    ),
    "oi_flush": StrategyInfo(
        strategy_id="oi_flush",
        name="OI Flush",
        description="OI清洗后趋势恢复",
        direction="both",
        default_params={"oi_drop_threshold": -0.10, "funding_reversal_threshold": 0.5},
        required_features=["oi_delta", "oi_zscore", "funding_delta"]
    ),
    "short_squeeze": StrategyInfo(
        strategy_id="short_squeeze",
        name="Short Squeeze",
        description="空头挤压",
        direction="long",
        default_params={"funding_zscore_threshold": -2.0, "oi_growth_threshold": 0.02},
        required_features=["funding_zscore", "oi_delta", "short_pressure"]
    ),
    "funding_exhaustion_trap": StrategyInfo(
        strategy_id="funding_exhaustion_trap",
        name="Funding Exhaustion Trap",
        description="资金费率极端反转",
        direction="both",
        default_params={"funding_zscore_threshold": 2.5},
        required_features=["funding_zscore", "funding_divergence"]
    ),
    "panic_reversal": StrategyInfo(
        strategy_id="panic_reversal",
        name="Panic Reversal",
        description="恐慌反转",
        direction="long",
        default_params={"drop_threshold": -0.015, "volume_ratio_threshold": 1.5},
        required_features=["return_1h", "volume_ratio", "liquidation_spike"]
    ),
    "long_liquidation_bounce": StrategyInfo(
        strategy_id="long_liquidation_bounce",
        name="Long Liquidation Bounce",
        description="多头踩踏反弹",
        direction="long",
        default_params={"drop_threshold": -0.02, "rsi_threshold": 25.0},
        required_features=["return_1h", "rsi_14", "volume_ratio", "long_liquidations"]
    ),
    "dead_cat_echo": StrategyInfo(
        strategy_id="dead_cat_echo",
        name="Dead Cat Echo",
        description="死猫反弹继续做空",
        direction="short",
        default_params={"drop_threshold_4h": -0.02, "bounce_ratio_threshold": 0.3},
        required_features=["return_4h", "return_1h", "volume_ratio"]
    ),
    "volume_climax_fade": StrategyInfo(
        strategy_id="volume_climax_fade",
        name="Volume Climax Fade",
        description="放量高潮衰竭",
        direction="short",
        default_params={"volume_ratio_threshold": 2.0, "upper_shadow_threshold": 0.3},
        required_features=["volume_ratio", "upper_shadow_ratio", "return_1h"]
    ),
    "weak_bounce_short": StrategyInfo(
        strategy_id="weak_bounce_short",
        name="Weak Bounce Short",
        description="弱反弹做空",
        direction="short",
        default_params={"drop_threshold_4h": -0.02, "bounce_max": 0.015},
        required_features=["return_4h", "return_1h", "volume_ratio"]
    ),
    "imbalance_pressure": StrategyInfo(
        strategy_id="imbalance_pressure",
        name="Imbalance Pressure",
        description="订单簿失衡压力",
        direction="both",
        default_params={"imbalance_threshold": 0.3},
        required_features=["imbalance_5", "depth_ratio", "microprice"]
    ),
    "sweep_detection": StrategyInfo(
        strategy_id="sweep_detection",
        name="Sweep Detection",
        description="大单扫盘检测",
        direction="both",
        default_params={"sweep_threshold": 0.7},
        required_features=["trade_delta", "sweep_score", "liquidity_vacuum"]
    ),
    "liquidity_vacuum": StrategyInfo(
        strategy_id="liquidity_vacuum",
        name="Liquidity Vacuum",
        description="流动性真空突破",
        direction="both",
        default_params={"spread_expansion_ratio": 2.0},
        required_features=["spread", "top5_depth", "cancel_rate"]
    ),
    "aggressive_flow": StrategyInfo(
        strategy_id="aggressive_flow",
        name="Aggressive Flow",
        description="主动成交流",
        direction="both",
        default_params={"flow_ratio_threshold": 2.0},
        required_features=["cumulative_delta", "aggressive_buy_volume", "aggressive_sell_volume"]
    ),
    "breakout": StrategyInfo(
        strategy_id="breakout",
        name="Breakout",
        description="区间突破",
        direction="both",
        default_params={"lookback": 48, "volume_ratio_threshold": 1.5},
        required_features=["close", "high", "low", "volume"]
    ),
    "trend_following": StrategyInfo(
        strategy_id="trend_following",
        name="Trend Following",
        description="趋势延续",
        direction="both",
        default_params={"fast_period": 10, "slow_period": 50},
        required_features=["close"]
    ),
    "volatility_expansion": StrategyInfo(
        strategy_id="volatility_expansion",
        name="Volatility Expansion",
        description="波动扩张",
        direction="both",
        default_params={"expansion_ratio": 1.5},
        required_features=["close", "high", "low"]
    ),
    "bb_compression_breakout": StrategyInfo(
        strategy_id="bb_compression_breakout",
        name="BB Compression Breakout",
        description="布林压缩突破",
        direction="both",
        default_params={"compression_threshold": 0.02},
        required_features=["bb_upper", "bb_lower", "bb_middle"]
    ),
    "momentum_ignition": StrategyInfo(
        strategy_id="momentum_ignition",
        name="Momentum Ignition",
        description="动量点火",
        direction="both",
        default_params={"volume_spike_threshold": 3.0, "return_threshold": 0.01},
        required_features=["close", "volume"]
    ),
    "lead_lag": StrategyInfo(
        strategy_id="lead_lag",
        name="Lead-Lag",
        description="跨交易所领先滞后",
        direction="both",
        default_params={"divergence_threshold": 0.005},
        required_features=["binance_return", "okx_return"]
    ),
    "premium_divergence": StrategyInfo(
        strategy_id="premium_divergence",
        name="Premium Divergence",
        description="价差异常",
        direction="both",
        default_params={"premium_threshold": 0.005},
        required_features=["basis", "premium", "spread"]
    ),
}


def get_strategy(strategy_id: str, params: Dict[str, Any] = None) -> BaseStrategy:
    """获取策略实例"""
    strategy_class = _STRATEGY_REGISTRY.get(strategy_id)
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy_id}")

    return strategy_class(params)


def get_strategy_info(strategy_id: str) -> Optional[StrategyInfo]:
    """获取策略信息"""
    return _STRATEGY_INFO.get(strategy_id)


def list_strategies() -> List[StrategyInfo]:
    """列出所有策略"""
    return list(_STRATEGY_INFO.values())


def register_strategy(strategy_id: str, strategy_class: Type[BaseStrategy], info: StrategyInfo):
    """注册策略"""
    _STRATEGY_REGISTRY[strategy_id] = strategy_class
    _STRATEGY_INFO[strategy_id] = info
    logger.info(f"Strategy registered: {strategy_id}")
