"""
统一的 MarketDataService 单例
管理所有数据采集器，确保只有一个数据源采集中心
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
from infrastructure.config import get_datasource_config_manager

from .collectors import (
    ExchangeCollector,
    ETFCollector,
    NewsCollector,
    MacroCollector,
    SocialMediaCollector,
    CryptoStockCollector,
    TraderDataCollector,
)

logger = get_logger("data_service.market_data")


class MarketDataService:
    """统一的市场数据服务单例"""
    
    _instance: Optional['MarketDataService'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, symbols: Optional[List[str]] = None, exchanges: Optional[List[str]] = None):
        if self._initialized:
            return
            
        self.ds_config = get_datasource_config_manager()
        self.symbols = symbols or self.ds_config.get_symbols()
        self.exchanges = exchanges or self.ds_config.get_exchanges()
        
        self.collectors: Dict[str, Any] = {}
        self._initialized = False
        
        logger.info("MarketDataService instance created")
    
    async def initialize(self):
        """初始化所有采集器"""
        if self._initialized:
            return
            
        logger.info("Initializing MarketDataService collectors...")
        
        self.collectors = {
            "exchange": ExchangeCollector(self.symbols, self.exchanges),
            "etf": ETFCollector(),
            "news": NewsCollector(),
            "macro": MacroCollector(),
            "social": SocialMediaCollector(),
            "crypto_stock": CryptoStockCollector(),
            "trader": TraderDataCollector(),
        }
        
        self._initialized = True
        logger.info("MarketDataService initialized successfully")
    
    def get_collector(self, name: str) -> Optional[Any]:
        """获取指定的采集器"""
        if not self._initialized:
            logger.warning("MarketDataService not initialized")
            return None
        return self.collectors.get(name)
    
    def get_exchange_collector(self) -> Optional[ExchangeCollector]:
        """获取交易所价格采集器"""
        return self.get_collector("exchange")
    
    def get_news_collector(self) -> Optional[NewsCollector]:
        """获取新闻采集器"""
        return self.get_collector("news")
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized


# 全局单例实例
_market_data_service: Optional[MarketDataService] = None


def get_market_data_service(
    symbols: Optional[List[str]] = None,
    exchanges: Optional[List[str]] = None
) -> MarketDataService:
    """获取 MarketDataService 单例"""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService(symbols, exchanges)
    return _market_data_service


def reset_market_data_service():
    """重置 MarketDataService（主要用于测试）"""
    global _market_data_service
    if _market_data_service:
        _market_data_service._initialized = False
        _market_data_service.collectors = {}
    _market_data_service = None
