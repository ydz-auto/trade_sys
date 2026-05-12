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
│  (Adapters, Collectors, Crawlers...)    │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Standard Event Protocol         │
│         (Unified Event Format)          │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│              Event Bus                  │
│  (Pub/Sub, Routing, Replay)             │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Intelligence Layer              │
│  (LLM, Sentiment, Narrative...)        │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│         Feature/Factor Engine          │
└─────────────────────────────────────────┘
"""

# 导出共享合约（从 shared/contracts 导入，保持向后兼容）
from shared.contracts import (
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
]
