import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from research.factor.registry import FactorRegistry, FactorType, FactorStatus
from datetime import datetime


class TestFactorRegistry:
    @pytest.fixture
    def registry(self):
        return FactorRegistry()

    @pytest.fixture
    def sample_metadata(self):
        return {
            "factor_id": "factor_001",
            "name": "momentum_20d",
            "version": "1.0.0",
            "factor_type": FactorType.MOMENTUM if hasattr(FactorType, 'MOMENTUM') else FactorType.TECHNICAL,
            "status": FactorStatus.EXPERIMENTAL,
            "description": "20-day momentum factor",
            "author": "researcher_001",
            "tags": ["momentum", "trend"]
        }

    def test_registry_creation(self, registry):
        assert registry is not None
        assert registry._factors == {}

    def test_get_factor_not_found(self, registry):
        factor = registry.get_factor("nonexistent")
        assert factor is None

    def test_factor_status_enum(self):
        assert FactorStatus.EXPERIMENTAL.value == "experimental"
        assert FactorStatus.VALIDATED.value == "validated"
        assert FactorStatus.PRODUCTION.value == "production"
        assert FactorStatus.DEPRECATED.value == "deprecated"

    def test_factor_type_enum(self):
        assert FactorType.RAW.value == "raw"
        assert FactorType.TECHNICAL.value == "technical"
        assert FactorType.SENTIMENT.value == "sentiment"
