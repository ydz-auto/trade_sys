"""
Test Signal Domain - 信号领域测试
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID

from domain.signal.models import (
    Signal,
    SignalDirection,
    SignalConfidence,
    SignalStrength,
    SignalState,
    SignalType,
)
from domain.signal.fusion import (
    VotingFusion,
    BlendingFusion,
    ConsensusFusion,
    EnsembleFusion,
    FusionResult,
)
from domain.signal.lifecycle import (
    SignalDecay,
    SignalDecayConfig,
    SignalInvalidation,
    SignalInvalidationRule,
    SignalCooldown,
    SignalCooldownConfig,
    SignalGenerator,
)
from domain.signal.registry import SignalRegistry, SignalQuery


class TestSignalModels:
    """测试信号模型"""
    
    def test_signal_creation(self):
        """测试信号创建"""
        signal = Signal(
            symbol="BTC/USDT",
            timeframe="1h",
            direction=SignalDirection.LONG,
            type=SignalType.TECHNICAL,
            confidence=SignalConfidence(value=0.8),
            strength=SignalStrength(magnitude=0.7),
        )
        
        assert signal.symbol == "BTC/USDT"
        assert signal.direction == SignalDirection.LONG
        assert signal.state == SignalState.PENDING
        assert signal.confidence.value == 0.8
        assert signal.strength.magnitude == 0.7
    
    def test_signal_activation(self):
        """测试信号激活"""
        signal = Signal(
            symbol="ETH/USDT",
            timeframe="1h",
            direction=SignalDirection.SHORT,
            type=SignalType.SENTIMENT,
            confidence=SignalConfidence(value=0.6),
            strength=SignalStrength(magnitude=0.5),
        )
        
        signal.activate()
        
        assert signal.state == SignalState.ACTIVE
        assert signal.activated_at is not None
    
    def test_signal_expiration(self):
        """测试信号过期"""
        signal = Signal(
            symbol="ETH/USDT",
            timeframe="1h",
            direction=SignalDirection.NEUTRAL,
            type=SignalType.MACRO,
            confidence=SignalConfidence(value=0.4),
            strength=SignalStrength(magnitude=0.3),
            ttl_seconds=10,
        )
        
        assert signal.expires_at is not None
        
        signal.expires_at = datetime.utcnow() - timedelta(seconds=5)
        
        assert signal.is_expired()
        assert not signal.is_active()
    
    def test_signal_remaining_ttl(self):
        """测试信号剩余TTL"""
        signal = Signal(
            symbol="SOL/USDT",
            timeframe="5m",
            direction=SignalDirection.LONG,
            type=SignalType.ORDERBOOK,
            confidence=SignalConfidence(value=0.9),
            strength=SignalStrength(magnitude=0.8),
            ttl_seconds=3600,
        )
        
        assert signal.expires_at is not None
        remaining = signal.remaining_ttl()
        assert remaining is not None
        assert 3500 <= remaining <= 3600


class TestSignalFusion:
    """测试信号融合"""
    
    def test_voting_fusion(self):
        """测试投票融合"""
        fusion = VotingFusion()
        
        signals = [
            Signal(
                symbol="BTC/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG,
                type=SignalType.TECHNICAL,
                confidence=SignalConfidence(value=0.8),
                strength=SignalStrength(magnitude=0.7),
            ),
            Signal(
                symbol="BTC/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG,
                type=SignalType.SENTIMENT,
                confidence=SignalConfidence(value=0.7),
                strength=SignalStrength(magnitude=0.6),
            ),
            Signal(
                symbol="BTC/USDT",
                timeframe="1h",
                direction=SignalDirection.SHORT,
                type=SignalType.MACRO,
                confidence=SignalConfidence(value=0.6),
                strength=SignalStrength(magnitude=0.5),
            ),
        ]
        
        for s in signals:
            s.activate()
        
        result = fusion.fuse(signals)
        
        assert result.direction == SignalDirection.LONG
        assert result.confidence.value > 0
        assert len(result.contributing_signals) == 2
    
    def test_blending_fusion(self):
        """测试混合融合"""
        fusion = BlendingFusion()
        
        signals = [
            Signal(
                symbol="ETH/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG,
                type=SignalType.TECHNICAL,
                confidence=SignalConfidence(value=0.9),
                strength=SignalStrength(magnitude=0.8),
            ),
            Signal(
                symbol="ETH/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG,
                type=SignalType.SENTIMENT,
                confidence=SignalConfidence(value=0.8),
                strength=SignalStrength(magnitude=0.7),
            ),
        ]
        
        for s in signals:
            s.activate()
        
        result = fusion.fuse(signals)
        
        assert result.direction == SignalDirection.LONG
        assert result.method == "blending"
    
    def test_consensus_fusion(self):
        """测试共识融合"""
        fusion = ConsensusFusion(consensus_threshold=0.8)
        
        signals = [
            Signal(
                symbol="SOL/USDT",
                timeframe="1h",
                direction=SignalDirection.SHORT,
                type=SignalType.TECHNICAL,
                confidence=SignalConfidence(value=0.85),
                strength=SignalStrength(magnitude=0.8),
            ),
            Signal(
                symbol="SOL/USDT",
                timeframe="1h",
                direction=SignalDirection.SHORT,
                type=SignalType.SENTIMENT,
                confidence=SignalConfidence(value=0.8),
                strength=SignalStrength(magnitude=0.75),
            ),
            Signal(
                symbol="SOL/USDT",
                timeframe="1h",
                direction=SignalDirection.SHORT,
                type=SignalType.MACRO,
                confidence=SignalConfidence(value=0.78),
                strength=SignalStrength(magnitude=0.7),
            ),
        ]
        
        for s in signals:
            s.activate()
        
        result = fusion.fuse(signals)
        
        assert result.direction == SignalDirection.SHORT
        assert result.method == "consensus"


class TestSignalLifecycle:
    """测试信号生命周期"""
    
    def test_signal_decay(self):
        """测试信号衰减"""
        config = SignalDecayConfig(half_life_seconds=3600, min_active_seconds=600)
        decay = SignalDecay(config)
        
        signal = Signal(
            symbol="BTC/USDT",
            timeframe="1h",
            direction=SignalDirection.LONG,
            type=SignalType.TECHNICAL,
            confidence=SignalConfidence(value=0.8),
            strength=SignalStrength(magnitude=0.7),
        )
        
        signal.generated_at = datetime.utcnow() - timedelta(hours=2)
        
        decayed = decay.calculate_decayed_confidence(signal)
        
        assert decayed < 0.8
        assert decayed > 0.1
    
    def test_signal_cooldown(self):
        """测试信号冷却"""
        config = SignalCooldownConfig(cooldown_seconds=1800)
        cooldown = SignalCooldown(config)
        
        strategy_id = "momentum_strategy"
        symbol = "BTC/USDT"
        
        assert not cooldown.is_in_cooldown(strategy_id, symbol)
        
        cooldown.record_trigger(strategy_id, symbol)
        
        assert cooldown.is_in_cooldown(strategy_id, symbol)
        
        cooldown.last_trigger_time[strategy_id] = datetime.utcnow() - timedelta(hours=1)
        
        assert not cooldown.is_in_cooldown(strategy_id, symbol)
    
    def test_signal_generator(self):
        """测试信号生成"""
        generator = SignalGenerator()
        
        signal = generator.generate(
            symbol="ETH/USDT",
            timeframe="1h",
            direction=SignalDirection.LONG,
            signal_type="technical",
            confidence=0.75,
            strength=0.65,
            strategy_id="breakout_strategy",
            ttl_seconds=3600,
        )
        
        assert signal is not None
        assert signal.direction == SignalDirection.LONG
        assert signal.strategy_id == "breakout_strategy"


class TestSignalRegistry:
    """测试信号注册表"""
    
    def test_registry_basic_operations(self):
        """测试注册表基本操作"""
        registry = SignalRegistry()
        
        signal1 = Signal(
            symbol="BTC/USDT",
            timeframe="1h",
            direction=SignalDirection.LONG,
            type=SignalType.TECHNICAL,
            confidence=SignalConfidence(value=0.8),
            strength=SignalStrength(magnitude=0.7),
            strategy_id="strategy1",
        )
        
        signal2 = Signal(
            symbol="ETH/USDT",
            timeframe="1h",
            direction=SignalDirection.SHORT,
            type=SignalType.SENTIMENT,
            confidence=SignalConfidence(value=0.6),
            strength=SignalStrength(magnitude=0.5),
            strategy_id="strategy2",
        )
        
        registry.register(signal1)
        registry.register(signal2)
        
        assert len(registry.signals) == 2
        
        retrieved = registry.get(signal1.signal_id)
        assert retrieved == signal1
        
        active = registry.get_active_signals()
        assert len(active) == 2
        
        by_symbol = registry.get_signals_by_symbol("BTC/USDT")
        assert len(by_symbol) == 1
        
        by_strategy = registry.get_signals_by_strategy("strategy1")
        assert len(by_strategy) == 1
    
    def test_registry_query(self):
        """测试注册表查询"""
        registry = SignalRegistry()
        
        for i in range(5):
            signal = Signal(
                symbol="BTC/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG if i % 2 == 0 else SignalDirection.SHORT,
                type=SignalType.TECHNICAL,
                confidence=SignalConfidence(value=0.5 + i * 0.1),
                strength=SignalStrength(magnitude=0.5 + i * 0.1),
            )
            registry.register(signal)
        
        query = SignalQuery(min_confidence=0.7)
        results = registry.query(query)
        
        assert len(results) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
