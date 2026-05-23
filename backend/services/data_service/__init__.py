"""
Data Service - 数据服务模块

AI Native Trading System 的数据层

架构：
┌─────────────────────────────────────────┐
│          External Sources                │
│  (Exchange APIs, Skills, Crawlers...)  │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Data Collection Layer           │
│  (Adapters, Collectors, Crawlers...)   │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Standard Event Protocol         │
│         (Unified Event Format)          │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│              Event Bus                  │
│  (Pub/Sub, Routing, Replay)           │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Intelligence Layer              │
│  (LLM, Sentiment, Narrative...)        │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Feature/Factor Engine           │
└─────────────────────────────────────────┘
"""

# 导出共享合约（从 shared/contracts 导入，保持向后兼容）
from domain.contracts import (
    StandardEvent,
    EventType,
    Sentiment,
    Importance,
    Source,
    EventFilter,
    create_news_event,
    create_tweet_event,
    create_whale_event
)

# 导出实时源管理器
from .source_manager import (
    DataSourceManager,
    SourceStatus,
    SourceInfo,
    get_source_manager,
    start_sources,
    stop_sources,
    get_source_status,
    get_source_stats
)

# 导出实时源
from .sources import (
    BaseSource,
    Priority,
    QQRealtimeSource,
    TelegramRealtimeSource,
)

__all__ = [
    # Standard Event (shared contract)
    "StandardEvent",
    "EventType",
    "Sentiment",
    "Importance",
    "Source",
    "EventFilter",
    "create_news_event",
    "create_tweet_event",
    "create_whale_event",
    # Source Manager
    "DataSourceManager",
    "SourceStatus",
    "SourceInfo",
    "get_source_manager",
    "start_sources",
    "stop_sources",
    "get_source_status",
    "get_source_stats",
    # Real-time Sources
    "BaseSource",
    "Priority",
    "QQRealtimeSource",
    "TelegramRealtimeSource",
]
