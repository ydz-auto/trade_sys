"""
Data Domain 配置

数据领域的配置定义
包括数据源、数据采集频率、缓存策略等
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class DataSourceConfig(BaseModel):
    """数据源配置"""
    symbols: List[str] = Field(default=["BTCUSDT", "ETHUSDT"], description="交易标的")
    exchanges: List[str] = Field(default=["binance"], description="交易所")
    check_interval_seconds: int = Field(default=60, ge=1, description="检查间隔(秒)")


class NewsSourceConfig(BaseModel):
    """新闻源配置"""
    sources: Dict[str, str] = Field(default_factory=dict, description="新闻源 URL 映射")
    check_interval_seconds: int = Field(default=300, ge=60, description="新闻检查间隔(秒)")
    min_content_length: int = Field(default=100, description="最小内容长度")


class MacroSourceConfig(BaseModel):
    """宏观数据源配置"""
    gold_api: Optional[str] = Field(default=None, description="黄金 API")
    oil_api: Optional[str] = Field(default=None, description="原油 API")
    check_interval_seconds: int = Field(default=3600, ge=300, description="检查间隔(秒)")


class ETFSourceConfig(BaseModel):
    """ETF 数据源配置"""
    enabled: bool = Field(default=False, description="是否启用")
    symbols: List[str] = Field(default_factory=list, description="ETF 标的")
    api_farside: Optional[str] = Field(default=None, description="Farside API")
    check_interval_seconds: int = Field(default=300, description="检查间隔(秒)")


class DataRuntimeConfig(BaseModel):
    """
    数据运行时配置
    支持热更新和版本化
    """
    source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    news: NewsSourceConfig = Field(default_factory=NewsSourceConfig)
    macro: MacroSourceConfig = Field(default_factory=MacroSourceConfig)
    etf: ETFSourceConfig = Field(default_factory=ETFSourceConfig)

    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl_seconds: int = Field(default=60, ge=1, description="缓存 TTL(秒)")

    enable_realtime: bool = Field(default=True, description="是否启用实时数据")
    enable_historical: bool = Field(default=True, description="是否启用历史数据")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


DATA_DEFAULTS: Dict[str, Any] = {
    "datasource.symbols": ["BTCUSDT", "ETHUSDT"],
    "datasource.exchanges": ["binance"],
    "datasource.check_interval_seconds": 60,
}


DATA_SCHEMA: Dict[str, Dict[str, Any]] = {
    "datasource.symbols": {
        "value_type": "list",
        "default": ["BTCUSDT", "ETHUSDT"],
        "description": "Trading symbols",
    },
    "datasource.exchanges": {
        "value_type": "list",
        "default": ["binance"],
        "description": "Enabled exchanges",
    },
}
