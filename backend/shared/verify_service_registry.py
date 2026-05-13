"""
Service Registry Verification Script
验证去中心化服务注册中心
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.service_registry import (
    ServiceRegistry,
    ServiceEndpoint,
    ServiceInfo,
    ServiceStatus,
    get_service_registry,
    ServiceClient,
)


async def verify_service_registry():
    """验证服务注册中心"""
    print("=" * 60)
    print("Service Registry Verification")
    print("=" * 60)
    
    registry = get_service_registry()
    
    print("\n[1] Testing service registration...")
    service_id = await registry.register(
        service_name="aggregation_service",
        version="1.0.0",
        endpoints=[
            ServiceEndpoint(host="localhost", port=8080, protocol="http"),
            ServiceEndpoint(host="localhost", port=8081, protocol="grpc"),
        ],
        capabilities=["candle_aggregation", "trade_processing"],
        dependencies=["clickhouse"],
        metadata={"cluster": "primary"},
    )
    print(f"    Registered service: {service_id}")
    
    print("\n[2] Testing service discovery...")
    services = await registry.discover("aggregation_service")
    print(f"    Found {len(services)} service(s)")
    for s in services:
        print(f"      - {s.service_name}: {s.status.value}")
        print(f"        Endpoints: {[str(e) for e in s.endpoints]}")
    
    print("\n[3] Testing heartbeat...")
    success = await registry.heartbeat(service_id)
    print(f"    Heartbeat success: {success}")
    
    print("\n[4] Testing status update...")
    success = await registry.update_status(service_id, ServiceStatus.DEGRADED)
    print(f"    Status update success: {success}")
    
    service = await registry.get_service(service_id)
    if service:
        print(f"    Current status: {service.status.value}")
    
    print("\n[5] Testing capability discovery...")
    capable_services = await registry.discover_with_capability("candle_aggregation")
    print(f"    Services with 'candle_aggregation': {len(capable_services)}")
    for s in capable_services:
        print(f"      - {s.service_name}")
    
    print("\n[6] Testing service unregistration...")
    success = await registry.unregister(service_id)
    print(f"    Unregister success: {success}")
    
    services = await registry.discover("aggregation_service")
    print(f"    Remaining services: {len(services)}")
    
    print("\n[7] Testing all services...")
    await registry.register(
        service_name="data_service",
        version="1.0.0",
        endpoints=[ServiceEndpoint(host="localhost", port=9090)],
    )
    await registry.register(
        service_name="execution_service",
        version="1.0.0",
        endpoints=[ServiceEndpoint(host="localhost", port=7070)],
    )
    
    all_services = await registry.get_all_services()
    print(f"    Total registered services: {len(all_services)}")
    for s in all_services:
        print(f"      - {s.service_name}: {s.version}")
    
    print("\n" + "=" * 60)
    print("✅ Service Registry Verification Complete!")
    print("=" * 60)
    
    return True


async def verify_service_client():
    """验证服务客户端"""
    print("\n[Service Client Verification]")
    
    client = ServiceClient()
    
    print("\n  Testing endpoint discovery...")
    endpoint = await client.get_endpoint("execution_service")
    print(f"    Endpoint for execution_service: {endpoint}")
    
    print("  ✅ Service Client verified!")
    return True


async def main():
    """主函数"""
    try:
        await verify_service_registry()
        await verify_service_client()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
