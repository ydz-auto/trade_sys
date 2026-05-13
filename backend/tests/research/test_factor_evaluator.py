import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from research.factor.evaluator import FactorEvaluator, EvaluationMetrics
from datetime import datetime


class TestFactorEvaluator:
    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        n = 100
        factor_values = np.random.randn(n) * 0.1 + 0.05
        returns = np.random.randn(n) * 0.02 + factor_values * 0.5 + np.random.randn(n) * 0.01
        return {
            "factor": factor_values,
            "returns": returns
        }

    def test_evaluator_creation(self):
        evaluator = FactorEvaluator()
        assert evaluator is not None
        assert len(evaluator._regime_classifiers) == 4

    def test_register_regime_classifier(self):
        evaluator = FactorEvaluator()
        evaluator.register_regime_classifier("custom_regime", lambda r: r > 0.01)
        assert "custom_regime" in evaluator._regime_classifiers

    def test_compute_ic(self, sample_data):
        evaluator = FactorEvaluator()
        ic_result = evaluator._compute_ic(
            sample_data["factor"],
            sample_data["returns"]
        )
        assert ic_result is not None
        assert isinstance(ic_result, (float, np.floating))

    def test_compute_rank_ic(self, sample_data):
        evaluator = FactorEvaluator()
        rank_ic_result = evaluator._compute_rank_ic(
            sample_data["factor"],
            sample_data["returns"]
        )
        assert rank_ic_result is not None

    def test_compute_sharpe(self):
        evaluator = FactorEvaluator()
        ic_values = np.random.randn(50) * 0.05 + 0.03
        sharpe = evaluator._compute_sharpe(ic_values)
        assert sharpe is not None

    def test_compute_turnover(self, sample_data):
        evaluator = FactorEvaluator()
        turnover = evaluator._compute_turnover(sample_data["factor"])
        assert turnover is not None
        assert turnover >= 0

    def test_compute_max_drawdown(self):
        evaluator = FactorEvaluator()
        returns = np.array([-0.01, 0.02, -0.03, 0.05, -0.02, 0.03])
        dd = evaluator._compute_max_drawdown(returns)
        assert dd is not None
        assert dd <= 0

    def test_compute_stability(self):
        evaluator = FactorEvaluator()
        ic_values = np.random.randn(50) * 0.05 + 0.03
        stability = evaluator._compute_stability(ic_values)
        assert stability is not None
        assert 0 <= stability <= 1

    def test_metrics_to_dict(self):
        metrics = EvaluationMetrics(
            ic=0.08,
            rank_ic=0.07,
            ir=0.5,
            sharpe=1.5,
            max_drawdown=-0.1,
            turnover=0.15,
            decay=0.8,
            stability=0.7
        )
        result = metrics.to_dict()
        assert "ic" in result
        assert result["ic"] == 0.08
        assert result["sharpe"] == 1.5
