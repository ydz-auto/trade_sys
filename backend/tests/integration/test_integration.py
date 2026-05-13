"""
Integration Tests - 集成测试
端到端测试验证各模块协同工作
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.contracts import Candle, Trade, Signal, Timeframe, Exchange
from shared.replay import (
    ReplayOrchestrator,
    get_replay_orchestrator,
    ReplayStatus,
    RebuildStatus,
)
from shared.idempotency import (
    IdempotencyManager,
    get_idempotency_manager,
    ExecutionStatus,
)
from shared.service_registry import (
    ServiceRegistry,
    ServiceEndpoint,
    ServiceStatus,
    get_service_registry,
)
from shared.permission import (
    PermissionManager,
    PermissionAction,
    get_permission_manager,
)
from shared.observability import (
    ObservabilityManager,
    get_observability_manager,
)
from shared.data_quality import (
    DataQualityChecker,
    CandleDataQualityChecker,
    get_data_quality_checker,
)


class IntegrationTestSuite:
    """集成测试套件"""
    
    def __init__(self):
        self.results: Dict[str, bool] = {}
        self.errors: Dict[str, str] = {}
    
    def record_result(self, test_name: str, success: bool, error: str = ""):
        self.results[test_name] = success
        if error:
            self.errors[test_name] = error
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("Integration Test Summary")
        print("=" * 60)
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for test_name, success in self.results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {status}: {test_name}")
            if test_name in self.errors:
                print(f"         Error: {self.errors[test_name]}")
        
        print()
        print(f"Total: {passed}/{total} tests passed")
        print("=" * 60)


async def test_contracts_to_replay_flow():
    """测试: Contracts -> Replay 数据流"""
    print("\n[Test 1: Contracts -> Replay Flow]")
    
    try:
        candle = Candle(
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
            timeframe=Timeframe.M1,
            open_time=int(datetime.now().timestamp() * 1000),
            close_time=int(datetime.now().timestamp() * 1000) + 60000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            quote_volume=5000000.0,
            trade_count=500,
            is_closed=True,
        )
        
        assert candle.exchange == Exchange.BINANCE
        assert candle.timeframe == Timeframe.M1
        assert candle.timeframe.seconds == 60
        
        orchestrator = await get_replay_orchestrator()
        
        task = await orchestrator.create_replay_task(
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1m",
            start_time=int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
            end_time=int(datetime.now().timestamp() * 1000),
        )
        
        assert task.task_id is not None
        assert task.status == ReplayStatus.PENDING
        
        print("  ✅ Candle creation and replay task creation work together")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_idempotency_with_execution():
    """测试: 幂等性与执行服务集成"""
    print("\n[Test 2: Idempotency + Execution]")
    
    try:
        idempotency = await get_idempotency_manager()
        
        can_execute1, existing1 = await idempotency.check_and_lock(
            operation_type="order",
            operation_key="test_order_001",
            request_data={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.001},
        )
        
        assert can_execute1 == True
        assert existing1 is None
        
        can_execute2, existing2 = await idempotency.check_and_lock(
            operation_type="order",
            operation_key="test_order_001",
            request_data={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.001},
        )
        
        assert can_execute2 == False
        
        await idempotency.complete(
            operation_type="order",
            operation_key="test_order_001",
            result={"order_id": "12345", "status": "filled"},
        )
        
        status = await idempotency.get_status("order", "test_order_001")
        assert status == ExecutionStatus.COMPLETED
        
        print("  ✅ Idempotency correctly prevents duplicate executions")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_service_registry_discovery():
    """测试: 服务注册与发现"""
    print("\n[Test 3: Service Registry + Discovery]")
    
    try:
        registry = get_service_registry()
        
        service_id = await registry.register(
            service_name="aggregation_service",
            version="1.0.0",
            endpoints=[
                ServiceEndpoint(host="localhost", port=8080),
            ],
            capabilities=["candle_aggregation", "trade_processing"],
        )
        
        assert service_id is not None
        
        services = await registry.discover("aggregation_service")
        assert len(services) == 1
        
        capable = await registry.discover_with_capability("candle_aggregation")
        assert len(capable) == 1
        
        await registry.unregister(service_id)
        
        services = await registry.discover("aggregation_service")
        assert len(services) == 0
        
        print("  ✅ Service registration and discovery work correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_permission_with_config():
    """测试: 权限控制与配置管理"""
    print("\n[Test 4: Permission + Config Management]")
    
    try:
        permission = get_permission_manager()
        
        await permission.assign_role("test_user", "viewer")
        
        can_read = await permission.check_permission(
            "test_user",
            PermissionAction.READ,
            "datasource.symbols",
            "config",
        )
        assert can_read == True
        
        can_write = await permission.check_permission(
            "test_user",
            PermissionAction.WRITE,
            "api_key",
            "config",
        )
        assert can_write == False
        
        is_sensitive = permission.is_sensitive("binance.api_key")
        assert is_sensitive == True
        
        masked = permission.mask_sensitive_value("api_key", "super_secret_12345")
        assert "****" in masked or "*" in masked
        
        print("  ✅ Permission control works with config access")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_observability_metrics():
    """测试: 可观测性指标收集"""
    print("\n[Test 5: Observability + Metrics]")
    
    try:
        observability = get_observability_manager("test_service")
        
        observability.record_request("/api/candles", "GET", 200, 45.5)
        observability.record_request("/api/trades", "POST", 201, 120.3)
        observability.record_business_event("candle_created", {"symbol": "BTCUSDT"})
        
        metrics = await observability.metrics.get_metrics()
        assert len(metrics) > 0
        
        span = observability.start_operation("test_operation")
        await asyncio.sleep(0.05)
        observability.end_operation(span, success=True)
        
        assert span.duration_ms is not None
        assert span.duration_ms > 0
        
        health = await observability.health_checker.check()
        assert health.status in ["healthy", "unhealthy"]
        
        print("  ✅ Observability collects metrics and traces correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_data_quality_with_candles():
    """测试: 数据质量检测与K线"""
    print("\n[Test 6: Data Quality + Candle Validation]")
    
    try:
        checker = CandleDataQualityChecker()
        
        good_candle = {
            "open_time": 1700000000,
            "close_time": 1700000060,
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50050.0,
            "volume": 100.0,
        }
        
        bad_candle = {
            "open_time": 1700000000,
            "close_time": 1700000060,
            "open": 50000.0,
            "high": 49900.0,
            "low": 50100.0,
            "close": 50050.0,
            "volume": 100.0,
        }
        
        assert checker.check_price_consistency(good_candle) == True
        assert checker.check_price_consistency(bad_candle) == False
        
        quality = checker.check_candles([good_candle, bad_candle])
        assert quality.total_records == 2
        assert quality.accuracy < 1.0
        
        print("  ✅ Data quality correctly identifies invalid candles")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_full_pipeline():
    """测试: 完整数据管道"""
    print("\n[Test 7: Full Pipeline Integration]")
    
    try:
        observability = get_observability_manager("pipeline_test")
        idempotency = await get_idempotency_manager()
        quality_checker = CandleDataQualityChecker()
        
        span = observability.start_operation("full_pipeline")
        
        candles = []
        for i in range(5):
            candle = {
                "open_time": 1700000000 + i * 60,
                "close_time": 1700000060 + i * 60,
                "open": 50000.0 + i * 10,
                "high": 50100.0 + i * 10,
                "low": 49900.0 + i * 10,
                "close": 50050.0 + i * 10,
                "volume": 100.0 + i * 10,
            }
            candles.append(candle)
        
        quality = quality_checker.check_candles(candles)
        observability.metrics.gauge("data_quality_score", quality.completeness)
        
        can_execute, _ = await idempotency.check_and_lock(
            operation_type="pipeline",
            operation_key="test_pipeline_001",
            request_data={"candle_count": len(candles)},
        )
        
        assert can_execute == True
        
        await idempotency.complete(
            operation_type="pipeline",
            operation_key="test_pipeline_001",
            result={"processed": len(candles), "quality": quality.status.value},
        )
        
        observability.end_operation(span, success=True)
        
        status = await observability.get_status()
        assert status["service"] == "pipeline_test"
        
        print("  ✅ Full pipeline integrates all modules correctly")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def main():
    """运行所有集成测试"""
    print("=" * 60)
    print("Running Integration Tests")
    print("=" * 60)
    
    suite = IntegrationTestSuite()
    
    tests = [
        ("Contracts -> Replay Flow", test_contracts_to_replay_flow),
        ("Idempotency + Execution", test_idempotency_with_execution),
        ("Service Registry + Discovery", test_service_registry_discovery),
        ("Permission + Config", test_permission_with_config),
        ("Observability + Metrics", test_observability_metrics),
        ("Data Quality + Candles", test_data_quality_with_candles),
        ("Full Pipeline", test_full_pipeline),
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            suite.record_result(test_name, result)
        except Exception as e:
            suite.record_result(test_name, False, str(e))
    
    suite.print_summary()
    
    return all(suite.results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
