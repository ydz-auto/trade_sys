import time
import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.monitoring.health import HealthChecker, ServiceStatus
from infrastructure.metrics.collector import MetricsCollector
from infrastructure.monitoring.alerting.sender import AlertManager, Alert
from infrastructure.observability.manager import get_observability_manager
from infrastructure.observability.service_registry import get_service_registry, ServiceStatus as ObsServiceStatus
from infrastructure.storage.data_quality import get_data_quality_checker

logger = get_logger("infrastructure.monitoring.dashboard")


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


@dataclass
class DashboardMetric:
    name: str
    value: Any
    unit: str = ""
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class DashboardPanel:
    title: str
    metrics: List[DashboardMetric]
    refresh_interval: int = 5000


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


class MonitoringDashboard:

    def __init__(self, service_name: str = "system"):
        self.service_name = service_name
        self.observability = get_observability_manager(service_name)
        self.registry = get_service_registry()
        self.quality_checker = get_data_quality_checker()

    async def get_system_overview(self) -> Dict[str, Any]:
        status = await self.observability.get_status()
        services = await self.registry.get_all_services()

        healthy_count = sum(1 for s in services if s.status == ObsServiceStatus.HEALTHY)
        unhealthy_count = len(services) - healthy_count

        return {
            "service": self.service_name,
            "status": status.get("status", "unknown"),
            "uptime_ms": status.get("uptime_ms", 0),
            "services": {
                "total": len(services),
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
        }

    async def get_metrics_panel(self) -> Dict[str, Any]:
        metrics = await self.observability.metrics.get_metrics()

        return {
            "title": "System Metrics",
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "type": m.type.value,
                    "labels": m.labels,
                    "timestamp": m.timestamp,
                }
                for m in metrics
            ],
            "prometheus": await self.observability.metrics.get_prometheus_format(),
        }

    async def get_health_panel(self) -> Dict[str, Any]:
        health = await self.observability.health_checker.check()

        checks = []
        for check_name, result in health.checks.items():
            checks.append({
                "name": check_name,
                "status": "pass" if result else "fail",
                "timestamp": health.timestamp,
            })

        return {
            "title": "Health Checks",
            "status": health.status,
            "checks": checks,
            "message": health.message,
        }

    async def get_services_panel(self) -> Dict[str, Any]:
        services = await self.registry.get_all_services()

        return {
            "title": "Services",
            "services": [
                {
                    "service_id": s.service_id,
                    "service_name": s.service_name,
                    "version": s.version,
                    "status": s.status.value,
                    "endpoints": [str(e) for e in s.endpoints],
                    "capabilities": s.capabilities,
                    "last_heartbeat": s.last_heartbeat,
                }
                for s in services
            ],
        }

    async def get_traces_panel(self, limit: int = 50) -> Dict[str, Any]:
        traces = await self.observability.tracer.get_traces(limit=limit)

        return {
            "title": "Recent Traces",
            "traces": [
                {
                    "span_id": t.span_id,
                    "trace_id": t.trace_id,
                    "name": t.name,
                    "service": t.service_name,
                    "duration_ms": t.duration_ms,
                    "start_time": t.start_time,
                    "events": t.events,
                }
                for t in traces
            ],
        }

    async def get_data_quality_panel(self) -> Dict[str, Any]:
        return {
            "title": "Data Quality",
            "status": "active",
            "thresholds": self.quality_checker._thresholds,
        }

    async def get_full_dashboard(self) -> Dict[str, Any]:
        return {
            "timestamp": int(datetime.now().timestamp() * 1000),
            "overview": await self.get_system_overview(),
            "metrics": await self.get_metrics_panel(),
            "health": await self.get_health_panel(),
            "services": await self.get_services_panel(),
            "traces": await self.get_traces_panel(),
            "data_quality": await self.get_data_quality_panel(),
        }


def create_dashboard_routes(dashboard: MonitoringDashboard) -> Dict[str, Any]:
    return {
        "/api/dashboard/overview": {
            "handler": dashboard.get_system_overview,
            "method": "GET",
        },
        "/api/dashboard/metrics": {
            "handler": dashboard.get_metrics_panel,
            "method": "GET",
        },
        "/api/dashboard/health": {
            "handler": dashboard.get_health_panel,
            "method": "GET",
        },
        "/api/dashboard/services": {
            "handler": dashboard.get_services_panel,
            "method": "GET",
        },
        "/api/dashboard/traces": {
            "handler": lambda: dashboard.get_traces_panel(),
            "method": "GET",
        },
        "/api/dashboard/full": {
            "handler": dashboard.get_full_dashboard,
            "method": "GET",
        },
    }


_default_dashboard_provider = DashboardProvider()
_dashboard: Optional[MonitoringDashboard] = None


def get_dashboard_provider() -> DashboardProvider:
    return _default_dashboard_provider


def get_dashboard(service_name: str = "system") -> MonitoringDashboard:
    global _dashboard
    if _dashboard is None:
        _dashboard = MonitoringDashboard(service_name)
    return _dashboard
