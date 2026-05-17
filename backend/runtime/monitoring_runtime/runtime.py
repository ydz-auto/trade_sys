"""
Monitoring Runtime - 监控服务运行时实现

系统健康检查和指标收集
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig, RuntimeState
from infrastructure.logging import get_logger
from infrastructure.observability import get_observability_manager


class MonitoringConfig(RuntimeConfig):
    """Monitoring Runtime 配置"""
    name: str = "monitoring_runtime"
    
    check_interval: int = 10
    alert_webhook: Optional[str] = None


class MonitoringRuntime(BaseRuntime):
    """
    Monitoring Runtime
    
    职责：
    1. 系统健康检查
    2. 指标收集
    3. 告警通知
    """
    
    def __init__(self, config: MonitoringConfig = None):
        config = config or MonitoringConfig.from_env()
        super().__init__(config)
        self.config: MonitoringConfig = config
        
        self.observability = None
        self.runtimes_status: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """初始化"""
        self.logger.info("Initializing Monitoring Runtime...")
        
        self.observability = get_observability_manager("monitoring_runtime")
        
        self.logger.info("Monitoring Runtime initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭"""
        self.logger.info("Shutting down Monitoring Runtime...")
        self.logger.info(f"Monitoring Runtime stopped. Stats: {self.context.stats}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Monitoring Runtime...")
        
        while not self.context.is_shutdown_requested():
            try:
                await self._collect_metrics()
                await self._check_health()
                await asyncio.sleep(self.config.check_interval)
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                self.context.record_error(str(e))
    
    async def _collect_metrics(self) -> None:
        """收集指标"""
        self.context.increment_stat("metrics_collected")
        
        if self.observability:
            self.observability.record_request("/health", "GET", 200, 0.1)
    
    async def _check_health(self) -> None:
        """健康检查"""
        self.context.increment_stat("health_checks")
        
        health = await self.health_check()
        
        if not health.get("healthy", False):
            self.logger.warning(f"Health check failed: {health}")
            self.context.increment_stat("health_failures")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "observability_ready": self.observability is not None,
        })
        return health


_monitoring_runtime: Optional[MonitoringRuntime] = None


def get_monitoring_runtime() -> MonitoringRuntime:
    """获取 Monitoring Runtime 单例"""
    global _monitoring_runtime
    if _monitoring_runtime is None:
        _monitoring_runtime = MonitoringRuntime()
    return _monitoring_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Monitoring Runtime - System Health & Metrics")
    print("=" * 60)
    
    runtime = get_monitoring_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
