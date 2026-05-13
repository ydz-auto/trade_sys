import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from research.strategy.versioning import (
    StrategyVersion, AlphaPipeline, DeploymentStatus
)
from datetime import datetime


class TestStrategyVersioning:
    def test_create_version(self):
        version = StrategyVersion(
            version_id="strategy_001_v1",
            strategy_id="strategy_001",
            version="v1",
            name="test_strategy",
            factors=["factor_001"],
            parameters={"lookback": 20},
            sharpe=1.5,
            ir=0.8,
            max_drawdown=-0.1,
            created_at=datetime.now(),
            status="draft",
            tags=["test"]
        )
        assert version.strategy_id == "strategy_001"
        assert version.version == "v1"
        assert version.status == "draft"

    def test_version_to_dict(self):
        version = StrategyVersion(
            version_id="strategy_001_v1",
            strategy_id="strategy_001",
            version="v1",
            name="test_strategy",
            factors=["factor_001"],
            parameters={"lookback": 20},
            sharpe=1.5,
            ir=0.8,
            max_drawdown=-0.1,
            created_at=datetime.now(),
            status="draft",
            tags=["test"]
        )
        result = version.to_dict()
        assert "version_id" in result
        assert result["name"] == "test_strategy"


class TestAlphaPipeline:
    def test_pipeline_creation(self):
        pipeline = AlphaPipeline()
        assert pipeline is not None

    def test_register_strategy_version(self):
        pipeline = AlphaPipeline()
        version = pipeline.register_strategy_version(
            strategy_id="strategy_001",
            name="test_strategy",
            factors=["factor_001"],
            parameters={"lookback": 20},
            sharpe=1.5,
            ir=0.8,
            max_drawdown=-0.1
        )
        assert version is not None
        assert version.strategy_id == "strategy_001"
        assert version.sharpe == 1.5

    def test_get_strategy_versions(self):
        pipeline = AlphaPipeline()
        pipeline.register_strategy_version(
            strategy_id="strategy_001",
            name="test_strategy_1",
            factors=["factor_001"],
            parameters={"lookback": 20},
            sharpe=1.5,
            ir=0.8,
            max_drawdown=-0.1
        )
        pipeline.register_strategy_version(
            strategy_id="strategy_001",
            name="test_strategy_2",
            factors=["factor_001"],
            parameters={"lookback": 30},
            sharpe=1.8,
            ir=0.9,
            max_drawdown=-0.12
        )
        versions = pipeline.get_strategy_versions("strategy_001")
        assert len(versions) == 2

    def test_get_active_deployments(self):
        pipeline = AlphaPipeline()
        deployments = pipeline.get_active_deployments()
        assert isinstance(deployments, list)

    def test_deployment_status_enum(self):
        assert DeploymentStatus.SHADOW.value == "shadow"
        assert DeploymentStatus.PAPER.value == "paper"
        assert DeploymentStatus.LIVE.value == "live"
