"""
Factor Service - 因子计算服务

计算多种因子并发布到 Kafka:
- 趋势因子
- 动量因子
- 波动率因子
- 情绪因子
- 资金流因子
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import random
import math

from infrastructure.logging import get_logger
from infrastructure.cache import get_redis_client

logger = get_logger("services.factor_service")


@dataclass
class FactorData:
    """因子数据"""
    type: str
    name: str
    name_en: str
    weight: float
    value: float
    confidence: int
    color: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class FactorCalculator:
    """因子计算器
    
    基于市场数据计算各类因子
    """
    
    DEFAULT_WEIGHTS = {
        "trend": 0.25,
        "momentum": 0.25,
        "volatility": 0.20,
        "sentiment": 0.15,
        "flow": 0.15,
    }
    
    FACTOR_CONFIGS = {
        "trend": {
            "name": "趋势因子",
            "name_en": "Trend Factor",
            "color": "blue",
        },
        "momentum": {
            "name": "动量因子",
            "name_en": "Momentum Factor",
            "color": "green",
        },
        "volatility": {
            "name": "波动率因子",
            "name_en": "Volatility Factor",
            "color": "orange",
        },
        "sentiment": {
            "name": "情绪因子",
            "name_en": "Sentiment Factor",
            "color": "purple",
        },
        "flow": {
            "name": "资金流因子",
            "name_en": "Flow Factor",
            "color": "cyan",
        },
    }
    
    def __init__(self):
        self._redis = None
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        self._last_prices: Dict[str, float] = {}
    
    async def initialize(self):
        """初始化"""
        try:
            self._redis = get_redis_client()
            logger.info("FactorCalculator initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis not available for FactorCalculator: {e}")
    
    def update_price(self, symbol: str, price: float, volume: float = 0):
        """更新价格数据"""
        self._last_prices[symbol] = price
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
            self._volume_history[symbol] = []
        
        self._price_history[symbol].append(price)
        self._volume_history[symbol].append(volume)
        
        if len(self._price_history[symbol]) > 100:
            self._price_history[symbol] = self._price_history[symbol][-100:]
            self._volume_history[symbol] = self._volume_history[symbol][-100:]
    
    async def calculate_all_factors(self, symbol: str = "BTC") -> List[FactorData]:
        """计算所有因子"""
        factors = []
        
        prices = self._price_history.get(symbol, [])
        volumes = self._volume_history.get(symbol, [])
        
        if len(prices) < 5:
            return self._get_default_factors()
        
        trend_value = self._calculate_trend(prices)
        momentum_value = self._calculate_momentum(prices)
        volatility_value = self._calculate_volatility(prices)
        sentiment_value = await self._calculate_sentiment(symbol)
        flow_value = self._calculate_flow(prices, volumes)
        
        factor_values = {
            "trend": trend_value,
            "momentum": momentum_value,
            "volatility": volatility_value,
            "sentiment": sentiment_value,
            "flow": flow_value,
        }
        
        for factor_type, config in self.FACTOR_CONFIGS.items():
            value = factor_values.get(factor_type, 0.5)
            confidence = self._calculate_confidence(value, len(prices))
            
            factors.append(FactorData(
                type=factor_type,
                name=config["name"],
                name_en=config["name_en"],
                weight=self.DEFAULT_WEIGHTS.get(factor_type, 0.2),
                value=round(value, 3),
                confidence=confidence,
                color=config["color"],
            ))
        
        return factors
    
    def _calculate_trend(self, prices: List[float]) -> float:
        """计算趋势因子
        
        基于移动平均线的趋势判断
        """
        if len(prices) < 10:
            return 0.5
        
        ma_short = sum(prices[-5:]) / 5
        ma_long = sum(prices[-10:]) / 10
        
        if ma_long == 0:
            return 0.5
        
        trend = (ma_short - ma_long) / ma_long
        
        return max(-1, min(1, trend * 10)) * 0.5 + 0.5
    
    def _calculate_momentum(self, prices: List[float]) -> float:
        """计算动量因子
        
        基于价格变化率
        """
        if len(prices) < 5:
            return 0.5
        
        current = prices[-1]
        past = prices[-5]
        
        if past == 0:
            return 0.5
        
        momentum = (current - past) / past
        
        return max(-1, min(1, momentum * 5)) * 0.5 + 0.5
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """计算波动率因子
        
        基于价格标准差
        """
        if len(prices) < 10:
            return 0.5
        
        mean = sum(prices[-10:]) / 10
        variance = sum((p - mean) ** 2 for p in prices[-10:]) / 10
        std = math.sqrt(variance)
        
        if mean == 0:
            return 0.5
        
        cv = std / mean
        
        return max(0, min(1, 1 - cv * 10))
    
    async def _calculate_sentiment(self, symbol: str) -> float:
        """计算情绪因子
        
        基于新闻情绪和社交媒体情绪
        """
        sentiment_score = 0.5
        
        if self._redis:
            try:
                news_data = await self._redis.lrange("news:latest", 0, 4)
                if news_data:
                    total_sentiment = 0
                    count = 0
                    for item in news_data:
                        try:
                            import json
                            news = json.loads(item) if isinstance(item, str) else item
                            score = news.get("sentiment_score", 0.5)
                            if news.get("sentiment") == "bullish":
                                score = 0.5 + abs(score - 0.5)
                            elif news.get("sentiment") == "bearish":
                                score = 0.5 - abs(score - 0.5)
                            total_sentiment += score
                            count += 1
                        except:
                            pass
                    if count > 0:
                        sentiment_score = total_sentiment / count
            except Exception as e:
                logger.debug(f"Could not get sentiment from news: {e}")
        
        return sentiment_score
    
    def _calculate_flow(self, prices: List[float], volumes: List[float]) -> float:
        """计算资金流因子
        
        基于价格和成交量的关系
        """
        if len(prices) < 5 or len(volumes) < 5:
            return 0.5
        
        price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        if not price_changes or not volumes:
            return 0.5
        
        flow_score = 0
        total_volume = 0
        
        for i, change in enumerate(price_changes[-5:]):
            vol = volumes[-(i+2)] if i < len(volumes) else 1
            if change > 0:
                flow_score += vol
            else:
                flow_score -= vol
            total_volume += vol
        
        if total_volume == 0:
            return 0.5
        
        normalized = flow_score / total_volume
        
        return max(0, min(1, normalized * 0.5 + 0.5))
    
    def _calculate_confidence(self, value: float, data_points: int) -> int:
        """计算置信度"""
        base_confidence = 50
        
        if data_points >= 50:
            base_confidence = 80
        elif data_points >= 20:
            base_confidence = 70
        elif data_points >= 10:
            base_confidence = 60
        
        deviation = abs(value - 0.5)
        confidence_adjustment = int(deviation * 40)
        
        return min(100, base_confidence + confidence_adjustment)
    
    def _get_default_factors(self) -> List[FactorData]:
        """获取默认因子数据"""
        factors = []
        for factor_type, config in self.FACTOR_CONFIGS.items():
            factors.append(FactorData(
                type=factor_type,
                name=config["name"],
                name_en=config["name_en"],
                weight=self.DEFAULT_WEIGHTS.get(factor_type, 0.2),
                value=0.5,
                confidence=50,
                color=config["color"],
            ))
        return factors


_factor_calculator: Optional[FactorCalculator] = None


def get_factor_calculator() -> FactorCalculator:
    """获取因子计算器单例"""
    global _factor_calculator
    if _factor_calculator is None:
        _factor_calculator = FactorCalculator()
    return _factor_calculator
