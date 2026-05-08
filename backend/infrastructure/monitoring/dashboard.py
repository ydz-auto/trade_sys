"""
监控面板模块
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from infrastructure.monitoring.health import HealthChecker, ServiceStatus
from infrastructure.monitoring.metrics import MetricsCollector
from infrastructure.monitoring.alert import AlertManager, Alert


@dataclass
class SystemHealthData:
    overall_status: str
    services: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class TradingData:
    balance: float
    pnl: float
    pnl_percent: float
    positions_count: int
    total_exposure: float
    trades_today: int
    wins_today: int = 0
    losses_today: int = 0


@dataclass
class RiskData:
    risk_index: int
    risk_level: str
    max_drawdown: float
    daily_loss: float
    consecutive_losses: int


@dataclass
class DashboardData:
    system_health: SystemHealthData
    trading: TradingData
    risk: RiskData
    recent_alerts: List[Alert]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_health": {
                "overall_status": self.system_health.overall_status,
                "services": self.system_health.services,
                "timestamp": self.system_health.timestamp,
            },
            "trading": {
                "balance": self.trading.balance,
                "pnl_today": self.trading.pnl,
                "pnl_percent": self.trading.pnl_percent,
                "positions_count": self.trading.positions_count,
                "total_exposure": self.trading.total_exposure,
                "trades_today": self.trading.trades_today,
                "wins_today": self.trading.wins_today,
                "losses_today": self.trading.losses_today,
            },
            "risk": {
                "risk_index": self.risk.risk_index,
                "risk_level": self.risk.risk_level,
                "max_drawdown": self.risk.max_drawdown,
                "daily_loss": self.risk.daily_loss,
                "consecutive_losses": self.risk.consecutive_losses,
            },
            "recent_alerts": [a.to_dict() for a in self.recent_alerts],
            "timestamp": self.timestamp,
        }


class DashboardProvider:
    def __init__(
        self,
        health_checker: Optional[HealthChecker] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        alert_manager: Optional[AlertManager] = None,
    ):
        self.health_checker = health_checker
        self.metrics_collector = metrics_collector
        self.alert_manager = alert_manager
        self._custom_data_providers: Dict[str, callable] = {}

    def register_data_provider(self, name: str, provider: callable):
        self._custom_data_providers[name] = provider

    async def get_system_health(self) -> SystemHealthData:
        if not self.health_checker:
            return SystemHealthData(
                overall_status="UNKNOWN",
                services={},
            )

        status = await self.health_checker.get_overall_status()
        return SystemHealthData(
            overall_status=status.get("overall", "UNKNOWN"),
            services=status.get("services", {}),
        )

    async def get_trading_data(
        self,
        balance: float = 0,
        pnl: float = 0,
        positions_count: int = 0,
    ) -> TradingData:
        pnl_percent = (pnl / balance * 100) if balance > 0 else 0

        metrics_data = {}
        if self.metrics_collector:
            metrics_data = self.metrics_collector.get_all_metrics()

        trades_today = 0
        wins_today = 0
        losses_today = 0

        if "counters" in metrics_data:
            for key in metrics_data["counters"]:
                if "trades" in key:
                    trades_today = metrics_data["counters"][key]["value"]

        return TradingData(
            balance=balance,
            pnl=pnl,
            pnl_percent=pnl_percent,
            positions_count=positions_count,
            total_exposure=0,
            trades_today=int(trades_today),
            wins_today=wins_today,
            losses_today=losses_today,
        )

    async def get_risk_data(
        self,
        risk_index: int = 0,
        risk_level: str = "NORMAL",
        max_drawdown: float = 0,
        daily_loss: float = 0,
        consecutive_losses: int = 0,
    ) -> RiskData:
        return RiskData(
            risk_index=risk_index,
            risk_level=risk_level,
            max_drawdown=max_drawdown,
            daily_loss=daily_loss,
            consecutive_losses=consecutive_losses,
        )

    async def get_dashboard_data(
        self,
        trading_data: Optional[Dict] = None,
        risk_data: Optional[Dict] = None,
    ) -> DashboardData:
        system_health = await self.get_system_health()

        trading = await self.get_trading_data(
            balance=trading_data.get("balance", 0) if trading_data else 0,
            pnl=trading_data.get("pnl", 0) if trading_data else 0,
            positions_count=trading_data.get("positions_count", 0) if trading_data else 0,
        )

        risk = await self.get_risk_data(
            risk_index=risk_data.get("risk_index", 0) if risk_data else 0,
            risk_level=risk_data.get("risk_level", "NORMAL") if risk_data else "NORMAL",
            max_drawdown=risk_data.get("max_drawdown", 0) if risk_data else 0,
            daily_loss=risk_data.get("daily_loss", 0) if risk_data else 0,
            consecutive_losses=risk_data.get("consecutive_losses", 0) if risk_data else 0,
        )

        recent_alerts = []
        if self.alert_manager:
            recent_alerts = self.alert_manager.get_active_alerts()[-10:]

        return DashboardData(
            system_health=system_health,
            trading=trading,
            risk=risk,
            recent_alerts=recent_alerts,
        )

    async def get_json_dashboard(self, **kwargs) -> Dict[str, Any]:
        dashboard = await self.get_dashboard_data(**kwargs)
        return dashboard.to_dict()


_default_dashboard_provider = DashboardProvider()


def get_dashboard_provider() -> DashboardProvider:
    return _default_dashboard_provider