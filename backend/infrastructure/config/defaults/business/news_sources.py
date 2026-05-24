"""
Deprecated: 此模块已迁移至 application.config.defaults.business.news_sources
请使用: from application.config.defaults.business.news_sources import RSS_NEWS_SOURCES, ...
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.news_sources is deprecated, use application.config.defaults.business.news_sources instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.news_sources import (  # noqa: F401
    RSS_NEWS_SOURCES, CHINESE_MEDIA_CONFIG, REST_NEWS_SOURCES,
    TWITTER_KEYWORDS, REDDIT_KEYWORDS,
)
