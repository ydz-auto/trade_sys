from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.kernel.authority import STATE_OWNERS, assert_state_owner, owns_state
from runtime.kernel.authority.ownership_registry import OwnershipViolation, assert_known_state
from runtime.contracts import RuntimeProtocol, to_immutable_event
from runtime.kernel.guards.import_guard import check_import_boundaries, ImportViolation
from infrastructure.messaging.schema.base_event import BaseEvent


def test_runtime_protocol_is_runtime_checkable():
    assert RuntimeProtocol is not None


def test_ownership_registry_core_states():
    assert STATE_OWNERS["pending_orders"] == "execution_runtime"
    assert STATE_OWNERS["positions"] == "portfolio_runtime"
    assert STATE_OWNERS["replay_cursor"] == "replay_runtime"
    assert_state_owner("feature_runtime", "feature_availability")


def test_ownership_registry_analytical_runtimes():
    assert STATE_OWNERS["projection_read_model"] == "projection_runtime"
    assert STATE_OWNERS["correlation_matrix"] == "correlation_runtime"
    assert STATE_OWNERS["regime_state"] == "regime_runtime"
    assert STATE_OWNERS["narrative_state"] == "narrative_runtime"


def test_ownership_registry_replay_states():
    assert STATE_OWNERS["replay_deterministic_state"] == "replay_runtime"
    assert STATE_OWNERS["replay_session"] == "replay_runtime"


def test_ownership_registry_execution_states():
    assert STATE_OWNERS["execution_reconciliation"] == "execution_runtime"
    assert STATE_OWNERS["fill_lifecycle"] == "execution_runtime"
    assert STATE_OWNERS["order_state"] == "execution_runtime"


def test_ownership_registry_kernel_states():
    assert STATE_OWNERS["kernel_state"] == "kernel_runtime"
    assert STATE_OWNERS["checkpoint_state"] == "kernel_runtime"
    assert STATE_OWNERS["snapshot_state"] == "kernel_runtime"


def test_ownership_violation_raises():
    import pytest
    with pytest.raises(OwnershipViolation):
        assert_state_owner("signal_runtime", "pending_orders")


def test_owns_state_helper():
    assert owns_state("execution_runtime", "pending_orders")
    assert not owns_state("portfolio_runtime", "pending_orders")


def test_assert_known_state_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        assert_known_state("nonexistent_state")


def test_transport_event_converts_to_immutable_event():
    event = BaseEvent(
        event_type="market",
        category="market",
        source="ingestion_runtime",
        symbol="btcusdt",
        event_time_ms=1000,
        ingest_time_ms=1100,
        process_time_ms=1200,
        metadata={"exchange": "binance"},
    )

    immutable = to_immutable_event(event)

    assert immutable.event_id == event.event_id
    assert immutable.symbol == "BTCUSDT"
    assert immutable.event_time_ms == 1000
    assert immutable.available_time_ms == 1100
    assert immutable.processing_time_ms == 1200
    assert immutable.exchange == "binance"


def test_transport_event_with_explicit_available_time():
    event = BaseEvent(
        event_type="feature",
        category="feature",
        source="feature_runtime",
        symbol="ETHUSDT",
        event_time_ms=2000,
        ingest_time_ms=2100,
        process_time_ms=2200,
        metadata={"exchange": "bybit"},
    )

    immutable = to_immutable_event(event, available_time_ms=2050)

    assert immutable.available_time_ms == 2050
    assert immutable.processing_time_ms == 2200


