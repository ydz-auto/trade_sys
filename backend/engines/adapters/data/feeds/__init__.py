"""
Adapters Module - 适配器层

所有数据源适配器都在这里注册。

数据源列表：
- OdailyAdapter: Odaily 星球日报 (通过 odaily-skill)
- CryptoPanicAdapter: CryptoPanic 新闻聚合
- WhaleAlertAdapter: 链上巨鲸监控
- TwitterAdapter: Twitter/X
- QQAdapter: QQ 数据

使用示例：
    from adapters import get_adapter_registry, OdailyAdapter
    
    registry = get_adapter_registry()
    registry.register(OdailyAdapter())
    events = await registry.collect_all()
"""

from .base import (
    BaseAdapter,
    AdapterConfig,
    AdapterRegistry,
    get_adapter_registry,
)

from .odaily_adapter import OdailyAdapter, get_odaily_adapter

OdailySkillAdapter = OdailyAdapter

from .cryptopanic_adapter import CryptoPanicAdapter
from .whale_alert_adapter import WhaleAlertAdapter
from .twitter_adapter import TwitterAdapter
from .qq_adapter import QQAdapter

__all__ = [
    "BaseAdapter",
    "AdapterConfig",
    "AdapterRegistry",
    "get_adapter_registry",
    
    "OdailyAdapter",
    "OdailySkillAdapter",
    "get_odaily_adapter",
    
    "CryptoPanicAdapter",
    "WhaleAlertAdapter",
    "TwitterAdapter",
    "QQAdapter",
]
