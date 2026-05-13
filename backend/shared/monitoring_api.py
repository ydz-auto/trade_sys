"""
Monitoring Dashboard API - 监控面板 API
提供实时监控数据的 HTTP 接口
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json

from infrastructure.logging import get_logger
from shared.observability import get_observability_manager
from shared.service_registry import get_service_registry, ServiceStatus
from shared.data_quality import get_data_quality_checker

logger = get_logger("shared.monitoring_api")


@dataclass
class DashboardMetric:
    """面板指标"""
    name: str
    value: Any
    unit: str = ""
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class DashboardPanel:
    """面板"""
    title: str
    metrics: List[DashboardMetric]
    refresh_interval: int = 5000


class MonitoringDashboard:
    """监控面板"""
    
    def __init__(self, service_name: str = "system"):
        self.service_name = service_name
        self.observability = get_observability_manager(service_name)
        self.registry = get_service_registry()
        self.quality_checker = get_data_quality_checker()
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """获取系统概览"""
        status = await self.observability.get_status()
        services = await self.registry.get_all_services()
        
        healthy_count = sum(1 for s in services if s.status == ServiceStatus.HEALTHY)
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
        """获取指标面板"""
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
        """获取健康面板"""
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
        """获取服务面板"""
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
        """获取追踪面板"""
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
        """获取数据质量面板"""
        return {
            "title": "Data Quality",
            "status": "active",
            "thresholds": self.quality_checker._thresholds,
        }
    
    async def get_full_dashboard(self) -> Dict[str, Any]:
        """获取完整面板"""
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
    """创建路由配置"""
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


_dashboard: Optional[MonitoringDashboard] = None


def get_dashboard(service_name: str = "system") -> MonitoringDashboard:
    """获取监控面板"""
    global _dashboard
    if _dashboard is None:
        _dashboard = MonitoringDashboard(service_name)
    return _dashboard
