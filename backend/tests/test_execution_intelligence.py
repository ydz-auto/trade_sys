"""
Test Execution Intelligence - 执行智能测试
"""

import pytest
from domain.execution.intelligence import (
    SlippagePredictor,
    SlippagePrediction,
    ImpactModel,
    ImpactResult,
    LiquidityEstimator,
    LiquidityEstimate,
    LiquidityRating,
    ExecutionOptimizer,
    ExecutionStrategyType,
    ExecutionPlan,
)


class TestSlippagePredictor:
    """测试滑点预测器"""
    
    def test_basic_prediction(self):
        """测试基本预测"""
        predictor = SlippagePredictor()
        
        prediction = predictor.predict(
            order_size=1.0,
            current_price=50000.0,
            spread_bps=10.0,
            volatility=0.02,
            orderbook_depth=100.0,
            avg_trade_size=10.0,
            is_maker=False,
        )
        
        assert isinstance(prediction, SlippagePrediction)
        assert prediction.expected_slippage_bps > 0
        assert prediction.confidence > 0
    
    def test_maker_vs_taker(self):
        """测试maker vs taker滑点"""
        predictor = SlippagePredictor()
        
        maker_prediction = predictor.predict(
            order_size=1.0,
            current_price=50000.0,
            spread_bps=10.0,
            volatility=0.02,
            orderbook_depth=100.0,
            avg_trade_size=10.0,
            is_maker=True,
        )
        
        taker_prediction = predictor.predict(
            order_size=1.0,
            current_price=50000.0,
            spread_bps=10.0,
            volatility=0.02,
            orderbook_depth=100.0,
            avg_trade_size=10.0,
            is_maker=False,
        )
        
        assert maker_prediction.expected_slippage_bps < taker_prediction.expected_slippage_bps
    
    def test_large_order_slippage(self):
        """测试大单滑点"""
        predictor = SlippagePredictor()
        
        small_order = predictor.predict(
            order_size=1.0,
            current_price=50000.0,
            spread_bps=10.0,
            volatility=0.02,
            orderbook_depth=100.0,
            avg_trade_size=10.0,
        )
        
        large_order = predictor.predict(
            order_size=50.0,
            current_price=50000.0,
            spread_bps=10.0,
            volatility=0.02,
            orderbook_depth=100.0,
            avg_trade_size=10.0,
        )
        
        assert large_order.expected_slippage_bps > small_order.expected_slippage_bps
    
    def test_prediction_factors(self):
        """测试预测因素"""
        predictor = SlippagePredictor()
        
        prediction = predictor.predict(
            order_size=5.0,
            current_price=50000.0,
            spread_bps=15.0,
            volatility=0.03,
            orderbook_depth=50.0,
            avg_trade_size=5.0,
        )
        
        assert "spread" in prediction.factors
        assert "volatility" in prediction.factors
        assert "size" in prediction.factors
        assert "liquidity" in prediction.factors


class TestImpactModel:
    """测试市场冲击模型"""
    
    def test_basic_impact_calculation(self):
        """测试基本冲击计算"""
        model = ImpactModel()
        
        impact = model.calculate_impact(
            order_size=5.0,
            current_price=50000.0,
            orderbook_depth=100.0,
            volatility=0.02,
            avg_daily_volume=1000.0,
        )
        
        assert isinstance(impact, ImpactResult)
        assert impact.total_impact_bps > 0
        assert impact.temporary_impact_bps > 0
    
    def test_temporary_vs_permanent_impact(self):
        """测试临时 vs 永久冲击"""
        model = ImpactModel()
        
        impact = model.calculate_impact(
            order_size=1.0,
            current_price=50000.0,
            orderbook_depth=100.0,
            volatility=0.02,
            avg_daily_volume=1000.0,
        )
        
        assert impact.temporary_impact_bps > impact.permanent_impact_bps
    
    def test_impact_with_large_order(self):
        """测试大单冲击"""
        model = ImpactModel()
        
        small_order = model.calculate_impact(
            order_size=1.0,
            current_price=50000.0,
            orderbook_depth=100.0,
            volatility=0.02,
            avg_daily_volume=1000.0,
        )
        
        large_order = model.calculate_impact(
            order_size=50.0,
            current_price=50000.0,
            orderbook_depth=100.0,
            volatility=0.02,
            avg_daily_volume=1000.0,
        )
        
        assert large_order.total_impact_bps > small_order.total_impact_bps
    
    def test_optimal_size_estimation(self):
        """测试最优规模估算"""
        model = ImpactModel()
        
        optimal_size = model.estimate_optimal_size(
            desired_size=50.0,
            max_impact_bps=20.0,
            current_price=50000.0,
            orderbook_depth=100.0,
            volatility=0.02,
            avg_daily_volume=1000.0,
        )
        
        assert optimal_size > 0
        assert optimal_size <= 50.0


