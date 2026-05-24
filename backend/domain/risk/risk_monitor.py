"""
Risk Monitor - 风险监控

综合风险监控:
1. 实时风险监控
2. 告警系统
3. 自动保护
4. 风险报告
"""
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from .position_risk import PositionRiskCalculator, PositionRisk
from .portfolio_risk import PortfolioRiskCalculator, PortfolioRisk
from .market_risk import MarketRiskMonitor, MarketRiskAssessment
from .limit_manager import LimitManager, LimitCheckResult

import logging

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class RiskAlert:
    timestamp: datetime
    level: AlertLevel
    source: str
    message: str
    
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskStatus:
    timestamp: datetime
    
    position_risks: Dict[str, PositionRisk]
    portfolio_risk: PortfolioRisk
    market_risk: MarketRiskAssessment
    limit_check: LimitCheckResult
    
    overall_risk_score: float
    
    alerts: List[RiskAlert]
    
    is_trading_allowed: bool
    recommended_actions: List[str]


class RiskMonitor:
    def __init__(
        self,
        position_calculator: Optional[PositionRiskCalculator] = None,
        portfolio_calculator: Optional[PortfolioRiskCalculator] = None,
        market_monitor: Optional[MarketRiskMonitor] = None,
        limit_manager: Optional[LimitManager] = None,
    ):
        self._position_calc = position_calculator or PositionRiskCalculator()
        self._portfolio_calc = portfolio_calculator or PortfolioRiskCalculator()
        self._market_monitor = market_monitor or MarketRiskMonitor()
        self._limit_manager = limit_manager or LimitManager()
        
        self._alert_handlers: List[Callable] = []
        self._alerts: List[RiskAlert] = []
        self._max_alerts = 100
        
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("RiskMonitor initialized")
    
    async def start(self) -> None:
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("RiskMonitor started")
    
    async def stop(self) -> None:
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("RiskMonitor stopped")
    
    async def _monitor_loop(self) -> None:
        while self._is_running:
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
    
    def assess(
        self,
        positions: List[Dict[str, Any]],
        account_balance: float,
        peak_balance: float,
        market_data: Dict[str, Any],
        correlations: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> RiskStatus:
        timestamp = datetime.now()
        
        position_risks = {}
        for pos in positions:
            symbol = pos.get("symbol", "unknown")
            risk = self._position_calc.calculate(
                symbol=symbol,
                position_size=pos.get("size", 0),
                entry_price=pos.get("entry_price", 0),
                current_price=pos.get("current_price", 0),
                leverage=pos.get("leverage", 1),
                account_balance=account_balance,
                volatility=pos.get("volatility", 0.02),
                position_side=pos.get("side", "long"),
            )
            position_risks[symbol] = risk
        
        portfolio_risk = self._portfolio_calc.calculate(
            positions, account_balance, correlations
        )
        
        symbols = [p.get("symbol", "") for p in positions]
        market_risk = self._market_monitor.assess(market_data, symbols)
        
        gross_exposure = sum(abs(p.get("value", 0)) for p in positions)
        max_position = max((abs(p.get("size", 0)) for p in positions), default=0)
        max_leverage = max((p.get("leverage", 1) for p in positions), default=1)
        
        limit_check = self._limit_manager.check(
            position_size=max_position,
            position_value=gross_exposure,
            leverage=max_leverage,
            account_balance=account_balance,
            peak_balance=peak_balance,
            gross_exposure=gross_exposure,
        )
        
        overall_score = self._calculate_overall_score(
            position_risks, portfolio_risk, market_risk, limit_check
        )
        
        alerts = self._generate_alerts(
            position_risks, portfolio_risk, market_risk, limit_check
        )
        
        for alert in alerts:
            self._alerts.append(alert)
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Alert handler error: {e}")
        
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]
        
        can_trade = (
            limit_check.can_trade and
            market_risk.condition.value in ["normal", "elevated"] and
            overall_score < 0.8
        )
        
        actions = self._compile_actions(
            market_risk, limit_check, alerts
        )
        
        return RiskStatus(
            timestamp=timestamp,
            position_risks=position_risks,
            portfolio_risk=portfolio_risk,
            market_risk=market_risk,
            limit_check=limit_check,
            overall_risk_score=overall_score,
            alerts=alerts,
            is_trading_allowed=can_trade,
            recommended_actions=actions,
        )
    
    def _calculate_overall_score(
        self,
        position_risks: Dict[str, PositionRisk],
        portfolio_risk: PortfolioRisk,
        market_risk: MarketRiskAssessment,
        limit_check: LimitCheckResult,
    ) -> float:
        scores = []
        
        if position_risks:
            pos_scores = [r.risk_score for r in position_risks.values()]
            scores.append(max(pos_scores))
        
        scores.append(portfolio_risk.risk_score)
        scores.append(market_risk.overall_risk)
        
        if limit_check.any_breach:
            scores.append(1.0)
        elif limit_check.any_warning:
            scores.append(0.6)
        
        return max(scores) if scores else 0.0
    
    def _generate_alerts(
        self,
        position_risks: Dict[str, PositionRisk],
        portfolio_risk: PortfolioRisk,
        market_risk: MarketRiskAssessment,
        limit_check: LimitCheckResult,
    ) -> List[RiskAlert]:
        alerts = []
        now = datetime.now()
        
        for symbol, risk in position_risks.items():
            if risk.risk_level.value == "critical":
                alerts.append(RiskAlert(
                    timestamp=now,
                    level=AlertLevel.CRITICAL,
                    source="position",
                    message=f"Critical risk for {symbol}",
                    details={"symbol": symbol, "score": risk.risk_score},
                ))
            elif risk.risk_level.value == "high":
                alerts.append(RiskAlert(
                    timestamp=now,
                    level=AlertLevel.WARNING,
                    source="position",
                    message=f"High risk for {symbol}",
                    details={"symbol": symbol, "score": risk.risk_score},
                ))
        
        if portfolio_risk.risk_score > 0.7:
            alerts.append(RiskAlert(
                timestamp=now,
                level=AlertLevel.WARNING,
                source="portfolio",
                message="High portfolio risk",
                details={"score": portfolio_risk.risk_score},
            ))
        
        if market_risk.condition.value in ["crisis", "stress"]:
            alerts.append(RiskAlert(
                timestamp=now,
                level=AlertLevel.ERROR if market_risk.condition.value == "crisis" else AlertLevel.WARNING,
                source="market",
                message=f"Market condition: {market_risk.condition.value}",
                details={"overall_risk": market_risk.overall_risk},
            ))
        
        for limit_type in limit_check.breached_limits:
            alerts.append(RiskAlert(
                timestamp=now,
                level=AlertLevel.ERROR,
                source="limit",
                message=f"Limit breached: {limit_type.value}",
                details={"limit_type": limit_type.value},
            ))
        
        return alerts
    
    def _compile_actions(
        self,
        market_risk: MarketRiskAssessment,
        limit_check: LimitCheckResult,
        alerts: List[RiskAlert],
    ) -> List[str]:
        actions = []
        
        actions.extend(market_risk.recommended_actions)
        
        if not limit_check.can_trade:
            actions.append(limit_check.recommended_action)
        
        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        if critical_alerts:
            actions.append("Critical alerts detected - review immediately")
        
        return list(set(actions))
    
    def on_alert(self, handler: Callable) -> None:
        self._alert_handlers.append(handler)
    
    def get_recent_alerts(self, limit: int = 20) -> List[RiskAlert]:
        return self._alerts[-limit:]
    
    def get_summary(self, status: RiskStatus) -> Dict[str, Any]:
        return {
            "timestamp": status.timestamp.isoformat(),
            "overall_risk_score": status.overall_risk_score,
            "is_trading_allowed": status.is_trading_allowed,
            "position_count": len(status.position_risks),
            "portfolio": {
                "leverage": status.portfolio_risk.leverage_ratio,
                "var_95": status.portfolio_risk.var_95,
                "risk_score": status.portfolio_risk.risk_score,
            },
            "market": {
                "condition": status.market_risk.condition.value,
                "volatility_risk": status.market_risk.volatility_risk,
                "liquidity_risk": status.market_risk.liquidity_risk,
            },
            "limits": {
                "all_passed": status.limit_check.all_passed,
                "breached": [l.value for l in status.limit_check.breached_limits],
            },
            "alerts_count": len(status.alerts),
            "recommended_actions": status.recommended_actions,
        }
