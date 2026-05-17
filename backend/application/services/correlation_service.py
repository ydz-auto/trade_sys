"""
Correlation Service - 相关性分析业务服务

职责：
- 相关性计算逻辑
- 信号评估逻辑
- 分析结果生成逻辑

注意：这是纯业务逻辑，不包含任何基础设施代码。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class SignalDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class CorrelationResult:
    """相关性分析结果"""
    symbol: str
    timeframe: str
    correlations: Dict[str, float]
    signals: List[Dict[str, Any]]
    timestamp: datetime


class CorrelationCalculator:
    """相关性计算器 - 纯业务逻辑"""
    
    def pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """计算 Pearson 相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(a * b for a, b in zip(x, y))
        sum_x2 = sum(a * a for a in x)
        sum_y2 = sum(b * b for b in y)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def rolling_correlation(
        self,
        series1: List[float],
        series2: List[float],
        window: int = 20,
    ) -> List[float]:
        """计算滚动相关性"""
        if len(series1) < window or len(series2) < window:
            return []
        
        correlations = []
        for i in range(window, len(series1) + 1):
            x = series1[i - window:i]
            y = series2[i - window:i]
            correlations.append(self.pearson_correlation(x, y))
        
        return correlations


class SignalAssessor:
    """信号评估器 - 纯业务逻辑"""
    
    def assess(
        self,
        correlation: float,
        threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """评估相关性信号"""
        if correlation > threshold:
            direction = SignalDirection.BULLISH
            strength = min((correlation - threshold) / (1 - threshold), 1.0)
        elif correlation < -threshold:
            direction = SignalDirection.BEARISH
            strength = min((-correlation - threshold) / (1 - threshold), 1.0)
        else:
            direction = SignalDirection.NEUTRAL
            strength = 0.0
        
        return {
            "direction": direction.value,
            "strength": strength,
            "confidence": abs(correlation),
        }


class CorrelationService:
    """
    Correlation Service - 相关性分析业务服务
    
    编排相关性计算和信号评估的完整流程。
    这是纯业务逻辑层，不包含任何基础设施代码。
    """
    
    def __init__(self, correlation_threshold: float = 0.3):
        self.calculator = CorrelationCalculator()
        self.assessor = SignalAssessor()
        self.correlation_threshold = correlation_threshold
    
    def calculate_correlation(
        self,
        series1: List[float],
        series2: List[float],
    ) -> float:
        """计算相关性（纯业务逻辑）"""
        return self.calculator.pearson_correlation(series1, series2)
    
    def assess_signal(self, correlation: float) -> Dict[str, Any]:
        """评估信号（纯业务逻辑）"""
        return self.assessor.assess(correlation, self.correlation_threshold)
    
    def analyze(
        self,
        symbol: str,
        timeframe: str,
        price_series: List[float],
        factor_series: Dict[str, List[float]],
    ) -> CorrelationResult:
        """
        执行相关性分析（纯业务逻辑）
        
        这是业务用例的入口点，编排整个业务流程。
        """
        correlations = {}
        signals = []
        
        for factor_name, series in factor_series.items():
            if len(series) != len(price_series):
                continue
            
            correlation = self.calculate_correlation(price_series, series)
            correlations[factor_name] = correlation
            
            assessment = self.assess_signal(correlation)
            if assessment["direction"] != "neutral":
                signals.append({
                    "factor": factor_name,
                    **assessment,
                })
        
        return CorrelationResult(
            symbol=symbol,
            timeframe=timeframe,
            correlations=correlations,
            signals=signals,
            timestamp=datetime.now(),
        )
