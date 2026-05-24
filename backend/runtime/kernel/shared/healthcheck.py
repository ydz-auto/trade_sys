"""
Runtime Health Check - 统一的健康检查

所有 Runtime 共享的健康检查组件。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)


class RuntimeHealthCheck:
    """
    统一的 Runtime 健康检查
    
    职责：
    - 组件健康检查
    - 依赖健康检查
    - 健康状态聚合
    """
    
    def __init__(self, name: str):
        self.name = name
        self._checks: Dict[str, Callable] = {}
        self._dependencies: Dict[str, Callable] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
    
    def register_check(self, name: str, check: Callable) -> None:
        """注册健康检查"""
        self._checks[name] = check
    
    def register_dependency(self, name: str, check: Callable) -> None:
        """注册依赖检查"""
        self._dependencies[name] = check
    
    async def run_check(self, name: str) -> HealthCheckResult:
        """运行单个检查"""
        check = self._checks.get(name)
        if not check:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message="Check not found",
            )
        
        try:
            if asyncio.iscoroutinefunction(check):
                result = await check()
            else:
                result = check()
            
            if isinstance(result, HealthCheckResult):
                self._last_results[name] = result
                return result
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                result = HealthCheckResult(
                    name=name,
                    status=status,
                    message="OK" if result else "Failed",
                )
                self._last_results[name] = result
                return result
            else:
                result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message="OK",
                    details=result if isinstance(result, dict) else {},
                )
                self._last_results[name] = result
                return result
                
        except Exception as e:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
            self._last_results[name] = result
            return result
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """运行所有检查"""
        results = {}
        
        for name in self._checks:
            results[name] = await self.run_check(name)
        
        for name in self._dependencies:
            results[name] = await self.run_check(name)
        
        return results
    
    async def get_aggregate_status(self) -> HealthStatus:
        """获取聚合状态"""
        results = await self.run_all_checks()
        
        if not results:
            return HealthStatus.HEALTHY
        
        statuses = [r.status for r in results.values()]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    async def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        results = await self.run_all_checks()
        aggregate = await self.get_aggregate_status()
        
        return {
            "name": self.name,
            "status": aggregate.value,
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                    "checked_at": result.checked_at.isoformat(),
                }
                for name, result in results.items()
            },
        }
