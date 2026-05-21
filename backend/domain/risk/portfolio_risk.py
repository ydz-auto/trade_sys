"""
Portfolio Risk - 组合风险

计算整体组合风险:
1. 总风险敞口
2. 相关性风险
3. 集中度风险
4. 整体 VaR
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("risk.portfolio_risk")


@dataclass
class PortfolioRisk:
    total_value: float
    total_margin: float
    
    gross_exposure: float
    net_exposure: float
    
    leverage_ratio: float
    
    var_95: float
    var_99: float
    
    concentration_score: float
    correlation_risk: float
    
    diversification_ratio: float
    
    risk_score: float
    
    positions_at_risk: List[str]
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioRiskCalculator:
    confidence_95: float = 1.645
    confidence_99: float = 2.326
    
    max_concentration: float = 0.3
    
    def calculate(
        self,
        positions: List[Dict[str, Any]],
        account_balance: float,
        correlations: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> PortfolioRisk:
        if not positions:
            return self._empty_risk(account_balance)
        
        total_value = sum(abs(p.get("value", 0)) for p in positions)
        total_margin = sum(p.get("margin", 0) for p in positions)
        
        long_value = sum(p.get("value", 0) for p in positions if p.get("side") == "long")
        short_value = sum(abs(p.get("value", 0)) for p in positions if p.get("side") == "short")
        
        gross_exposure = long_value + short_value
        net_exposure = long_value - short_value
        
        leverage_ratio = gross_exposure / account_balance if account_balance > 0 else 0.0
        
        var_95, var_99 = self._calculate_portfolio_var(
            positions, correlations
        )
        
        concentration_score = self._calculate_concentration(positions, total_value)
        
        correlation_risk = self._calculate_correlation_risk(
            positions, correlations
        )
        
        div_ratio = self._calculate_diversification_ratio(
            positions, correlations
        )
        
        risk_score = self._calculate_risk_score(
            leverage_ratio, concentration_score, correlation_risk
        )
        
        positions_at_risk = self._identify_risky_positions(positions)
        
        return PortfolioRisk(
            total_value=total_value,
            total_margin=total_margin,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            leverage_ratio=leverage_ratio,
            var_95=var_95,
            var_99=var_99,
            concentration_score=concentration_score,
            correlation_risk=correlation_risk,
            diversification_ratio=div_ratio,
            risk_score=risk_score,
            positions_at_risk=positions_at_risk,
        )
    
    def _calculate_portfolio_var(
        self,
        positions: List[Dict[str, Any]],
        correlations: Optional[Dict[str, Dict[str, float]]],
    ) -> tuple:
        if not positions:
            return 0.0, 0.0
        
        variances = []
        for p in positions:
            value = abs(p.get("value", 0))
            vol = p.get("volatility", 0.02)
            daily_var = (value * vol / np.sqrt(365)) ** 2
            variances.append(daily_var)
        
        if correlations:
            for i, p1 in enumerate(positions):
                for j, p2 in enumerate(positions):
                    if i < j:
                        s1, s2 = p1.get("symbol", ""), p2.get("symbol", "")
                        corr = correlations.get(s1, {}).get(s2, 0.0)
                        cov = corr * np.sqrt(variances[i] * variances[j])
                        variances.append(2 * cov)
        
        total_variance = sum(variances)
        portfolio_std = np.sqrt(total_variance)
        
        var_95 = portfolio_std * self.confidence_95
        var_99 = portfolio_std * self.confidence_99
        
        return var_95, var_99
    
    def _calculate_concentration(
        self,
        positions: List[Dict[str, Any]],
        total_value: float,
    ) -> float:
        if total_value <= 0:
            return 0.0
        
        weights = [abs(p.get("value", 0)) / total_value for p in positions]
        
        herfindahl = sum(w ** 2 for w in weights)
        
        max_weight = max(weights) if weights else 0.0
        
        return 0.5 * herfindahl + 0.5 * max_weight
    
    def _calculate_correlation_risk(
        self,
        positions: List[Dict[str, Any]],
        correlations: Optional[Dict[str, Dict[str, float]]],
    ) -> float:
        if not correlations or len(positions) < 2:
            return 0.0
        
        high_corr_pairs = 0
        total_pairs = 0
        
        for i, p1 in enumerate(positions):
            for j, p2 in enumerate(positions):
                if i < j:
                    s1, s2 = p1.get("symbol", ""), p2.get("symbol", "")
                    corr = correlations.get(s1, {}).get(s2, 0.0)
                    total_pairs += 1
                    if abs(corr) > 0.7:
                        high_corr_pairs += 1
        
        return high_corr_pairs / total_pairs if total_pairs > 0 else 0.0
    
    def _calculate_diversification_ratio(
        self,
        positions: List[Dict[str, Any]],
        correlations: Optional[Dict[str, Dict[str, float]]],
    ) -> float:
        if len(positions) < 2:
            return 1.0
        
        individual_risks = [
            abs(p.get("value", 0)) * p.get("volatility", 0.02) / np.sqrt(365)
            for p in positions
        ]
        sum_individual = sum(individual_risks)
        
        var_95, _ = self._calculate_portfolio_var(positions, correlations)
        portfolio_risk = var_95 / self.confidence_95
        
        if portfolio_risk <= 0:
            return 1.0
        
        return sum_individual / portfolio_risk
    
    def _calculate_risk_score(
        self,
        leverage: float,
        concentration: float,
        corr_risk: float,
    ) -> float:
        score = 0.0
        
        if leverage > 10:
            score += 0.4
        elif leverage > 5:
            score += 0.2
        
        if concentration > 0.5:
            score += 0.3
        elif concentration > 0.3:
            score += 0.15
        
        if corr_risk > 0.5:
            score += 0.3
        elif corr_risk > 0.3:
            score += 0.15
        
        return min(1.0, score)
    
    def _identify_risky_positions(
        self,
        positions: List[Dict[str, Any]],
    ) -> List[str]:
        risky = []
        
        for p in positions:
            leverage = p.get("leverage", 1)
            pnl_pct = p.get("unrealized_pnl_pct", 0)
            
            if leverage > 10 or pnl_pct < -0.3:
                risky.append(p.get("symbol", "unknown"))
        
        return risky
    
    def _empty_risk(self, balance: float) -> PortfolioRisk:
        return PortfolioRisk(
            total_value=0.0,
            total_margin=0.0,
            gross_exposure=0.0,
            net_exposure=0.0,
            leverage_ratio=0.0,
            var_95=0.0,
            var_99=0.0,
            concentration_score=0.0,
            correlation_risk=0.0,
            diversification_ratio=1.0,
            risk_score=0.0,
            positions_at_risk=[],
        )


def calculate_portfolio_risk(
    positions: List[Dict[str, Any]],
    account_balance: float,
    correlations: Optional[Dict[str, Dict[str, float]]] = None,
    calculator: Optional[PortfolioRiskCalculator] = None,
) -> PortfolioRisk:
    calculator = calculator or PortfolioRiskCalculator()
    return calculator.calculate(positions, account_balance, correlations)
