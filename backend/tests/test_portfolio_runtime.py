"""
Test Portfolio Runtime - 组合运行时测试
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from domain.portfolio import Portfolio, Position
from domain.signal import Signal, SignalDirection, SignalConfidence, SignalStrength, SignalType, SignalRegistry


class TestPortfolioRuntime:
    """测试 Portfolio Runtime"""
    
    @pytest.fixture
    def mock_portfolio(self):
        """创建测试组合"""
        return Portfolio(
            portfolio_id="test_portfolio",
            initial_capital=100000.0,
            equity=100000.0,
        )
    
    @pytest.fixture
    def mock_signal_registry(self):
        """创建信号注册表"""
        return SignalRegistry()
    
    def test_portfolio_creation(self, mock_portfolio):
        """测试组合创建"""
        assert mock_portfolio.initial_capital == 100000.0
        assert mock_portfolio.equity == 100000.0
        assert len(mock_portfolio.positions) == 0
    
    def test_position_update(self, mock_portfolio):
        """测试仓位更新"""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=1.0,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=1000.0,
        )
        
        mock_portfolio.update_position(position)
        
        assert "BTC/USDT" in mock_portfolio.positions
        assert mock_portfolio.positions["BTC/USDT"].unrealized_pnl == 1000.0
    
    def test_position_close(self, mock_portfolio):
        """测试仓位关闭"""
        position = Position(
            symbol="BTC/USDT",
            side="long",
            size=1.0,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=1000.0,
        )
        
        mock_portfolio.update_position(position)
        mock_portfolio.close_position("BTC/USDT")
        
        assert "BTC/USDT" not in mock_portfolio.positions
    
    def test_exposure_calculation(self, mock_portfolio):
        """测试敞口计算"""
        position1 = Position(
            symbol="BTC/USDT",
            side="long",
            size=1.0,
            entry_price=50000.0,
            current_price=50000.0,
            unrealized_pnl=0.0,
        )
        
        position2 = Position(
            symbol="ETH/USDT",
            side="short",
            size=10.0,
            entry_price=3000.0,
            current_price=3000.0,
            unrealized_pnl=0.0,
        )
        
        mock_portfolio.update_position(position1)
        mock_portfolio.update_position(position2)
        
        total_exposure = mock_portfolio.total_exposure
        net_exposure = mock_portfolio.net_exposure
        
        assert total_exposure > 0
        assert net_exposure > 0
    
    def test_portfolio_equity_update(self, mock_portfolio):
        """测试组合权益更新"""
        initial_equity = mock_portfolio.equity
        
        pnl = 5000.0
        mock_portfolio.equity += pnl
        
        assert mock_portfolio.equity == initial_equity + pnl
    
    def test_multiple_positions(self, mock_portfolio):
        """测试多仓位管理"""
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        for i, symbol in enumerate(symbols):
            position = Position(
                symbol=symbol,
                side="long",
                size=float(i + 1),
                entry_price=1000.0 * (i + 1),
                current_price=1050.0 * (i + 1),
                unrealized_pnl=50.0 * (i + 1),
            )
            mock_portfolio.update_position(position)
        
        assert len(mock_portfolio.positions) == 3
        assert mock_portfolio.total_exposure > 0


class TestSignalRegistryIntegration:
    """测试信号注册表集成"""
    
    def test_signal_creation_and_registration(self):
        """测试信号创建和注册"""
        registry = SignalRegistry()
        
        signals = []
        for i in range(3):
            signal = Signal(
                symbol=f"COIN{i}/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG if i % 2 == 0 else SignalDirection.SHORT,
                type=SignalType.TECHNICAL,
                confidence=SignalConfidence(value=0.7 + i * 0.1),
                strength=SignalStrength(magnitude=0.6 + i * 0.1),
                strategy_id=f"strategy_{i}",
            )
            signals.append(signal)
            registry.register(signal)
        
        assert len(registry.signals) == 3
        
        for signal in signals:
            retrieved = registry.get(signal.signal_id)
            assert retrieved == signal
    
    def test_signal_lifecycle(self):
        """测试信号生命周期"""
        registry = SignalRegistry()
        
        signal = Signal(
            symbol="BTC/USDT",
            timeframe="1h",
            direction=SignalDirection.LONG,
            type=SignalType.TECHNICAL,
            confidence=SignalConfidence(value=0.8),
            strength=SignalStrength(magnitude=0.7),
        )
        
        assert signal.state.value == "pending"
        
        registry.register(signal)
        
        signal.activate()
        registry.update(signal)
        
        active_signals = registry.get_active_signals()
        assert len(active_signals) == 1
        
        signal.deactivate()
        registry.update(signal)
        
        active_signals = registry.get_active_signals()
        assert len(active_signals) == 0
    
    def test_strategy_signal_filtering(self):
        """测试策略信号过滤"""
        registry = SignalRegistry()
        
        for strategy in ["strategy_a", "strategy_b", "strategy_c"]:
            for symbol in ["BTC/USDT", "ETH/USDT"]:
                signal = Signal(
                    symbol=symbol,
                    timeframe="1h",
                    direction=SignalDirection.LONG,
                    type=SignalType.TECHNICAL,
                    confidence=SignalConfidence(value=0.7),
                    strength=SignalStrength(magnitude=0.6),
                    strategy_id=strategy,
                )
                registry.register(signal)
        
        strategy_a_signals = registry.get_signals_by_strategy("strategy_a")
        assert len(strategy_a_signals) == 2
        
        all_signals = registry.query(SignalQuery())
        assert len(all_signals) == 6


class TestCapitalAllocation:
    """测试资金分配"""
    
    def test_capital_allocation_logic(self):
        """测试资金分配逻辑"""
        total_capital = 100000.0
        max_exposure = 1.0
        
        signals = []
        for i in range(3):
            signal = Signal(
                symbol=f"COIN{i}/USDT",
                timeframe="1h",
                direction=SignalDirection.LONG,
                type=SignalType.TECHNICAL,
                confidence=SignalConfidence(value=0.6 + i * 0.1),
                strength=SignalStrength(magnitude=0.5 + i * 0.1),
            )
            signals.append(signal)
        
        total_weight = sum(s.confidence.value * s.strength.magnitude for s in signals)
        
        available_capital = total_capital * max_exposure
        
        allocations = {}
        for signal in signals:
            weight = (signal.confidence.value * signal.strength.magnitude) / total_weight
            allocation = available_capital * weight
            allocations[signal.symbol] = allocation
        
        total_allocated = sum(allocations.values())
        
        assert abs(total_allocated - available_capital) < 0.01
        assert all(alloc > 0 for alloc in allocations.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
