"""
Position Risk - 仓位风险

计算单个仓位风险:
1. VaR 计算
2. 风险敞口
3. 杠杆风险
4. 爆仓风险
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("risk.position_risk")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PositionRisk:
    symbol: str
    position_size: float
    position_value: float
    entry_price: float
    current_price: float
    
    unrealized_pnl: float
    unrealized_pnl_pct: float
    
    leverage: float
    margin_used: float
    
    var_95: float
    var_99: float
    
    liquidation_price: float
    distance_to_liquidation_pct: float
    
    risk_score: float
    risk_level: RiskLevel
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionRiskCalculator:
    maintenance_margin_rate: float = 0.005
    confidence_95: float = 1.645
    confidence_99: float = 2.326
    
    def calculate(
        self,
        symbol: str,
        position_size: float,
        entry_price: float,
        current_price: float,
        leverage: float,
        account_balance: float,
        volatility: float,
        position_side: str = "long",
    ) -> PositionRisk:
        position_value = abs(position_size) * current_price
        margin_used = position_value / leverage
        
        if position_side == "long":
            unrealized_pnl = (current_price - entry_price) * position_size
            liq_price = entry_price * (1 - (1 / leverage) + self.maintenance_margin_rate)
        else:
            unrealized_pnl = (entry_price - current_price) * abs(position_size)
            liq_price = entry_price * (1 + (1 / leverage) - self.maintenance_margin_rate)
        
        unrealized_pnl_pct = unrealized_pnl / (position_value / leverage) if position_value > 0 else 0.0
        
        daily_vol = volatility / np.sqrt(365)
        
        var_95 = position_value * daily_vol * self.confidence_95
        var_99 = position_value * daily_vol * self.confidence_99
        
        if position_side == "long":
            if current_price <= liq_price:
                distance_pct = 0.0
            else:
                distance_pct = (current_price - liq_price) / current_price
        else:
            if current_price >= liq_price:
                distance_pct = 0.0
            else:
                distance_pct = (liq_price - current_price) / current_price
        
        risk_score = self._calculate_risk_score(
            leverage, distance_pct, abs(unrealized_pnl_pct), volatility
        )
        
        risk_level = self._determine_risk_level(risk_score)
        
        return PositionRisk(
            symbol=symbol,
            position_size=position_size,
            position_value=position_value,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            leverage=leverage,
            margin_used=margin_used,
            var_95=var_95,
            var_99=var_99,
            liquidation_price=liq_price,
            distance_to_liquidation_pct=distance_pct,
            risk_score=risk_score,
            risk_level=risk_level,
        )
    
    def _calculate_risk_score(
        self,
        leverage: float,
        distance_pct: float,
        pnl_pct: float,
        volatility: float,
    ) -> float:
        score = 0.0
        
        if leverage > 20:
            score += 0.4
        elif leverage > 10:
            score += 0.2
        elif leverage > 5:
            score += 0.1
        
        if distance_pct < 0.05:
            score += 0.4
        elif distance_pct < 0.1:
            score += 0.2
        elif distance_pct < 0.2:
            score += 0.1
        
        if pnl_pct < -0.5:
            score += 0.2
        
        if volatility > 0.1:
            score += 0.1
        
        return min(1.0, score)
    
    def _determine_risk_level(self, score: float) -> RiskLevel:
        if score < 0.3:
            return RiskLevel.LOW
        elif score < 0.5:
            return RiskLevel.MEDIUM
        elif score < 0.7:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL


def calculate_position_risk(
    symbol: str,
    position_size: float,
    entry_price: float,
    current_price: float,
    leverage: float,
    account_balance: float,
    volatility: float,
    position_side: str = "long",
    calculator: Optional[PositionRiskCalculator] = None,
) -> PositionRisk:
    calculator = calculator or PositionRiskCalculator()
    return calculator.calculate(
        symbol, position_size, entry_price, current_price,
        leverage, account_balance, volatility, position_side
    )
