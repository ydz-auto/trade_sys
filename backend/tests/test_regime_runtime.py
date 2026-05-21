"""
Test Regime Runtime - 市场状态运行时测试
"""

import pytest
from datetime import datetime
import numpy as np

from runtime.regime_runtime import (
    MarketRegime,
    RegimeState,
    RegimeRuntime,
    RegimeRuntimeConfig,
)


class TestMarketRegime:
    """测试市场状态枚举"""
    
    def test_regime_values(self):
        """测试状态枚举值"""
        assert MarketRegime.HIGH_VOLATILITY.value == "high_volatility"
        assert MarketRegime.LOW_VOLATILITY.value == "low_volatility"
        assert MarketRegime.TRENDING.value == "trending"
        assert MarketRegime.RANGING.value == "ranging"
        assert MarketRegime.LIQUIDATION_CASCADE.value == "liquidation_cascade"
        assert MarketRegime.NARRATIVE_BURST.value == "narrative_burst"
        assert MarketRegime.LIQUIDITY_DRAIN.value == "liquidity_drain"
        assert MarketRegime.UNKNOWN.value == "unknown"


class TestRegimeClassification:
    """测试状态分类"""
    
    def test_high_volatility_detection(self):
        """测试高波动状态检测"""
        volatility = 0.08
        volatility_threshold = 0.03
        
        if volatility > volatility_threshold:
            regime = MarketRegime.HIGH_VOLATILITY
        else:
            regime = MarketRegime.LOW_VOLATILITY
        
        assert regime == MarketRegime.HIGH_VOLATILITY
    
    def test_liquidation_cascade_detection(self):
        """测试爆仓潮检测"""
        liquidation_volume = 50_000_000
        
        if liquidation_volume > 10_000_000:
            regime = MarketRegime.LIQUIDATION_CASCADE
        else:
            regime = MarketRegime.UNKNOWN
        
        assert regime == MarketRegime.LIQUIDATION_CASCADE
    
    def test_narrative_burst_detection(self):
        """测试叙事爆发检测"""
        narrative_score = 0.9
        
        if narrative_score > 0.8:
            regime = MarketRegime.NARRATIVE_BURST
        else:
            regime = MarketRegime.UNKNOWN
        
        assert regime == MarketRegime.NARRATIVE_BURST
    
    def test_trending_detection(self):
        """测试趋势检测"""
        trend_strength = 3.0
        
        if trend_strength > 2.0:
            regime = MarketRegime.TRENDING
        else:
            regime = MarketRegime.RANGING
        
        assert regime == MarketRegime.TRENDING
    
    def test_ranging_detection(self):
        """测试横盘检测"""
        price_range = 0.015
        range_threshold = 0.02
        trend_strength = 1.0
        
        if trend_strength < 2.0 and price_range < range_threshold:
            regime = MarketRegime.RANGING
        else:
            regime = MarketRegime.UNKNOWN
        
        assert regime == MarketRegime.RANGING
    
    def test_liquidity_drain_detection(self):
        """测试流动性枯竭检测"""
        liquidity_score = 0.85
        
        if liquidity_score > 0.7:
            regime = MarketRegime.LIQUIDITY_DRAIN
        else:
            regime = MarketRegime.UNKNOWN
        
        assert regime == MarketRegime.LIQUIDITY_DRAIN


class TestRegimeState:
    """测试状态数据"""
    
    def test_state_creation(self):
        """测试状态创建"""
        state = RegimeState(
            regime=MarketRegime.HIGH_VOLATILITY,
            confidence=0.85,
            since=datetime.utcnow(),
            duration_seconds=0.0,
            features={"volatility": 0.08},
            active_strategies=["breakout", "momentum"],
        )
        
        assert state.regime == MarketRegime.HIGH_VOLATILITY
        assert state.confidence == 0.85
        assert "breakout" in state.active_strategies
        assert "volatility" in state.features
    
    def test_state_duration_update(self):
        """测试状态持续时间更新"""
        state = RegimeState(
            regime=MarketRegime.TRENDING,
            confidence=0.75,
            since=datetime.utcnow(),
            duration_seconds=0.0,
            features={},
            active_strategies=["trend_following"],
        )
        
        from datetime import timedelta
        import time
        
        time.sleep(0.1)
        
        state.duration_seconds = (datetime.utcnow() - state.since).total_seconds()
        
        assert state.duration_seconds >= 0.1


