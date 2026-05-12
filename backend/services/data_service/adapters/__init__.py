"""
Adapters Module - 适配器层

所有数据源适配器都在这里注册。

数据源列表：
- OdailySkillAdapter: ClawHub Odaily Skill (M1-M5)
- CryptoPanicAdapter: CryptoPanic 新闻聚合
- WhaleAlertAdapter: 链上巨鲸监控
- TwitterAdapter: Twitter/X (真实 API 支持)
- NewsAdapter: 通用新闻适配器

使用示例：
    from adapters import get_adapter_registry
    
    registry = get_adapter_registry()
    events = await registry.collect_all()
"""

from .skill_adapter import (
    SkillAdapter,
    AdapterConfig,
    AdapterRegistry,
    OdailySkillAdapter,
    NewsAdapter,
    PANewsAdapter,
    get_adapter_registry
)

from .cryptopanic_adapter import CryptoPanicAdapter
from .whale_alert_adapter import WhaleAlertAdapter
from .twitter_adapter import TwitterAdapter
from .qq_adapter import QQAdapter

__all__ = [
    # 基础类
    "SkillAdapter",
    "AdapterConfig",
    "AdapterRegistry",
    "get_adapter_registry",
    
    # 新闻适配器
    "OdailySkillAdapter",
    "CryptoPanicAdapter",
    "NewsAdapter",
    "PANewsAdapter",
    
    # 社交/链上适配器
    "TwitterAdapter",
    "WhaleAlertAdapter",
    "QQAdapter",
]
