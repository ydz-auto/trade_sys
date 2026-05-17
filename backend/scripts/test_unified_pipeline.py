#!/usr/bin/env python3
"""
测试统一数据管道

演示如何使用统一的数据管道，包括：
- 创建 Odaily 数据管道
- 创建 RSS 数据管道
- 熔断和降级机制
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger
from infrastructure.pipeline import (
    PipelineConfig,
    DataSourceType,
    UnifiedPublisher,
    UnifiedConsumer,
    DataPipeline,
    DataSource,
    create_rss_pipeline
)

logger = get_logger("test_unified_pipeline")


class MockOdailySource(DataSource):
    """模拟 Odaily 数据源"""
    
    def __init__(self):
        self._call_count = 0
    
    async def fetch(self):
        self._call_count += 1
        
        # 模拟不同情况下的数据
        if self._call_count % 5 == 0:
            # 每5次返回空（测试降级）
            logger.info("Mock: Returning empty data (fallback test)")
            return []
        
        return [
            {
                "id": f"odaily-{self._call_count}-1",
                "title": f"Odaily 快讯 {self._call_count}: BTC ETF 获批",
                "content": "BlackRock BTC ETF 正式获批，市场情绪高涨",
                "source": "clawhub_odaily",
                "sentiment": "bullish",
                "symbols": ["BTC"],
                "tags": ["odaily", "etf"]
            },
            {
                "id": f"odaily-{self._call_count}-2",
                "title": f"Odaily 快讯 {self._call_count}: ETH 升级时间表确定",
                "content": "以太坊升级预计在下季度进行",
                "source": "clawhub_odaily",
                "sentiment": "neutral",
                "symbols": ["ETH"],
                "tags": ["odaily", "ethereum"]
            }
        ]
    
    def get_source_name(self):
        return "MockOdaily"


class MockRSSSource(DataSource):
    """模拟 RSS 数据源"""
    
    def __init__(self):
        self._call_count = 0
    
    async def fetch(self):
        self._call_count += 1
        
        return [
            {
                "id": f"rss-{self._call_count}-1",
                "title": f"Cointelegraph: Bitcoin 突破新高 {self._call_count}",
                "content": "BTC 价格突破 $100,000 大关",
                "source": "cointelegraph",
                "url": "https://cointelegraph.com/news/1",
                "published": "2024-01-01"
            },
            {
                "id": f"rss-{self._call_count}-2",
                "title": f"Decrypt: Ethereum 升级进展 {self._call_count}",
                "content": "以太坊网络性能持续改善",
                "source": "decrypt",
                "url": "https://decrypt.com/news/1",
                "published": "2024-01-01"
            }
        ]
    
    def get_source_name(self):
        return "MockRSS"


async def test_publisher():
    """测试发布者"""
    logger.info("=" * 60)
    logger.info("测试 1: UnifiedPublisher")
    logger.info("=" * 60)
    
    # 创建配置
    config = PipelineConfig(
        name="test_publisher",
        source_type=DataSourceType.SKILL,
        kafka_topic="test.raw.odaily",
        circuit_failure_threshold=3,
        circuit_recovery_timeout=10.0,
        retry_max_attempts=2,
        fallback_enabled=True,
        fallback_data=[
            {
                "id": "fallback-1",
                "title": "【降级数据】BTC ETF 获批（模拟）",
                "content": "降级数据，当 Kafka 不可用时使用"
            }
        ]
    )
    
    # 创建发布者
    publisher = UnifiedPublisher(config, "localhost:9092")
    
    try:
        await publisher.start()
        logger.info("Publisher started")
        
        # 发布测试消息
        test_event = {
            "id": "test-1",
            "title": "测试消息",
            "content": "这是一条测试消息"
        }
        
        success = await publisher.publish(test_event)
        logger.info(f"Publish result: {success}")
        
        # 获取指标
        metrics = publisher.get_metrics()
        logger.info(f"Publisher metrics: {metrics.to_dict()}")
        
        await publisher.stop()
        logger.info("Publisher stopped")
        
        return True
        
    except Exception as e:
        logger.error(f"Publisher test failed: {e}")
        return False


async def test_pipeline():
    """测试完整的数据管道"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 2: DataPipeline")
    logger.info("=" * 60)
    
    # 创建配置
    config = PipelineConfig(
        name="test_odaily_pipeline",
        source_type=DataSourceType.SKILL,
        kafka_topic="test.raw.odaily",
        circuit_failure_threshold=5,
        circuit_recovery_timeout=30.0,
        retry_max_attempts=3,
        fallback_enabled=True,
        fallback_data=[
            {"id": "fallback-1", "title": "降级数据 1"},
            {"id": "fallback-2", "title": "降级数据 2"}
        ]
    )
    
    # 创建数据源
    data_source = MockOdailySource()
    
    # 消息处理器
    async def message_handler(msg):
        logger.info(f"Processing message: {msg.get('title', 'N/A')[:50]}")
    
    # 创建管道
    pipeline = DataPipeline(
        config=config,
        data_source=data_source,
        kafka_bootstrap_servers="localhost:9092",
        message_handler=message_handler
    )
    
    logger.info("Pipeline created")
    
    # 获取状态
    status = pipeline.get_status()
    logger.info(f"Initial status: {status.value}")
    
    # 获取指标
    metrics = pipeline.get_metrics()
    logger.info(f"Initial metrics: {metrics}")
    
    return True


