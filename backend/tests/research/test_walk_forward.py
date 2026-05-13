import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from research.backtest.walk_forward import (
    WalkForwardEngine, WindowStatus
)
from datetime import datetime, timedelta


class TestWalkForwardEngine:
    def test_engine_creation(self):
        engine = WalkForwardEngine()
        assert engine is not None
        assert engine._windows == []

    def test_window_status_enum(self):
        assert WindowStatus.TRAIN.value == "train"
        assert WindowStatus.VALIDATE.value == "validate"
        assert WindowStatus.TEST.value == "test"

    def test_default_config(self):
        engine = WalkForwardEngine()
        assert engine.config is not None
        assert engine.config.train_period == timedelta(days=90)
        assert engine.config.validate_period == timedelta(days=30)
        assert engine.config.step_size == timedelta(days=7)
