"""
Portfolio Exposure Tests - 组合敞口测试
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from infrastructure.risk.exposure import (
    PortfolioExposureManager,
    PositionExposure,
    AggregatedExposure,
    ExposureLimit,
    ExposureType,
    get_exposure_manager,
)


class TestPortfolioExposureManager:
    """组合敞口管理器测试"""

    def test_initialization(self):
        """测试初始化"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        assert manager.initial_capital == 100000.0
        assert manager.total_capital == 100000.0
        assert manager.available_capital == 100000.0
        assert len(manager._positions) == 0

    def test_update_position_long(self):
        """测试更新多头持仓"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        position = manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=51000,
            leverage=2.0,
        )
        
        assert position.symbol == "BTC/USDT"
        assert position.side == "long"
        assert position.quantity == 1.0
        assert position.value == 51000.0
        assert position.unrealized_pnl == 1000.0

    def test_update_position_short(self):
        """测试更新空头持仓"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        position = manager.update_position(
            symbol="ETH/USDT",
            exchange="binance",
            quantity=-10.0,
            entry_price=3000,
            current_price=2900,
            leverage=2.0,
        )
        
        assert position.side == "short"
        assert position.quantity == -10.0
        assert position.unrealized_pnl == 1000.0

    def test_remove_position(self):
        """测试移除持仓"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=51000,
            leverage=2.0,
        )
        
        position = manager.remove_position("BTC/USDT", "binance", realized_pnl=500.0)
        
        assert position is not None
        assert len(manager._positions) == 0
        assert manager._realized_pnl == 500.0

    def test_exposure_by_exchange(self):
        """测试按交易所聚合敞口"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=50000,
            leverage=1.0,
        )
        
        manager.update_position(
            symbol="ETH/USDT",
            exchange="binance",
            quantity=10.0,
            entry_price=3000,
            current_price=3000,
            leverage=1.0,
        )
        
        exposures = manager.get_exposure_by_exchange()
        
        assert "binance" in exposures
        assert exposures["binance"].gross_value == 80000.0
        assert exposures["binance"].net_value == 80000.0

    def test_exposure_by_symbol(self):
        """测试按币种聚合敞口"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=50000,
            leverage=1.0,
        )
        
        manager.update_position(
            symbol="ETH/USDT",
            exchange="binance",
            quantity=10.0,
            entry_price=3000,
            current_price=3000,
            leverage=1.0,
        )
        
        exposures = manager.get_exposure_by_symbol()
        
        assert "BTC/USDT" in exposures
        assert "ETH/USDT" in exposures
        assert exposures["BTC/USDT"].gross_value == 50000.0

    def test_total_exposure(self):
        """测试总敞口"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=50000,
            leverage=2.0,
        )
        
        total = manager.get_total_exposure()
        
        assert total.gross_value == 50000.0
        assert total.long_value == 50000.0
        assert total.short_value == 0.0
        assert total.leverage == 2.0

    def test_check_limits_pass(self):
        """测试限制检查通过"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=0.2,
            entry_price=50000,
            current_price=50000,
            leverage=2.0,
        )
        
        ok, violations = manager.check_limits()
        
        assert ok
        assert len(violations) == 0

    def test_check_limits_fail(self):
        """测试限制检查失败"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.set_limit(ExposureLimit(
            dimension="portfolio",
            max_gross=40000.0,
        ))
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=50000,
            leverage=1.0,
        )
        
        ok, violations = manager.check_limits()
        
        assert not ok
        assert len(violations) > 0

    def test_check_order_approve(self):
        """测试订单检查通过"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        ok, violations = manager.check_order(
            symbol="BTC/USDT",
            exchange="binance",
            side="buy",
            quantity=0.5,
            price=50000,
            leverage=2.0,
        )
        
        assert ok
        assert len(violations) == 0

    def test_check_order_reject_insufficient_capital(self):
        """测试订单检查拒绝 - 资金不足"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        ok, violations = manager.check_order(
            symbol="BTC/USDT",
            exchange="binance",
            side="buy",
            quantity=5.0,
            price=50000,
            leverage=1.0,
        )
        
        assert not ok
        assert any("Insufficient capital" in v for v in violations)

    def test_check_order_reject_exceed_limit(self):
        """测试订单检查拒绝 - 超限"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.set_limit(ExposureLimit(
            dimension="portfolio",
            max_gross=60000.0,
        ))
        
        manager.update_position(
            symbol="ETH/USDT",
            exchange="binance",
            quantity=3.0,
            entry_price=30000,
            current_price=30000,
            leverage=1.0,
        )
        
        ok, violations = manager.check_order(
            symbol="BTC/USDT",
            exchange="binance",
            side="buy",
            quantity=1.0,
            price=50000,
            leverage=1.0,
        )
        
        assert not ok

    def test_get_risk_state(self):
        """测试获取风险状态"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            entry_price=50000,
            current_price=51000,
            leverage=2.0,
        )
        
        state = manager.get_risk_state()
        
        assert state.total_capital == 100000.0
        assert state.total_exposure == 51000.0
        assert state.unrealized_pnl == 1000.0
        assert state.portfolio_leverage == 2.0

    def test_correlation_risk(self):
        """测试相关性风险"""
        manager = PortfolioExposureManager(initial_capital=100000.0)
        
        manager.update_position(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=0.5,
            entry_price=50000,
            current_price=50000,
            leverage=1.0,
        )
        
        manager.update_position(
            symbol="ETH/USDT",
            exchange="binance",
            quantity=8.33,
            entry_price=3000,
            current_price=3000,
            leverage=1.0,
        )
        
        manager.set_correlation("BTC/USDT", "ETH/USDT", 0.8)
        
        risk = manager.get_correlation_risk()
        assert risk >= 0.0


