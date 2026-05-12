"""
示例：使用带弹性能力的基类
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.logging import get_logger
from services.data_service.collectors import (
    BaseCollector,
    MultiSourceCollector,
    CollectorResult,
    SourceConfig
)
from infrastructure.resilience import (
    CircuitBreakerConfig,
    RetryConfig,
    FallbackChain,
    StaticValueFallback
)

logger = get_logger("example.base_collector")


class ExampleSingleCollector(BaseCollector):
    """单数据源收集器示例"""
    
    def __init__(self):
        # 自定义弹性配置
        circuit_config = CircuitBreakerConfig(
            name="example_single_circuit",
            failure_threshold=3,
            recovery_timeout=30.0
        )
        
        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0
        )
        
        # 降级：失败时返回缓存数据
        fallback_data = CollectorResult(
            success=True,
            data={"price": "cached_value", "cached": True},
            source="fallback_cache"
        )
        
        super().__init__(
            name="ExampleSingle",
            circuit_config=circuit_config,
            retry_config=retry_config,
            fallback_value=fallback_data
        )
        
        self.fail_count = 0
    
    async def collect(self) -> CollectorResult:
        """模拟采集，前3次失败，之后成功"""
        self.fail_count += 1
        
        if self.fail_count <= 3:
            raise Exception(f"模拟失败 {self.fail_count}")
        
        return CollectorResult(
            success=True,
            data={"price": "real_value", "timestamp": asyncio.get_event_loop().time()},
            confidence=1.0
        )


class ExampleMultiCollector(MultiSourceCollector):
    """多数据源收集器示例"""
    
    def __init__(self):
        sources = [
            SourceConfig(name="source_a", type="api", priority=1, retry_count=2, retry_delay=0.5),
            SourceConfig(name="source_b", type="api", priority=2, retry_count=3, retry_delay=1.0),
            SourceConfig(name="source_c", type="api", priority=3, retry_count=2, retry_delay=0.5),
        ]
        
        super().__init__("ExampleMulti", sources)
        
        self.source_fail_count = {
            "source_a": 0,
            "source_b": 0,
            "source_c": 0,
        }
    
    async def collect_source(self, name: str, config: SourceConfig) -> CollectorResult:
        """模拟各源独立采集"""
        self.source_fail_count[name] += 1
        
        # source_a 正常，source_b 失败1次，source_c 失败2次
        if name == "source_a":
            success, data = True, {"source": "a", "value": 100}
        elif name == "source_b" and self.source_fail_count[name] <= 1:
            raise Exception(f"source_b 模拟失败")
        elif name == "source_c" and self.source_fail_count[name] <= 2:
            raise Exception(f"source_c 模拟失败")
        else:
            success, data = True, {"source": name, "value": 100}
        
        return CollectorResult(success=success, data=data, confidence=1.0)


async def demo_single_collector():
    """演示单个收集器演示"""
    print("\n" + "="*60)
    print("演示：单个收集器演示")
    print("="*60)
    
    collector = ExampleSingleCollector()
    
    print("\n初始状态：")
    print(collector.get_status())
    
    for i in range(5):
        print(f"\n第 {i+1} 次采集：")
        result = await collector.collect_with_resilience()
        print(f"  结果: {result.success}")
        print(f"  数据: {result.data}")
        print(f"  来源: {result.source}")
        print(f"  错误: {result.error}")
        
        status = collector.get_status()
        print(f"  熔断器状态: {status['resilience']['circuit_breaker']['state']}")


async def demo_multi_collector():
    """多源收集器演示"""
    print("\n" + "="*60)
    print("演示：多源收集器演示")
    print("="*60)
    
    collector = ExampleMultiCollector()
    
    print("\n初始源状态：")
    for name, status in collector.get_source_status().items():
        print(f"  {name}: 启用={status['enabled']}, 优先级={status['priority']}")
    
    print("\n开始采集...")
    results = await collector.collect_all_sources()
    
    print("\n采集结果：")
    for name, result in results.items():
        print(f"  {name}: 成功={result.success}, 数据={result.data}, 错误={result.error}")
    
    print("\n采集后的源状态：")
    for name, status in collector.get_source_status().items():
        circuit = status['circuit_state']
        print(f"  {name}: 熔断器={circuit['state'] if circuit else 'N/A'}")
    
    print("\n最佳结果：")
    best = collector.get_best_result()
    if best:
        print(f"  {best.source}: {best.data}")


async def main():
    print("🚀 基类弹性能力演示")
    
    await demo_single_collector()
    await demo_multi_collector()
    
    print("\n✅ 演示完成！")


if __name__ == "__main__":
    asyncio.run(main())
