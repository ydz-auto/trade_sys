"""
Pytest Configuration - Pytest 配置

提供共享的 fixtures 和配置
"""

import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def pytest_configure(config):
    """Pytest 配置"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


@pytest.fixture(scope="session")
def backend_path_fixture():
    """Backend 路径 fixture"""
    return Path(__file__).parent.parent.parent


@pytest.fixture(autouse=True)
def reset_singletons():
    """重置单例（自动应用于所有测试）"""
    import infrastructure.runtime.clock as clock_module
    import infrastructure.verification.determinism as det_module
    import infrastructure.verification.consistency as cons_module
    import infrastructure.risk.exposure as exp_module
    import infrastructure.snapshot.manager as snap_module
    
    clock_module._clock_instance = None
    det_module._verifier = None
    cons_module._tester = None
    exp_module._exposure_manager = None
    snap_module._snapshot_manager = None
    
    yield
    
    clock_module._clock_instance = None
    det_module._verifier = None
    cons_module._tester = None
    exp_module._exposure_manager = None
    snap_module._snapshot_manager = None
