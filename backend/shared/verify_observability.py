"""
Observability Verification Script
验证可观测性功能
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.observability import (
    ObservabilityManager,
    MetricsCollector,
    Tracer,
    HealthChecker,
    get_observability_manager,
)


async def verify_observability():
    """验证可观测性模块"""
    print("=" * 60)
    print("Observability Verification")
    print("=" * 60)
    
    observability = get_observability_manager("test_service")
    
    print("\n[1] Testing metrics...")
    observability.metrics.counter("requests_total", 1, {"endpoint": "/api/test"})
    observability.metrics.counter("requests_total", 1, {"endpoint": "/api/test"})
    observability.metrics.gauge("active_connections", 42)
    observability.metrics.histogram("request_duration", 150.5, {"method": "GET"})
    
    metrics = await observability.metrics.get_metrics()
    print(f"    Collected {len(metrics)} metrics")
    for m in metrics:
        print(f"      - {m.name}: {m.value} ({m.type.value})")
    
    print("\n[2] Testing tracing...")
    span = observability.start_operation("test_operation", {"param": "value"})
    await asyncio.sleep(0.1)
    observability.end_operation(span, success=True)
    
    traces = await observability.tracer.get_traces()
    print(f"    Collected {len(traces)} traces")
    for t in traces:
        print(f"      - {t.name}: {t.duration_ms}ms")
    
    print("\n[3] Testing health checks...")
    async def db_check():
        return True
    
    async def api_check():
        return True
    
    observability.health_checker.register_check("database", db_check)
    observability.health_checker.register_check("api", api_check)
    
    health = await observability.health_checker.check()
    print(f"    Health status: {health.status}")
    print(f"    Checks: {health.checks}")
    
    print("\n[4] Testing request recording...")
    observability.record_request("/api/users", "GET", 200, 45.5)
    observability.record_request("/api/users", "POST", 201, 120.3)
    observability.record_request("/api/orders", "GET", 500, 5.2)
    
    metrics = await observability.metrics.get_metrics()
    print(f"    Total metrics after recording: {len(metrics)}")
    
    print("\n[5] Testing Prometheus format...")
    prom_output = await observability.metrics.get_prometheus_format()
    print(f"    Prometheus output (first 500 chars):")
    print(prom_output[:500])
    
    print("\n[6] Testing status summary...")
    status = await observability.get_status()
    print(f"    Service: {status['service']}")
    print(f"    Status: {status['status']}")
    print(f"    Uptime: {status['uptime_ms']}ms")
    
    print("\n" + "=" * 60)
    print("✅ Observability Verification Complete!")
    print("=" * 60)
    
    return True


async def verify_metrics_collector():
    """验证指标收集器"""
    print("\n[Metrics Collector Verification]")
    
    collector = MetricsCollector()
    
    collector.counter("page_views", 10)
    collector.counter("page_views", 5)
    collector.gauge("temperature", 25.5)
    collector.histogram("latency", 100)
    collector.histogram("latency", 200)
    
    metrics = await collector.get_metrics()
    print(f"  Total metrics: {len(metrics)}")
    
    prom = await collector.get_prometheus_format()
    print(f"  Prometheus format (first 300 chars):")
    print(prom[:300])
    
    print("  ✅ Metrics Collector verified!")
    return True


async def main():
    """主函数"""
    try:
        await verify_metrics_collector()
        await verify_observability()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
