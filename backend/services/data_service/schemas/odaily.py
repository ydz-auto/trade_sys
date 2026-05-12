"""
Data Service 内部 Schema - Odaily Skill 原始响应结构

这些是服务内部数据结构，不对外共享，仅用于从 Odaily Skill 获取原始数据。
可以自由修改，只影响 data_service 内部。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class OdailyRawArticle:
    """Odaily Skill 原始文章结构"""
    title: str = ""
    content: str = ""
    url: str = ""
    published_at: str = ""
    author: str = ""


@dataclass
class OdailyRawFlashNews:
    """Odaily Skill 原始快讯结构"""
    title: str = ""
    content: str = ""
    url: str = ""
    published_at: str = ""


@dataclass
class OdailyRawMarketData:
    """Odaily Skill 原始市场数据结构"""
    btc_price: float = 0.0
    eth_price: float = 0.0
    total_market_cap: float = 0.0
    fear_greed_index: int = 49
    regime: str = "neutral"


@dataclass
class OdailyRawWhaleTrade:
    """Odaily Skill 原始巨鲸交易结构"""
    event_title: str = ""
    direction: str = ""  # "yes" or "no"
    size_usd: float = 0.0
    price: float = 0.0
    trader: str = ""


@dataclass
class OdailySkillResponse:
    """Odaily Skill 完整原始响应"""
    module: str = ""
    articles: List[OdailyRawArticle] = field(default_factory=list)
    flash_news: List[OdailyRawFlashNews] = field(default_factory=list)
    market_data: Optional[OdailyRawMarketData] = None
    whale_trades: List[OdailyRawWhaleTrade] = field(default_factory=list)
    raw_markdown: str = ""
    has_data: bool = False
