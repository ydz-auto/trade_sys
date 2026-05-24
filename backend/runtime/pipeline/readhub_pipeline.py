"""
ReadHub Pipeline - 完整的数据流水线
整合：多源采集 → 清洗去重 → 质量打分 → 审核 → 推送
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.utils import (
    get_http_client,
    RSSFetcher,
    RSSSource,
    get_symbol_extractor,
    get_data_cleaner,
    get_date_parser
)
from infrastructure.quality import (
    get_deduplicator,
    get_scorer,
    get_tracker,
    get_reviewer,
    ReviewPriority
)
from runtime.pipeline.scheduler import get_scheduler
from runtime.pipeline.realtime_push import get_pusher
from runtime.pipeline.scheduler import TaskPriority

logger = get_logger("pipeline.readhub")


@dataclass
class PipelineConfig:
    """流水线配置"""
    rss_interval: float = 60.0
    api_interval: float = 120.0
    crawler_interval: float = 300.0
    max_concurrent_sources: int = 10
    quality_threshold: float = 0.5
    dedup_threshold: float = 0.85
    enable_human_review: bool = True
    enable_realtime_push: bool = True


@dataclass
class PipelineItem:
    """流水线处理项"""
    id: str
    title: str
    content: str
    url: str
    source: str
    author: str
    published_at: int
    raw_data: Dict = field(default_factory=dict)
    
    is_duplicate: bool = False
    original_id: Optional[str] = None
    quality_score: float = 0.0
    recommendation: str = "pass"
    symbols: List[str] = field(default_factory=list)
    
    processing_time_ms: float = 0
    pipeline_stage: str = "collected"


@dataclass
class PipelineStats:
    """流水线统计"""
    total_collected: int = 0
    total_deduplicated: int = 0
    total_quality_checked: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_pushed: int = 0
    avg_processing_time_ms: float = 0


class ReadHubPipeline:
    """ReadHub 风格的数据流水线
    
    特性：
    - 多源并行采集（RSS + API + 爬虫）
    - 智能去重（SimHash + MinHash）
    - 质量打分（来源 + 内容 + 信任度）
    - 可选人工审核
    - 实时推送
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        
        self.http_client = get_http_client()
        self.rss_fetcher = RSSFetcher()
        self.symbol_extractor = get_symbol_extractor()
        self.data_cleaner = get_data_cleaner()
        self.date_parser = get_date_parser()
        
        self.deduplicator = get_deduplicator()
        self.scorer = get_scorer()
        self.tracker = get_tracker()
        self.reviewer = get_reviewer()
        
        self.scheduler = get_scheduler()
        self.pusher = get_pusher()
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._stats = PipelineStats()
        self._callbacks: Dict[str, List[Callable]] = {}
        
        self._rss_sources: List[RSSSource] = []
        self._init_default_sources()
    
    def _init_default_sources(self):
        """初始化默认 RSS 源"""
        from infrastructure.utilities import PRESET_RSS_SOURCES
        self._rss_sources = PRESET_RSS_SOURCES
    
    def add_rss_source(self, name: str, url: str, priority: int = 1):
        """添加 RSS 源"""
        self._rss_sources.append(RSSSource(
            name=name,
            url=url,
            priority=priority
        ))
        logger.info(f"Added RSS source: {name}")
    
    async def collect_from_rss(self) -> List[PipelineItem]:
        """从 RSS 采集"""
        items = []
        
        try:
            articles = await self.rss_fetcher.fetch_multiple(self._rss_sources)
            
            for article in articles:
                item = PipelineItem(
                    id=article.id,
                    title=article.title,
                    content=article.content,
                    url=article.url,
                    source=article.source,
                    author=article.author or "",
                    published_at=article.published_at,
                    raw_data={
                        "tags": article.tags,
                        "summary": article.summary
                    }
                )
                items.append(item)
            
            self._stats.total_collected += len(items)
            logger.info(f"Collected {len(items)} items from RSS")
            
        except Exception as e:
            logger.error(f"RSS collection error: {e}")
        
        return items
    
    async def process_item(self, item: PipelineItem) -> PipelineItem:
        """处理单个项目"""
        start_time = time.time()
        
        try:
            item.pipeline_stage = "processing"
            
            cleaned = self.data_cleaner.clean_text(
                item.title + " " + item.content,
                remove_urls=True,
                remove_ads=True
            )
            item.content = cleaned.text
            
            item.symbols = self.symbol_extractor.extract_crypto_only(
                item.title + " " + item.content
            )
            
            dedup_result = self.deduplicator.check_duplicate(
                title=item.title,
                content=item.content,
                source=item.source,
                published_at=item.published_at
            )
            item.is_duplicate = dedup_result.is_duplicate
            item.original_id = dedup_result.original_id
            
            if not item.is_duplicate:
                quality = self.scorer.score(
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    url=item.url,
                    author=item.author
                )
                item.quality_score = quality.total_score
                item.recommendation = quality.recommendation
                
                self.deduplicator.add_content(
                    content_id=item.id,
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    published_at=item.published_at
                )
                
                self.tracker.create_record(
                    content_id=item.id,
                    url=item.url,
                    title=item.title,
                    published_at=item.published_at
                )
                
                if self.config.enable_human_review:
                    if self.reviewer.should_review(item.title, item.content, item.source):
                        self.reviewer.submit_for_review(
                            content_id=item.id,
                            title=item.title,
                            content=item.content,
                            source=item.source,
                            url=item.url,
                            priority=ReviewPriority.NORMAL,
                            reason="Auto-submitted for review"
                        )
            
            item.processing_time_ms = (time.time() - start_time) * 1000
            item.pipeline_stage = "processed"
            
            return item
            
        except Exception as e:
            logger.error(f"Error processing item {item.id}: {e}")
            item.pipeline_stage = "error"
            return item
    
    async def process_batch(self, items: List[PipelineItem]) -> List[PipelineItem]:
        """批量处理"""
        results = []
        
        semaphore = asyncio.Semaphore(self.config.max_concurrent_sources)
        
        async def process_with_semaphore(item: PipelineItem):
            async with semaphore:
                return await self.process_item(item)
        
        tasks = [process_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = [r for r in results if isinstance(r, PipelineItem)]
        
        self._stats.total_deduplicated += sum(1 for r in valid_results if r.is_duplicate)
        self._stats.total_quality_checked += sum(1 for r in valid_results if not r.is_duplicate)
        
        return valid_results
    
    async def push_to_realtime(self, items: List[PipelineItem]):
        """推送到实时系统"""
        if not self.config.enable_realtime_push:
            return
        
        for item in items:
            if item.is_duplicate:
                continue
            
            if item.recommendation == "pass":
                self._stats.total_approved += 1
                
                news_data = {
                    "id": item.id,
                    "title": item.title,
                    "content": item.content[:500],
                    "url": item.url,
                    "source": item.source,
                    "author": item.author,
                    "published_at": item.published_at,
                    "symbols": item.symbols,
                    "quality_score": item.quality_score
                }
                
                self.pusher.push_news(news_data)
                self._stats.total_pushed += 1
                
                self._notify_callbacks("news", item)
                
            elif item.recommendation == "flag":
                self._notify_callbacks("flagged", item)
    
    async def run_collection_cycle(self):
        """运行一次采集周期"""
        items = await self.collect_from_rss()
        
        if not items:
            return
        
        processed = await self.process_batch(items)
        
        approved = [item for item in processed if item.recommendation == "pass" and not item.is_duplicate]
        
        await self.push_to_realtime(approved)
        
        logger.info(f"Pipeline cycle complete: {len(items)} collected, "
                   f"{len(approved)} approved, {self._stats.total_pushed} pushed")
    
    async def start(self):
        """启动流水线"""
        if self._running:
            return
        
        self._running = True
        
        await self.pusher.start_heartbeat()
        
        self.scheduler.register_task(
            task_id="rss_collection",
            name="RSS Collection",
            callback=self.run_collection_cycle,
            interval=self.config.rss_interval,
            priority=TaskPriority.HIGH
        )
        
        await self.scheduler.start()
        
        logger.info("ReadHub Pipeline started")
    
    async def stop(self):
        """停止流水线"""
        if not self._running:
            return
        
        self._running = False
        
        await self.scheduler.stop()
        await self.pusher.stop_heartbeat()
        
        for task in self._tasks:
            task.cancel()
        
        logger.info("ReadHub Pipeline stopped")
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def _notify_callbacks(self, event: str, item: PipelineItem):
        """触发回调"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(item)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "pipeline_stats": {
                "total_collected": self._stats.total_collected,
                "total_deduplicated": self._stats.total_deduplicated,
                "total_quality_checked": self._stats.total_quality_checked,
                "total_approved": self._stats.total_approved,
                "total_rejected": self._stats.total_rejected,
                "total_pushed": self._stats.total_pushed,
                "avg_processing_time_ms": self._stats.avg_processing_time_ms
            },
            "deduplicator": self.deduplicator.get_stats(),
            "scorer": self.scorer.get_stats(),
            "reviewer": self.reviewer.get_stats(),
            "pusher": self.pusher.get_stats(),
            "scheduler": self.scheduler.get_all_stats()
        }


_pipeline: Optional[ReadHubPipeline] = None

def get_pipeline() -> ReadHubPipeline:
    """获取流水线单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = ReadHubPipeline()
    return _pipeline
