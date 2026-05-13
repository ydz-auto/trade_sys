import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from research.experiment.tracker import (
    ExperimentTracker, ExperimentStatus, ExperimentType
)


class TestExperimentTracker:
    @pytest.fixture
    def tracker(self):
        return ExperimentTracker()

    def test_tracker_creation(self, tracker):
        assert tracker is not None
        assert tracker._experiments == {}
        assert tracker._trials == {}

    def test_create_experiment(self, tracker):
        config = tracker.create_experiment(
            name="test_experiment",
            experiment_type=ExperimentType.BACKTEST
        )
        assert config is not None
        assert config.experiment_id.startswith("exp_")
        assert config.name == "test_experiment"

    def test_experiment_status_enum(self):
        assert ExperimentStatus.PENDING.value == "pending"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.FAILED.value == "failed"

    def test_experiment_type_enum(self):
        assert ExperimentType.BACKTEST.value == "backtest"
        assert ExperimentType.WALK_FORWARD.value == "walk_forward"
        assert ExperimentType.HYPERPARAMETER.value == "hyperparameter"