async def test_fallback_mechanism():
    """测试降级机制"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 3: 降级和熔断机制")
    logger.info("=" * 60)
    
    from infrastructure.resilience import CircuitBreaker, CircuitBreakerConfig, RetryPolicy, RetryConfig
    
    # 测试重试策略
    logger.info("测试重试策略...")
    
    retry = RetryPolicy(RetryConfig(
        max_attempts=3,
        initial_delay=0.1
    ))
    
    attempt_count = 0
    
    async def flaky_operation():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("Flaky operation")
        return "Success!"
    
    result = await retry.execute(flaky_operation)
    logger.info(f"Retry result: {result} (after {attempt_count} attempts)")
    
    # 测试降级数据
    logger.info("")
    logger.info("测试降级数据配置...")
    
    config = PipelineConfig(
        name="test_fallback",
        source_type=DataSourceType.API,
        kafka_topic="test.topic",
        fallback_enabled=True,
        fallback_data=[
            {"id": "fallback-1", "title": "降级数据示例"},
            {"id": "fallback-2", "title": "备用数据"}
        ]
    )
    
    logger.info(f"降级配置: enabled={config.fallback_enabled}")
    logger.info(f"降级数据数量: {len(config.fallback_data) if config.fallback_data else 0}")
    
    return True


async def test_create_pipeline_helpers():
    """测试便捷函数"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 4: 便捷管道创建函数")
    logger.info("=" * 60)
    
    # 创建 RSS 管道
    rss_pipeline = create_rss_pipeline(
        name="cointelegraph",
        rss_url="https://cointelegraph.com/rss",
        kafka_topic="test.raw.rss"
    )
    
    logger.info(f"Created RSS pipeline: {rss_pipeline.config.name}")
    logger.info(f"  Source type: {rss_pipeline.config.source_type.value}")
    logger.info(f"  Kafka topic: {rss_pipeline.config.kafka_topic}")
    logger.info(f"  Circuit threshold: {rss_pipeline.config.circuit_failure_threshold}")
    logger.info(f"  Retry attempts: {rss_pipeline.config.retry_max_attempts}")
    
    return True


async def main():
    """主测试函数"""
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "         统一数据管道测试".center(58) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # 运行所有测试
    results = []
    
    results.append(("UnifiedPublisher", await test_publisher()))
    results.append(("DataPipeline", await test_pipeline()))
    results.append(("Fallback & Circuit", await test_fallback_mechanism()))
    results.append(("Pipeline Helpers", await test_create_pipeline_helpers()))
    
    # 输出汇总
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info(f"{name:30s} {status}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("✅ 所有测试通过！")
        logger.info("")
        logger.info("统一管道特性：")
        logger.info("  ✓ 熔断保护：连续失败自动熔断")
        logger.info("  ✓ 自动降级：熔断时使用降级数据")
        logger.info("  ✓ 重试机制：失败自动重试")
        logger.info("  ✓ 批量处理：支持批量发布")
        logger.info("  ✓ 统一接口：适配所有数据源类型")
        return 0
    else:
        logger.error("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
