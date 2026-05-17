"""
Monitoring Runtime - 监控服务运行时

职责：
1. 系统健康检查
2. 指标收集
3. 告警通知

用法:
    python -m runtime.monitoring_runtime
"""

from runtime.monitoring_runtime.runtime import MonitoringRuntime, get_monitoring_runtime

__all__ = ["MonitoringRuntime", "get_monitoring_runtime"]
