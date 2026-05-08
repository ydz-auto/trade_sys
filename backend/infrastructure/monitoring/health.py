"""
健康检查模块
"""

import time
import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ServiceStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class HealthCheckResult:
    service_name: str
    status: ServiceStatus
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service_name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class HealthCheckStrategy:
    async def check(self) -> HealthCheckResult:
        raise NotImplementedError


class HTTPHealthCheck(HealthCheckStrategy):
    def __init__(
        self,
        name: str,
        url: str,
        timeout: float = 5.0,
        expected_status: int = 200,
    ):
        self.name = name
        self.url = url
        self.timeout = timeout
        self.expected_status = expected_status

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == self.expected_status:
                    status = ServiceStatus.OK
                    error = None
                else:
                    status = ServiceStatus.DEGRADED
                    error = f"Unexpected status: {response.status_code}"

                return HealthCheckResult(
                    service_name=self.name,
                    status=status,
                    latency_ms=latency_ms,
                    error=error,
                    details={"status_code": response.status_code},
                )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=self.name,
                status=ServiceStatus.DOWN,
                latency_ms=latency_ms,
                error=str(e),
            )


class TCPHealthCheck(HealthCheckStrategy):
    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        timeout: float = 5.0,
    ):
        self.name = name
        self.host = host
        self.port = port
        self.timeout = timeout

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            import asyncio

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            writer.close()
            await writer.wait_closed()
            latency_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                service_name=self.name,
                status=ServiceStatus.OK,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=self.name,
                status=ServiceStatus.DOWN,
                latency_ms=latency_ms,
                error=str(e),
            )


class FunctionHealthCheck(HealthCheckStrategy):
    def __init__(
        self,
        name: str,
        check_func: Callable[[], bool],
        details_func: Optional[Callable[[], Dict]] = None,
    ):
        self.name = name
        self.check_func = check_func
        self.details_func = details_func

    async def check(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            result = self.check_func()
            latency_ms = (time.time() - start_time) * 1000

            if result:
                status = ServiceStatus.OK
            else:
                status = ServiceStatus.DOWN

            details = {}
            if self.details_func:
                details = self.details_func()

            return HealthCheckResult(
                service_name=self.name,
                status=status,
                latency_ms=latency_ms,
                details=details,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=self.name,
                status=ServiceStatus.DOWN,
                latency_ms=latency_ms,
                error=str(e),
            )


class HealthChecker:
    def __init__(self):
        self.checks: Dict[str, HealthCheckStrategy] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}
        self._on_status_change: Optional[Callable] = None

    def register_check(self, name: str, check: HealthCheckStrategy):
        self.checks[name] = check

    def unregister_check(self, name: str):
        if name in self.checks:
            del self.checks[name]

    def set_status_change_callback(self, callback: Callable):
        self._on_status_change = callback

    async def check_service(self, name: str) -> HealthCheckResult:
        if name not in self.checks:
            return HealthCheckResult(
                service_name=name,
                status=ServiceStatus.UNKNOWN,
                error="No check registered",
            )

        check = self.checks[name]
        result = await check.check()

        old_result = self.last_results.get(name)
        if old_result and old_result.status != result.status:
            if self._on_status_change:
                self._on_status_change(name, old_result.status, result.status)

        self.last_results[name] = result
        return result

    async def check_all(self) -> Dict[str, HealthCheckResult]:
        results = {}
        for name in self.checks:
            results[name] = await self.check_service(name)
        return results

    async def get_overall_status(self) -> Dict[str, Any]:
        results = await self.check_all()

        if not results:
            overall = ServiceStatus.UNKNOWN
        elif any(r.status == ServiceStatus.DOWN for r in results.values()):
            overall = ServiceStatus.DOWN
        elif any(r.status == ServiceStatus.DEGRADED for r in results.values()):
            overall = ServiceStatus.DEGRADED
        else:
            overall = ServiceStatus.OK

        return {
            "overall": overall.value,
            "services": {name: r.to_dict() for name, r in results.items()},
            "timestamp": time.time(),
        }


class ServiceHealthCheck:
    def __init__(self, health_checker: Optional[HealthChecker] = None):
        self.health_checker = health_checker or HealthChecker()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_http_check(self, name: str, url: str, **kwargs):
        check = HTTPHealthCheck(name, url, **kwargs)
        self.health_checker.register_check(name, check)

    def add_tcp_check(self, name: str, host: str, port: int, **kwargs):
        check = TCPHealthCheck(name, host, port, **kwargs)
        self.health_checker.register_check(name, check)

    def add_function_check(
        self,
        name: str,
        check_func: Callable,
        details_func: Optional[Callable] = None,
    ):
        check = FunctionHealthCheck(name, check_func, details_func)
        self.health_checker.register_check(name, check)

    async def get_status(self) -> Dict[str, Any]:
        return await self.health_checker.get_overall_status()

    async def start_periodic_check(self, interval: float = 30.0):
        self._running = True
        while self._running:
            await self.health_checker.check_all()
            await asyncio.sleep(interval)

    def stop_periodic_check(self):
        self._running = False
        if self._task:
            self._task.cancel()


_default_health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    return _default_health_checker