"""
Correlation Service - 相关性分析业务服务（已废弃）

重要：这个模块已经重定位为 services/correlation_service/

请使用：
    from services.correlation_service import CorrelationWorker, get_correlation_service
    from services.correlation_service.strategy_adapter import get_correlation_adapter

核心类型定义已移至：
    from domain.analysis import SignalDirection
"""

from domain.analysis import SignalDirection

__all__ = ["SignalDirection"]
