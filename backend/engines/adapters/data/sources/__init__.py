"""
统一数据源基类

分层架构：
┌─────────────────────────────────────┐
│ sources/  - 实时消息源 (新)          │
│   ├── qq_realtime.py    (QQ群)      │
│   ├── telegram_realtime.py (TG)     │
│   └── base_source.py   (基类)       │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ collectors/ - 各种采集器 (历史)       │
│   ├── exchange_collector.py (价格)  │
│   ├── etf_collector.py   (ETF)     │
│   ├── news_collector.py  (新闻)     │
│   └── ...                          │
└─────────────────────────────────────┘

统一点：
- 都输出 StandardEvent
- 都支持熔断/降级
- 都用 shared/contracts
"""

from .base import (
    BaseSource,
    Priority
)

from .qq_realtime import (
    QQRealtimeSource,
)

from .telegram_realtime import (
    TelegramRealtimeSource,
)

__all__ = [
    "BaseSource",
    "Priority",
    "QQRealtimeSource",
    "TelegramRealtimeSource",
]
