"""
Risk Service - 风控业务服务

职责：
- 风控规则逻辑
- 风险评估逻辑
- 告警生成逻辑

注意：这是纯业务逻辑，不包含任何基础设施代码。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    """风险评估结果"""
    level: RiskLevel
    score: float
    factors: Dict[str, float]
    warnings: List[str]
    timestamp: datetime


class RiskFactorEvaluator:
    """风险因子评估器 - 纯业务逻辑"""
    
    def evaluate_position_risk(
        self,
        positions: List[Dict[str, Any]],
        max_positions: int = 5,
    ) -> float:
        """评估仓位风险"""
        if len(positions) > max_positions:
            return 1.0
        return len(positions) / max_positions
    
    def evaluate_leverage_risk(
        self,
        leverage: int,
        max_leverage: int = 5,
    ) -> float:
        """评估杠杆风险"""
        if leverage > max_leverage:
            return 1.0
        return leverage / max_leverage
    
    def evaluate_drawdown_risk(
        self,
        drawdown: float,
        max_drawdown: float = 0.1,
    ) -> float:
        """评估回撤风险"""
        if abs(drawdown) > max_drawdown:
            return 1.0
        return abs(drawdown) / max_drawdown
    
    def evaluate_volatility_risk(
        self,
        volatility: float,
        threshold: float = 0.5,
    ) -> float:
        """评估波动率风险"""
        if volatility > threshold:
            return 1.0
        return volatility / threshold


class RiskService:
    """
    Risk Service - 风控业务服务
    
    编排风险评估和告警生成的完整流程。
    这是纯业务逻辑层，不包含任何基础设施代码。
    """
    
    def __init__(
        self,
        max_positions: int = 5,
        max_leverage: int = 5,
        max_drawdown: float = 0.1,
    ):
        self.evaluator = RiskFactorEvaluator()
        self.max_positions = max_positions
        self.max_leverage = max_leverage
        self.max_drawdown = max_drawdown
    
    def assess(
        self,
        positions: List[Dict[str, Any]] = None,
        leverage: int = 1,
        drawdown: float = 0,
        volatility: float = 0,
    ) -> RiskAssessment:
        """
        执行风险评估（纯业务逻辑）
        
        这是业务用例的入口点，编排整个业务流程。
        """
        positions = positions or []
        
        factors = {
            "position": self.evaluator.evaluate_position_risk(
                positions, self.max_positions
            ),
            "leverage": self.evaluator.evaluate_leverage_risk(
                leverage, self.max_leverage
            ),
            "drawdown": self.evaluator.evaluate_drawdown_risk(
                drawdown, self.max_drawdown
            ),
            "volatility": self.evaluator.evaluate_volatility_risk(volatility),
        }
        
        score = sum(factors.values()) / len(factors)
        
        warnings = []
        if factors["position"] > 0.8:
            warnings.append(f"仓位风险过高: {len(positions)}/{self.max_positions}")
        if factors["leverage"] > 0.8:
            warnings.append(f"杠杆风险过高: {leverage}x")
        if factors["drawdown"] > 0.8:
            warnings.append(f"回撤风险过高: {drawdown:.2%}")
        if factors["volatility"] > 0.8:
            warnings.append(f"波动率风险过高: {volatility:.2%}")
        
        if score >= 0.8:
            level = RiskLevel.CRITICAL
        elif score >= 0.6:
            level = RiskLevel.HIGH
        elif score >= 0.4:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW
        
        return RiskAssessment(
            level=level,
            score=score,
            factors=factors,
            warnings=warnings,
            timestamp=datetime.now(),
        )
