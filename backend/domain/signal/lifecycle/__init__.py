"""
Signal Lifecycle - 信号生命周期管理

因为信号不是静态的，需要：
- 生成 (generation)
- 衰减 (decay)
- 失效 (invalidation)
- 冷却 (cooldown)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

from domain.signal.models import Signal, SignalState, SignalDirection


@dataclass
class SignalDecayConfig:
    """信号衰减配置"""
    half_life_seconds: int = 3600  # 半衰期1小时
    min_active_seconds: int = 600  # 最少活跃10分钟
    decay_factor: float = 0.1  # 衰减因子


class SignalDecay:
    """信号衰减 - 随时间衰减"""
    
    def __init__(self, config: Optional[SignalDecayConfig] = None):
        self.config = config or SignalDecayConfig()
    
    def calculate_decayed_confidence(self, signal: Signal) -> float:
        """计算衰减后的置信度"""
        if not signal.generated_at:
            return signal.confidence.value
        
        age = (datetime.utcnow() - signal.generated_at).total_seconds()
        
        if age < self.config.min_active_seconds:
            return signal.confidence.value
        
        decay = np.exp(-age * np.log(2) / self.config.half_life_seconds)
        decayed_confidence = signal.confidence.value * decay
        
        return max(0.0, decayed_confidence)
    
    def should_deactivate(self, signal: Signal, decay_threshold: float = 0.3) -> bool:
        """是否应该停用"""
        decayed = self.calculate_decayed_confidence(signal)
        return decayed < decay_threshold
    
    def apply_decay(self, signal: Signal) -> None:
        """应用衰减"""
        decayed_confidence = self.calculate_decayed_confidence(signal)
        signal.confidence.value = decayed_confidence
        
        if decayed_confidence < 0.1:
            signal.expire()
        elif decayed_confidence < 0.3:
            signal.deactivate()


@dataclass
class SignalInvalidationRule:
    """信号失效规则"""
    feature_change_threshold: float = 0.1  # 特征变化10%则失效
    volatility_spike_threshold: float = 2.0  # 波动率激增2倍
    regime_change: bool = True  # 市场状态变化则失效


class SignalInvalidation:
    """信号失效 - 条件触发"""
    
    def __init__(self, rules: Optional[SignalInvalidationRule] = None):
        self.rules = rules or SignalInvalidationRule()
        self.feature_history: Dict[str, List[float]] = {}
    
    def check_invalidation(
        self,
        signal: Signal,
        current_features: Dict[str, float],
        volatility_spike: bool = False,
        regime_changed: bool = False,
    ) -> bool:
        """检查是否应该失效"""
        if not signal.is_active():
            return False
        
        if regime_changed and self.rules.regime_change:
            return True
        
        if volatility_spike:
            return True
        
        for feature_name in signal.source_features:
            if feature_name in current_features and feature_name in self.feature_history:
                old_values = self.feature_history[feature_name]
                if old_values:
                    old_value = old_values[-1]
                    new_value = current_features[feature_name]
                    change = abs((new_value - old_value) / (old_value or 1))
                    if change > self.rules.feature_change_threshold:
                        return True
        
        return False
    
    def invalidate(self, signal: Signal, reason: str = "condition_met") -> None:
        """失效信号"""
        signal.deactivate()
        signal.metadata["invalidation_reason"] = reason
        signal.metadata["invalidation_time"] = datetime.utcnow().isoformat()
    
    def record_feature(self, feature_name: str, value: float) -> None:
        """记录特征值"""
        if feature_name not in self.feature_history:
            self.feature_history[feature_name] = []
        self.feature_history[feature_name].append(value)
        if len(self.feature_history[feature_name]) > 100:
            self.feature_history[feature_name] = self.feature_history[feature_name][-100:]


@dataclass
class SignalCooldownConfig:
    """信号冷却配置"""
    cooldown_seconds: int = 1800  # 30分钟
    cooldown_by_strategy: Dict[str, int] = None
    
    def __post_init__(self):
        if self.cooldown_by_strategy is None:
            self.cooldown_by_strategy = {}


class SignalCooldown:
    """信号冷却 - 防止频繁触发"""
    
    def __init__(self, config: Optional[SignalCooldownConfig] = None):
        self.config = config or SignalCooldownConfig()
        self.last_trigger_time: Dict[str, datetime] = {}  # strategy_id -> last_time
        self.last_trigger_symbol: Dict[str, Dict[str, datetime]] = {}  # symbol -> strategy -> last_time
    
    def is_in_cooldown(self, strategy_id: str, symbol: Optional[str] = None) -> bool:
        """是否在冷却期"""
        now = datetime.utcnow()
        
        if symbol:
            symbol_cooldowns = self.last_trigger_symbol.get(symbol, {})
            if strategy_id in symbol_cooldowns:
                cooldown_time = symbol_cooldowns[strategy_id]
                cooldown = self.config.cooldown_by_strategy.get(strategy_id, self.config.cooldown_seconds)
                if (now - cooldown_time).total_seconds() < cooldown:
                    return True
        
        if strategy_id in self.last_trigger_time:
            cooldown_time = self.last_trigger_time[strategy_id]
            cooldown = self.config.cooldown_by_strategy.get(strategy_id, self.config.cooldown_seconds)
            if (now - cooldown_time).total_seconds() < cooldown:
                return True
        
        return False
    
    def record_trigger(self, strategy_id: str, symbol: Optional[str] = None) -> None:
        """记录触发"""
        now = datetime.utcnow()
        self.last_trigger_time[strategy_id] = now
        
        if symbol:
            if symbol not in self.last_trigger_symbol:
                self.last_trigger_symbol[symbol] = {}
            self.last_trigger_symbol[symbol][strategy_id] = now
    
    def remaining_cooldown(self, strategy_id: str, symbol: Optional[str] = None) -> float:
        """剩余冷却时间（秒）"""
        now = datetime.utcnow()
        
        if symbol:
            symbol_cooldowns = self.last_trigger_symbol.get(symbol, {})
            if strategy_id in symbol_cooldowns:
                cooldown_time = symbol_cooldowns[strategy_id]
                cooldown = self.config.cooldown_by_strategy.get(strategy_id, self.config.cooldown_seconds)
                remaining = cooldown - (now - cooldown_time).total_seconds()
                return max(0.0, remaining)
        
        if strategy_id in self.last_trigger_time:
            cooldown_time = self.last_trigger_time[strategy_id]
            cooldown = self.config.cooldown_by_strategy.get(strategy_id, self.config.cooldown_seconds)
            remaining = cooldown - (now - cooldown_time).total_seconds()
            return max(0.0, remaining)
        
        return 0.0


class SignalGenerator:
    """信号生成 - 从特征到信号"""
    
    def __init__(self):
        self.decay = SignalDecay()
        self.invalidation = SignalInvalidation()
        self.cooldown = SignalCooldown()
    
    def generate(
        self,
        symbol: str,
        timeframe: str,
        direction: SignalDirection,
        signal_type: str,
        confidence: float,
        strength: float,
        source_features: Optional[List[str]] = None,
        strategy_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Signal:
        """生成信号"""
        from domain.signal.models import SignalConfidence, SignalStrength, SignalType
        
        if strategy_id and self.cooldown.is_in_cooldown(strategy_id, symbol):
            return None
        
        signal = Signal(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            type=SignalType(signal_type),
            confidence=SignalConfidence(value=confidence),
            strength=SignalStrength(magnitude=strength),
            source_features=source_features or [],
            strategy_id=strategy_id,
            ttl_seconds=ttl_seconds,
        )
        
        if ttl_seconds:
            signal.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        if strategy_id:
            self.cooldown.record_trigger(strategy_id, symbol)
        
        return signal
    
    def process_signals(self, signals: List[Signal]) -> List[Signal]:
        """批量处理信号"""
        processed = []
        
        for signal in signals:
            if not signal.is_active():
                continue
            
            self.decay.apply_decay(signal)
            
            if signal.is_active():
                processed.append(signal)
        
        return processed
