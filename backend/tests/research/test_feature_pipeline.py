import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from research.pipeline.feature_pipeline import (
    FeaturePipeline, PipelineStage, PipelineConfig, FeatureEngine
)
from datetime import datetime


class TestFeaturePipeline:
    def test_pipeline_creation(self):
        config = PipelineConfig(
            name="test_pipeline",
            symbols=["BTC/USDT"],
            timeframes=["1h"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1)
        )
        pipeline = FeaturePipeline(config)
        assert pipeline is not None
        assert pipeline.config.name == "test_pipeline"

    def test_pipeline_stage_enum(self):
        assert PipelineStage.RAW.value == "raw"
        assert PipelineStage.FEATURE.value == "feature"
        assert PipelineStage.FACTOR.value == "factor"

    def test_feature_engine_base(self):
        engine = FeatureEngine("test")
        assert engine.name == "test"
        assert engine.get_features() == {}