class TestLiquidityEstimator:
    """测试流动性估计器"""
    
    def test_excellent_liquidity(self):
        """测试优秀流动性"""
        estimator = LiquidityEstimator()
        
        estimate = estimator.estimate(
            bid_price=50000.0,
            ask_price=50005.0,
            bid_depth=100.0,
            ask_depth=100.0,
            recent_volume=50.0,
            volatility=0.01,
        )
        
        assert isinstance(estimate, LiquidityEstimate)
        assert estimate.bid_ask_spread_bps < 15.0
    
    def test_poor_liquidity(self):
        """测试差流动性"""
        estimator = LiquidityEstimator()
        
        estimate = estimator.estimate(
            bid_price=50000.0,
            ask_price=50200.0,
            bid_depth=5.0,
            ask_depth=5.0,
            recent_volume=500.0,
            volatility=0.05,
        )
        
        assert estimate.bid_ask_spread_bps > 30.0
    
    def test_liquidity_rating(self):
        """测试流动性评级"""
        estimator = LiquidityEstimator()
        
        excellent = estimator.estimate(50000.0, 50002.0, 200.0, 200.0, 10.0, 0.01)
        poor = estimator.estimate(50000.0, 50200.0, 5.0, 5.0, 500.0, 0.08)
        
        assert excellent.rating in [LiquidityRating.EXCELLENT, LiquidityRating.GOOD]
        assert poor.rating in [LiquidityRating.POOR, LiquidityRating.CRITICAL]
    
    def test_execution_recommendation(self):
        """测试执行建议"""
        estimator = LiquidityEstimator()
        
        excellent = estimator.estimate(50000.0, 50002.0, 200.0, 200.0, 10.0, 0.01)
        poor = estimator.estimate(50000.0, 50200.0, 5.0, 5.0, 500.0, 0.08)
        
        excellent_rec = estimator.get_execution_recommendation(excellent)
        poor_rec = estimator.get_execution_recommendation(poor)
        
        assert excellent_rec["recommendation"] in ["aggressive", "normal"]
        assert poor_rec["recommendation"] in ["passive", "avoid"]


