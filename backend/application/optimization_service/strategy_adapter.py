"""
Strategy Signal Adapter - 策略信号适配器

核心职责：
1. 桥接 STRATEGY_REGISTRY 和 SignalRuntime
2. 将策略参数转换为信号生成逻辑
3. 确保回测和实盘使用相同的信号生成代码

这是消除 research/runtime 分叉的关键组件。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("strategy_signal_adapter")


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class Signal:
    """交易信号"""
    signal_id: str
    strategy_id: str
    symbol: str
    direction: SignalDirection
    confidence: float
    strength: float
    timestamp: datetime
    params: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "strength": self.strength,
            "timestamp": self.timestamp.isoformat(),
            "params": self.params,
            "metadata": self.metadata,
        }


@dataclass
class SignalContext:
    """信号上下文"""
    price: float
    volume: float = 0.0
    features: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_feature(self, name: str, default: float = 0.0) -> float:
        return self.features.get(name, default)


class StrategySignalAdapter:
    """
    策略信号适配器
    
    将 STRATEGY_REGISTRY 中的策略转换为信号生成函数。
    
    用法：
    ```python
    adapter = StrategySignalAdapter()
    
    # 注册策略
    adapter.register("rsi_oversold", params={"period": 14, "oversold": 30})
    
    # 生成信号
    signal = adapter.generate_signal("rsi_oversold", context)
    ```
    """
    
    def __init__(self):
        self._strategies: Dict[str, Callable] = {}
        self._params: Dict[str, Dict[str, Any]] = {}
        self._signal_counter = 0
        
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认策略"""
        self.register("rsi_oversold", self._rsi_oversold_signal)
        self.register("rsi_overbought", self._rsi_overbought_signal)
        self.register("macd_cross", self._macd_cross_signal)
        self.register("sma_cross", self._sma_cross_signal)
        self.register("ema_cross", self._ema_cross_signal)
        self.register("bollinger_bands", self._bollinger_bands_signal)
        self.register("momentum", self._momentum_signal)
        self.register("volume_spike", self._volume_spike_signal)
    
    def register(
        self,
        strategy_id: str,
        signal_fn: Callable[[SignalContext, Dict[str, Any]], Optional[Signal]],
        default_params: Dict[str, Any] = None,
    ):
        """注册策略"""
        self._strategies[strategy_id] = signal_fn
        self._params[strategy_id] = default_params or {}
    
    def set_params(self, strategy_id: str, params: Dict[str, Any]):
        """设置策略参数"""
        self._params[strategy_id] = params
    
    def generate_signal(
        self,
        strategy_id: str,
        context: SignalContext,
        params: Dict[str, Any] = None,
    ) -> Optional[Signal]:
        """
        生成信号
        
        这是核心方法，确保回测和实盘使用相同的信号生成逻辑。
        """
        signal_fn = self._strategies.get(strategy_id)
        if signal_fn is None:
            return None
        
        merged_params = {**self._params.get(strategy_id, {}), **(params or {})}
        
        signal = signal_fn(context, merged_params)
        
        if signal:
            self._signal_counter += 1
            signal.signal_id = f"sig_{strategy_id}_{self._signal_counter}"
            signal.strategy_id = strategy_id
            signal.timestamp = context.timestamp
            signal.params = merged_params
        
        return signal
    
    def _rsi_oversold_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """RSI 超卖信号"""
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        
        rsi_key = f"rsi_{period}"
        rsi = context.get_feature(rsi_key)
        
        if rsi <= 0:
            return None
        
        if rsi < oversold:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.LONG,
                confidence=1.0 - (rsi / oversold),
                strength=(oversold - rsi) / oversold,
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _rsi_overbought_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """RSI 超买信号"""
        period = params.get("period", 14)
        overbought = params.get("overbought", 70)
        
        rsi_key = f"rsi_{period}"
        rsi = context.get_feature(rsi_key)
        
        if rsi <= 0:
            return None
        
        if rsi > overbought:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.SHORT,
                confidence=(rsi - overbought) / (100 - overbought),
                strength=(rsi - overbought) / (100 - overbought),
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _macd_cross_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """MACD 交叉信号"""
        macd = context.get_feature("macd")
        signal = context.get_feature("macd_signal")
        hist = context.get_feature("macd_hist", macd - signal if macd and signal else 0)
        
        if macd == 0 or signal == 0:
            return None
        
        if macd > signal and hist > 0:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.LONG,
                confidence=min(abs(hist) / abs(signal + 1e-10), 1.0),
                strength=abs(hist),
                timestamp=context.timestamp,
                params=params,
            )
        elif macd < signal and hist < 0:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.SHORT,
                confidence=min(abs(hist) / abs(signal + 1e-10), 1.0),
                strength=abs(hist),
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _sma_cross_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """SMA 交叉信号"""
        fast = params.get("fast", 10)
        slow = params.get("slow", 50)
        
        sma_fast = context.get_feature(f"sma_{fast}")
        sma_slow = context.get_feature(f"sma_{slow}")
        
        if sma_fast == 0 or sma_slow == 0:
            return None
        
        diff = (sma_fast - sma_slow) / sma_slow
        
        if sma_fast > sma_slow:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.LONG,
                confidence=min(abs(diff) * 10, 1.0),
                strength=abs(diff),
                timestamp=context.timestamp,
                params=params,
            )
        elif sma_fast < sma_slow:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.SHORT,
                confidence=min(abs(diff) * 10, 1.0),
                strength=abs(diff),
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _ema_cross_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """EMA 交叉信号"""
        fast = params.get("fast", 10)
        slow = params.get("slow", 50)
        
        ema_fast = context.get_feature(f"ema_{fast}")
        ema_slow = context.get_feature(f"ema_{slow}")
        
        if ema_fast == 0 or ema_slow == 0:
            return None
        
        diff = (ema_fast - ema_slow) / ema_slow
        
        if ema_fast > ema_slow:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.LONG,
                confidence=min(abs(diff) * 10, 1.0),
                strength=abs(diff),
                timestamp=context.timestamp,
                params=params,
            )
        elif ema_fast < ema_slow:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.SHORT,
                confidence=min(abs(diff) * 10, 1.0),
                strength=abs(diff),
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _bollinger_bands_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """布林带信号"""
        bb_upper = context.get_feature("bb_upper")
        bb_lower = context.get_feature("bb_lower")
        bb_width = context.get_feature("bb_width")
        
        price = context.price
        
        if bb_upper == 0 or bb_lower == 0:
            return None
        
        if price < bb_lower:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.LONG,
                confidence=(bb_lower - price) / (bb_lower + 1e-10),
                strength=(bb_lower - price) / price,
                timestamp=context.timestamp,
                params=params,
            )
        elif price > bb_upper:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.SHORT,
                confidence=(price - bb_upper) / (bb_upper + 1e-10),
                strength=(price - bb_upper) / price,
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _momentum_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """动量信号"""
        period = params.get("period", 10)
        threshold = params.get("threshold", 0.02)
        
        momentum = context.get_feature(f"momentum_{period}")
        
        if momentum == 0:
            return None
        
        if momentum > threshold:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.LONG,
                confidence=min(momentum / threshold, 1.0),
                strength=momentum,
                timestamp=context.timestamp,
                params=params,
            )
        elif momentum < -threshold:
            return Signal(
                signal_id="",
                strategy_id="",
                symbol="",
                direction=SignalDirection.SHORT,
                confidence=min(abs(momentum) / threshold, 1.0),
                strength=abs(momentum),
                timestamp=context.timestamp,
                params=params,
            )
        
        return None
    
    def _volume_spike_signal(
        self,
        context: SignalContext,
        params: Dict[str, Any],
    ) -> Optional[Signal]:
        """成交量激增信号"""
        lookback = params.get("lookback", 50)
        threshold = params.get("threshold", 2.0)
        
        volume_ratio = context.get_feature(f"volume_ratio_{lookback}")
        returns = context.get_feature("return", 0)
        
        if volume_ratio < threshold:
            return None
        
        direction = SignalDirection.LONG if returns > 0 else SignalDirection.SHORT
        
        return Signal(
            signal_id="",
            strategy_id="",
            symbol="",
            direction=direction,
            confidence=min(volume_ratio / threshold, 1.0),
            strength=volume_ratio,
            timestamp=context.timestamp,
            params=params,
            metadata={"volume_ratio": volume_ratio, "returns": returns},
        )
    
    def get_registered_strategies(self) -> List[str]:
        """获取已注册的策略列表"""
        return list(self._strategies.keys())
