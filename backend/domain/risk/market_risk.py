"""
Market Risk - 市场风险

监控市场整体风险:
1. 波动率风险
2. 流动性风险
3. 相关性突变
4. 极端事件
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from domain.logging import get_logger

logger = get_logger("risk.market_risk")


class MarketCondition(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    STRESS = "stress"
    CRISIS = "crisis"


@dataclass
class MarketRiskAssessment:
    timestamp: datetime
    
    condition: MarketCondition
    
    volatility_level: float
    liquidity_level: float
    correlation_level: float
    
    volatility_risk: float
    liquidity_risk: float
    tail_risk: float
    
    overall_risk: float
    
    recommended_actions: List[str]
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketRiskMonitor:
    volatility_threshold_high: float = 0.05
    volatility_threshold_extreme: float = 0.1
    
    liquidity_threshold_low: float = 0.3
    liquidity_threshold_critical: float = 0.1
    
    lookback_periods: int = 100
    
    def __post_init__(self):
        self._volatility_history: Dict[str, List[float]] = {}
        self._liquidity_history: Dict[str, List[float]] = {}
    
    def assess(
        self,
        market_data: Dict[str, Any],
        symbols: List[str],
    ) -> MarketRiskAssessment:
        timestamp = datetime.now()
        
        volatility_level = self._calculate_volatility_level(market_data, symbols)
        liquidity_level = self._calculate_liquidity_level(market_data, symbols)
        correlation_level = self._calculate_correlation_level(market_data)
        
        volatility_risk = self._assess_volatility_risk(volatility_level)
        liquidity_risk = self._assess_liquidity_risk(liquidity_level)
        tail_risk = self._assess_tail_risk(market_data)
        
        overall_risk = 0.4 * volatility_risk + 0.3 * liquidity_risk + 0.3 * tail_risk
        
        condition = self._determine_condition(overall_risk)
        
        actions = self._recommend_actions(condition, volatility_risk, liquidity_risk)
        
        return MarketRiskAssessment(
            timestamp=timestamp,
            condition=condition,
            volatility_level=volatility_level,
            liquidity_level=liquidity_level,
            correlation_level=correlation_level,
            volatility_risk=volatility_risk,
            liquidity_risk=liquidity_risk,
            tail_risk=tail_risk,
            overall_risk=overall_risk,
            recommended_actions=actions,
        )
    
    def _calculate_volatility_level(
        self,
        market_data: Dict[str, Any],
        symbols: List[str],
    ) -> float:
        volatilities = []
        
        for symbol in symbols:
            vol = market_data.get(f"{symbol}_volatility")
            if vol is None:
                vol = market_data.get("volatility", 0.02)
            volatilities.append(vol)
        
        return np.mean(volatilities) if volatilities else 0.02
    
    def _calculate_liquidity_level(
        self,
        market_data: Dict[str, Any],
        symbols: List[str],
    ) -> float:
        liquidities = []
        
        for symbol in symbols:
            liq = market_data.get(f"{symbol}_liquidity")
            if liq is None:
                liq = market_data.get("liquidity", 1.0)
            liquidities.append(liq)
        
        return np.mean(liquidities) if liquidities else 1.0
    
    def _calculate_correlation_level(
        self,
        market_data: Dict[str, Any],
    ) -> float:
        return market_data.get("avg_correlation", 0.5)
    
    def _assess_volatility_risk(self, volatility: float) -> float:
        if volatility > self.volatility_threshold_extreme:
            return 1.0
        elif volatility > self.volatility_threshold_high:
            return 0.7
        elif volatility > 0.03:
            return 0.4
        else:
            return 0.2
    
    def _assess_liquidity_risk(self, liquidity: float) -> float:
        if liquidity < self.liquidity_threshold_critical:
            return 1.0
        elif liquidity < self.liquidity_threshold_low:
            return 0.7
        elif liquidity < 0.5:
            return 0.4
        else:
            return 0.2
    
    def _assess_tail_risk(self, market_data: Dict[str, Any]) -> float:
        skewness = abs(market_data.get("skewness", 0.0))
        kurtosis = market_data.get("kurtosis", 3.0)
        
        tail_score = 0.0
        
        if abs(skewness) > 1:
            tail_score += 0.3
        
        if kurtosis > 5:
            tail_score += 0.4
        elif kurtosis > 4:
            tail_score += 0.2
        
        funding_rate = abs(market_data.get("funding_rate", 0.0))
        if funding_rate > 0.01:
            tail_score += 0.3
        
        return min(1.0, tail_score)
    
    def _determine_condition(self, overall_risk: float) -> MarketCondition:
        if overall_risk >= 0.8:
            return MarketCondition.CRISIS
        elif overall_risk >= 0.6:
            return MarketCondition.STRESS
        elif overall_risk >= 0.4:
            return MarketCondition.ELEVATED
        else:
            return MarketCondition.NORMAL
    
    def _recommend_actions(
        self,
        condition: MarketCondition,
        vol_risk: float,
        liq_risk: float,
    ) -> List[str]:
        actions = []
        
        if condition == MarketCondition.CRISIS:
            actions.append("Consider closing all positions")
            actions.append("Halt new trading activity")
        
        elif condition == MarketCondition.STRESS:
            actions.append("Reduce position sizes by 50%")
            actions.append("Avoid opening new positions")
        
        elif condition == MarketCondition.ELEVATED:
            actions.append("Monitor positions closely")
            actions.append("Reduce leverage if possible")
        
        if vol_risk > 0.7:
            actions.append("Volatility high - use tighter stops")
        
        if liq_risk > 0.7:
            actions.append("Liquidity low - reduce position sizes")
        
        return actions


def monitor_market_risk(
    market_data: Dict[str, Any],
    symbols: List[str],
    monitor: Optional[MarketRiskMonitor] = None,
) -> MarketRiskAssessment:
    monitor = monitor or MarketRiskMonitor()
    return monitor.assess(market_data, symbols)