class TestPositionExposure:
    """持仓敞口测试"""

    def test_position_creation(self):
        """测试持仓创建"""
        position = PositionExposure(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            value=50000.0,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=1000.0,
            unrealized_pnl_pct=0.02,
            leverage=2.0,
            margin_used=25000.0,
            side="long",
        )
        
        assert position.symbol == "BTC/USDT"
        assert position.side == "long"
        assert position.unrealized_pnl == 1000.0

    def test_position_to_dict(self):
        """测试持仓序列化"""
        position = PositionExposure(
            symbol="BTC/USDT",
            exchange="binance",
            quantity=1.0,
            value=50000.0,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=1000.0,
            unrealized_pnl_pct=0.02,
            leverage=2.0,
            margin_used=25000.0,
            side="long",
        )
        
        data = position.to_dict()
        
        assert data["symbol"] == "BTC/USDT"
        assert data["value"] == 50000.0
        assert data["unrealized_pnl"] == 1000.0


class TestAggregatedExposure:
    """聚合敞口测试"""

    def test_aggregated_exposure(self):
        """测试聚合敞口"""
        exposure = AggregatedExposure(
            dimension="exchange",
            value="binance",
            long_value=80000.0,
            short_value=20000.0,
            net_value=60000.0,
            gross_value=100000.0,
            leverage=2.0,
            margin_used=50000.0,
            unrealized_pnl=5000.0,
            positions=["BTC", "ETH"],
        )
        
        assert exposure.dimension == "exchange"
        assert exposure.gross_value == 100000.0
        assert exposure.net_value == 60000.0


class TestExposureLimit:
    """敞口限制测试"""

    def test_limit_check_pass(self):
        """测试限制检查通过"""
        limit = ExposureLimit(
            dimension="portfolio",
            max_long=100000.0,
            max_gross=200000.0,
            max_leverage=3.0,
        )
        
        exposure = AggregatedExposure(
            dimension="portfolio",
            value="total",
            long_value=50000.0,
            short_value=0.0,
            net_value=50000.0,
            gross_value=50000.0,
            leverage=1.0,
            margin_used=50000.0,
            unrealized_pnl=0.0,
        )
        
        ok, violations = limit.check(exposure)
        
        assert ok
        assert len(violations) == 0

    def test_limit_check_fail(self):
        """测试限制检查失败"""
        limit = ExposureLimit(
            dimension="portfolio",
            max_gross=40000.0,
        )
        
        exposure = AggregatedExposure(
            dimension="portfolio",
            value="total",
            long_value=50000.0,
            short_value=0.0,
            net_value=50000.0,
            gross_value=50000.0,
            leverage=1.0,
            margin_used=50000.0,
            unrealized_pnl=0.0,
        )
        
        ok, violations = limit.check(exposure)
        
        assert not ok
        assert len(violations) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
