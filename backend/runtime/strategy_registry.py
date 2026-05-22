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
    direction: str  # long, short, both
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


# 策略注册表
_STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "rsi_oversold": RSIOversoldStrategy,
    "rsi_overbought": RSIOverboughtStrategy,
    "macd_cross": MACDCrossStrategy,
    "sma_cross": SMACrossStrategy,
    "ema_cross": EMACrossStrategy,
    "bollinger_bands": BollingerBandsStrategy,
}

# 策略信息注册表
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