def test_import_guard_detects_domain_to_runtime(tmp_path):
    domain_dir = tmp_path / "domain"
    domain_dir.mkdir()
    (domain_dir / "bad.py").write_text("from runtime.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "domain"
    assert violations[0].imported_module == "runtime.foo"


def test_import_guard_detects_domain_to_infrastructure(tmp_path):
    domain_dir = tmp_path / "domain"
    domain_dir.mkdir()
    (domain_dir / "bad.py").write_text("from infrastructure.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "domain"
    assert violations[0].imported_module == "infrastructure.foo"


def test_import_guard_detects_domain_to_engines(tmp_path):
    domain_dir = tmp_path / "domain"
    domain_dir.mkdir()
    (domain_dir / "bad.py").write_text("from engines.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "domain"
    assert violations[0].imported_module == "engines.foo"


def test_import_guard_detects_api_to_runtime(tmp_path):
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "bad.py").write_text("from runtime.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "api"
    assert violations[0].imported_module == "runtime.foo"


def test_import_guard_detects_api_to_infrastructure(tmp_path):
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "bad.py").write_text("from infrastructure.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "api"
    assert violations[0].imported_module == "infrastructure.foo"


def test_import_guard_detects_api_to_engines(tmp_path):
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "bad.py").write_text("from engines.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "api"
    assert violations[0].imported_module == "engines.foo"


def test_import_guard_detects_infrastructure_to_runtime(tmp_path):
    infra_dir = tmp_path / "infrastructure"
    infra_dir.mkdir()
    (infra_dir / "bad.py").write_text("from runtime.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "infrastructure"
    assert violations[0].imported_module == "runtime.foo"


def test_import_guard_detects_infrastructure_to_engines(tmp_path):
    infra_dir = tmp_path / "infrastructure"
    infra_dir.mkdir()
    (infra_dir / "bad.py").write_text("from engines.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "infrastructure"
    assert violations[0].imported_module == "engines.foo"


def test_import_guard_engines_not_import_runtime(tmp_path):
    engines_dir = tmp_path / "engines"
    engines_dir.mkdir()
    (engines_dir / "bad.py").write_text("from runtime.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "engines"
    assert violations[0].imported_module == "runtime.foo"


def test_import_guard_engines_not_import_application(tmp_path):
    engines_dir = tmp_path / "engines"
    engines_dir.mkdir()
    (engines_dir / "bad.py").write_text("from application.foo import bar\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)

    assert len(violations) == 1
    assert violations[0].importer_layer == "engines"
    assert violations[0].imported_module == "application.foo"


def test_import_guard_allowlist_domain_logging(tmp_path):
    domain_dir = tmp_path / "domain"
    domain_dir.mkdir()
    (domain_dir / "ok.py").write_text("from domain.logging import get_logger\n", encoding="utf-8")

    violations = check_import_boundaries(tmp_path)
    assert len(violations) == 0


def test_import_guard_allowlist_application_infrastructure_queries(tmp_path):
    app_dir = tmp_path / "application"
    app_dir.mkdir()
    (app_dir / "ok.py").write_text(
        "from application.queries.infrastructure_queries import get_redis_value\n",
        encoding="utf-8",
    )

    violations = check_import_boundaries(tmp_path)
    assert len(violations) == 0


def test_import_guard_api_layer_is_clean():
    violations = check_import_boundaries(BACKEND_ROOT)

    api_violations = [
        v for v in violations
        if v.importer_layer == "api"
    ]

    assert api_violations == []


def test_import_guard_no_services_layer_exists():
    services_dir = BACKEND_ROOT / "services"
    assert not services_dir.exists(), "services/ directory should be removed"


def test_canonical_event_type_alias_exists():
    from runtime.contracts.canonical_event import CanonicalEvent
    assert CanonicalEvent is not None


def test_validate_canonical_event_function_exists():
    from runtime.contracts.canonical_event import validate_canonical_event
    assert callable(validate_canonical_event)


def test_compute_state_hash_function_exists():
    from runtime.contracts.canonical_event import compute_state_hash
    assert callable(compute_state_hash)


def test_isolation_manager_class_exists():
    from runtime.kernel.namespace import IsolationManager
    assert IsolationManager is not None


def test_checkpoint_manager_class_exists():
    from runtime.kernel.snapshot.checkpoint import CheckpointManager
    assert CheckpointManager is not None


def test_recovery_coordinator_class_exists():
    from runtime.kernel.snapshot.recovery_coordinator import RecoveryCoordinator
    assert RecoveryCoordinator is not None


def test_engines_compute_exists():
    assert (BACKEND_ROOT / "engines" / "compute").is_dir()


def test_engines_adapters_exists():
    assert (BACKEND_ROOT / "engines" / "adapters").is_dir()


def test_engines_ml_exists():
    assert (BACKEND_ROOT / "engines" / "ml").is_dir()


def test_runtime_kernel_snapshot_exists():
    assert (BACKEND_ROOT / "runtime" / "kernel" / "snapshot").is_dir()
