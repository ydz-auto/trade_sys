"""
Application Layer - 业务用例层

职责：
- 编排业务流程
- 协调 domain 对象
- 处理业务命令和查询
- 不包含任何基础设施代码

注意：这一层是纯业务逻辑，不依赖任何外部框架。

已删除的 Facade：
- BacktestService (移到 api层，直接用 RuntimeBus)
- ProjectionService (已被 runtime/projection_runtime 取代)
- CorrelationService (重定向到 services/correlation_service)
"""

__all__ = []