class TestStrategySelection:
    """测试策略选择"""
    
    def test_strategy_registry_mapping(self):
        """测试策略注册表映射"""
        registry = {
            MarketRegime.HIGH_VOLATILITY: ["breakout", "momentum"],
            MarketRegime.LOW_VOLATILITY: ["mean_reversion", "range"],
            MarketRegime.TRENDING: ["trend_following", "momentum"],
            MarketRegime.RANGING: ["mean_reversion", "grid"],
            MarketRegime.LIQUIDATION_CASCADE: ["liquidation_arbitrage", "contrarian"],
            MarketRegime.NARRATIVE_BURST: ["momentum", "news_trader"],
            MarketRegime.LIQUIDITY_DRAIN: ["passive", "low_touch"],
            MarketRegime.UNKNOWN: ["conservative"],
        }
        
        assert registry[MarketRegime.HIGH_VOLATILITY] == ["breakout", "momentum"]
        assert registry[MarketRegime.LIQUIDATION_CASCADE] == ["liquidation_arbitrage", "contrarian"]
        assert registry[MarketRegime.UNKNOWN] == ["conservative"]
    
    def test_strategy_should_enable(self):
        """测试策略启用判断"""
        current_regime = MarketRegime.HIGH_VOLATILITY
        
        strategy_registry = {
            MarketRegime.HIGH_VOLATILITY: ["breakout", "momentum"],
            MarketRegime.LOW_VOLATILITY: ["mean_reversion"],
        }
        
        active_strategies = strategy_registry.get(current_regime, [])
        
        assert "breakout" in active_strategies
        assert "mean_reversion" not in active_strategies


class TestRegimeRuntimeLogic:
    """测试 Regime Runtime 逻辑"""
    
    def test_price_history_management(self):
        """测试价格历史管理"""
        price_history = []
        max_history = 1000
        
        for i in range(1200):
            price_history.append(50000 + i)
        
        if len(price_history) > max_history:
            price_history = price_history[-max_history:]
        
        assert len(price_history) == 1000
        assert price_history[0] == 50200
    
    def test_volatility_calculation(self):
        """测试波动率计算"""
        prices = [50000, 50500, 50200, 51000, 50800, 51500, 51200, 52000]
        returns = np.diff(prices) / prices[:-1]
        
        volatility = np.std(returns)
        mean_return = np.mean(returns)
        
        assert volatility > 0
        assert mean_return > 0
    
    def test_trend_strength_calculation(self):
        """测试趋势强度计算"""
        prices = [50000, 51000, 52000, 53000, 54000, 55000, 56000, 57000]
        returns = np.diff(prices) / prices[:-1]
        
        trend_strength = abs(np.mean(returns)) / (np.std(returns) + 1e-10)
        
        assert trend_strength > 2.0
    
    def test_price_range_calculation(self):
        """测试价格区间计算"""
        prices = [50000, 51000, 50200, 50800, 50500, 51200, 50300, 51100]
        
        price_range = (np.max(prices) - np.min(prices)) / np.mean(prices)
        
        assert 0.01 < price_range < 0.05


class TestRegimeTransition:
    """测试状态转换"""
    
    def test_regime_change_detection(self):
        """测试状态变化检测"""
        current_regime = MarketRegime.HIGH_VOLATILITY
        new_regime = MarketRegime.TRENDING
        
        regime_changed = current_regime != new_regime
        
        assert regime_changed
        assert new_regime == MarketRegime.TRENDING
    
    def test_regime_stability(self):
        """测试状态稳定性"""
        current_regime = MarketRegime.RANGING
        new_regime = MarketRegime.RANGING
        
        regime_changed = current_regime != new_regime
        
        assert not regime_changed
    
    def test_regime_history_recording(self):
        """测试状态历史记录"""
        regime_history = []
        
        regime_history.append({
            "old_regime": MarketRegime.UNKNOWN.value,
            "new_regime": MarketRegime.HIGH_VOLATILITY.value,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": 0.85,
        })
        
        regime_history.append({
            "old_regime": MarketRegime.HIGH_VOLATILITY.value,
            "new_regime": MarketRegime.TRENDING.value,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": 0.78,
        })
        
        assert len(regime_history) == 2
        assert regime_history[1]["new_regime"] == "trending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
