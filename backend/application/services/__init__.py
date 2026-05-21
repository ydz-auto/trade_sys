"""
Application Services - 业务服务层

这些服务负责业务逻辑编排，不包含任何运行时代码。
"""

from application.services.signal_service import SignalService
from application.services.execution_service import ExecutionService
from application.services.projection_service import ProjectionService
from application.services.risk_service import RiskService

try:
    from services.correlation_service import CorrelationWorker
    CorrelationService = CorrelationWorker
except ImportError:
    CorrelationService = None

__all__ = [
    "SignalService",
    "ExecutionService",
    "ProjectionService",
    "RiskService",
]
