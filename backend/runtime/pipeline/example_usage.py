"""
ReadHub Pipeline 使用示例
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.logging import setup_logging, get_logger
from runtime.pipeline.readhub_pipeline import (
    ReadHubPipeline,
    PipelineConfig,
    get_pipeline,
)
from runtime.pipeline.realtime_push import get_pusher
from runtime.pipeline.scheduler import get_scheduler
from infrastructure.quality import (
    get_deduplicator,
    get_scorer,
    get_reviewer
)

logger = get_logger("pipeline_example")


async def demo_quality_modules():
    """演示质量模块"""
    logger.info("=" * 60)
    logger.info("质量模块演示")
    logger.info("=" * 60)
    
    deduplicator = get_deduplicator()
    scorer = get_scorer()
    
    test_content = {
        "title": "Bitcoin hits new all-time high above $100,000",
        "content": "Bitcoin has reached a new all-time high, surpassing $100,000 for the first time in history.",
        "source": "coindesk",
        "url": "https://coindesk.com/bitcoin-ath"
    }
    
    logger.info(f"\n测试内容: {test_content['title']}")
    
    dedup_result = deduplicator.check_duplicate(
        title=test_content["title"],
        content=test_content["content"],
        source=test_content["source"],
        published_at=1234567890
    )
    
    logger.info(f"是否重复: {dedup_result.is_duplicate}")
    
    quality = scorer.score(
        title=test_content["title"],
        content=test_content["content"],
        source=test_content["source"],
        url=test_content["url"]
    )
    
    logger.info(f"质量评分: {quality.total_score:.2f}")
    logger.info(f"建议: {quality.recommendation}")
    logger.info(f"标志: {quality.flags}")


async def demo_realtime_push():
    """演示实时推送"""
    logger.info("\n" + "=" * 60)
    logger.info("实时推送演示")
    logger.info("=" * 60)
    
    pusher = get_pusher()
    
    subscriber_id = "user_123"
    
    pusher.subscribe(
        subscriber_id=subscriber_id,
        channels=["news", "price"],
        keywords=["bitcoin", "ethereum", "btc", "eth"]
    )
    
    logger.info(f"订阅者 {subscriber_id} 已订阅")
    
    result = pusher.push_news({
        "id": "news_1",
        "title": "Bitcoin price surge continues",
        "source": "coindesk"
    })
    
    logger.info(f"推送结果: {result.delivered} 成功, {result.failed} 失败")
    
    message = await pusher.get_message(subscriber_id, timeout=1.0)
    if message:
        logger.info(f"收到消息: {message.data['title']}")


async def demo_scheduler():
    """演示调度器"""
    logger.info("\n" + "=" * 60)
    logger.info("调度器演示")
    logger.info("=" * 60)
    
    scheduler = get_scheduler()
    
    call_count = 0
    
    async def my_task():
        nonlocal call_count
        call_count += 1
        logger.info(f"任务执行 #{call_count}")
        return {"count": call_count}
    
    scheduler.register_task(
        task_id="demo_task",
        name="Demo Task",
        callback=my_task,
        interval=2.0,
        priority=1
    )
    
    await scheduler.start()
    
    await asyncio.sleep(5)
    
    await scheduler.stop()
    
    stats = scheduler.get_all_stats()
    logger.info(f"任务执行次数: {stats['demo_task']['total_runs']}")


async def demo_full_pipeline():
    """演示完整流水线"""
    logger.info("\n" + "=" * 60)
    logger.info("完整流水线演示")
    logger.info("=" * 60)
    
    config = PipelineConfig(
        rss_interval=30.0,
        enable_human_review=True,
        enable_realtime_push=True
    )
    
    pipeline = ReadHubPipeline(config)
    
    pipeline.register_callback("news", lambda item: logger.info(f"新新闻: {item.title}"))
    pipeline.register_callback("flagged", lambda item: logger.info(f"标记内容: {item.title}"))
    
    await pipeline.start()
    
    await asyncio.sleep(10)
    
    stats = pipeline.get_stats()
    logger.info(f"流水线统计:")
    logger.info(f"  采集: {stats['pipeline_stats']['total_collected']}")
    logger.info(f"  去重: {stats['pipeline_stats']['total_deduplicated']}")
    logger.info(f"  推送: {stats['pipeline_stats']['total_pushed']}")
    
    await pipeline.stop()


async def main():
    """主函数"""
    logger.info("ReadHub Pipeline 完整演示")
    
    await demo_quality_modules()
    await demo_realtime_push()
    await demo_scheduler()
    await demo_full_pipeline()
    
    logger.info("\n✅ 所有演示完成!")


if __name__ == "__main__":
    asyncio.run(main())