class TestExecutionOptimizer:
    """测试执行优化器"""
    
    def test_basic_optimization(self):
        """测试基本优化"""
        optimizer = ExecutionOptimizer()
        
        plan = optimizer.optimize(
            order_size=5.0,
            current_price=50000.0,
            side="buy",
            bid_price=50000.0,
            ask_price=50005.0,
            bid_depth=100.0,
            ask_depth=100.0,
            spread_bps=10.0,
            volatility=0.02,
            recent_volume=50.0,
            avg_daily_volume=1000.0,
            avg_trade_size=10.0,
        )
        
        assert isinstance(plan, ExecutionPlan)
        assert plan.strategy in ExecutionStrategyType
        assert plan.expected_slippage_bps > 0
    
    def test_aggressive_strategy_selection(self):
        """测试激进策略选择"""
        optimizer = ExecutionOptimizer()
        
        plan = optimizer.optimize(
            order_size=1.0,
            current_price=50000.0,
            side="buy",
            bid_price=50000.0,
            ask_price=50002.0,
            bid_depth=500.0,
            ask_depth=500.0,
            spread_bps=4.0,
            volatility=0.01,
            recent_volume=10.0,
            avg_daily_volume=1000.0,
            avg_trade_size=10.0,
            time_constraint_seconds=30.0,
        )
        
        assert plan.strategy in [ExecutionStrategyType.AGGRESSIVE, ExecutionStrategyType.NORMAL]
    
    def test_passive_strategy_selection(self):
        """测试被动策略选择"""
        optimizer = ExecutionOptimizer()
        
        plan = optimizer.optimize(
            order_size=50.0,
            current_price=50000.0,
            side="buy",
            bid_price=50000.0,
            ask_price=50300.0,
            bid_depth=5.0,
            ask_depth=5.0,
            spread_bps=60.0,
            volatility=0.08,
            recent_volume=500.0,
            avg_daily_volume=1000.0,
            avg_trade_size=5.0,
        )
        
        assert plan.strategy in [ExecutionStrategyType.PASSIVE, ExecutionStrategyType.TWAP]
    
    def test_plan_properties(self):
        """测试计划属性"""
        optimizer = ExecutionOptimizer()
        
        plan = optimizer.optimize(
            order_size=5.0,
            current_price=50000.0,
            side="buy",
            bid_price=50000.0,
            ask_price=50005.0,
            bid_depth=100.0,
            ask_depth=100.0,
            spread_bps=10.0,
            volatility=0.02,
            recent_volume=50.0,
            avg_daily_volume=1000.0,
            avg_trade_size=10.0,
        )
        
        assert plan.num_slices >= 1
        assert plan.expected_slippage_bps >= 0
        assert plan.expected_impact_bps >= 0
        assert plan.total_cost_bps > 0
        assert plan.confidence > 0
        assert len(plan.rationale) > 0


class TestIntegration:
    """测试集成"""
    
    def test_full_optimization_flow(self):
        """测试完整优化流程"""
        slippage_predictor = SlippagePredictor()
        impact_model = ImpactModel()
        liquidity_estimator = LiquidityEstimator()
        optimizer = ExecutionOptimizer()
        
        market_data = {
            "bid_price": 50000.0,
            "ask_price": 50005.0,
            "bid_depth": 100.0,
            "ask_depth": 100.0,
            "spread_bps": 10.0,
            "volatility": 0.02,
            "recent_volume": 50.0,
            "avg_daily_volume": 1000.0,
            "avg_trade_size": 10.0,
        }
        
        liquidity = liquidity_estimator.estimate(
            market_data["bid_price"],
            market_data["ask_price"],
            market_data["bid_depth"],
            market_data["ask_depth"],
            market_data["recent_volume"],
            market_data["volatility"],
        )
        
        slippage = slippage_predictor.predict(
            order_size=5.0,
            current_price=50000.0,
            spread_bps=market_data["spread_bps"],
            volatility=market_data["volatility"],
            orderbook_depth=market_data["bid_depth"] + market_data["ask_depth"],
            avg_trade_size=market_data["avg_trade_size"],
        )
        
        impact = impact_model.calculate_impact(
            order_size=5.0,
            current_price=50000.0,
            orderbook_depth=market_data["bid_depth"] + market_data["ask_depth"],
            volatility=market_data["volatility"],
            avg_daily_volume=market_data["avg_daily_volume"],
        )
        
        plan = optimizer.optimize(
            order_size=5.0,
            current_price=50000.0,
            side="buy",
            **market_data,
        )
        
        assert liquidity.rating in LiquidityRating
        assert slippage.expected_slippage_bps > 0
        assert impact.total_impact_bps > 0
        assert plan.strategy in ExecutionStrategyType


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
