"""
Runtime Layer - 统一的运行时层

所有 runtime 都遵循统一的 Runtime Contract：
- 统一的生命周期管理
- 统一的配置加载
- 统一的可观测性
- 统一的健康检查

Runtime 列表：
- ingestion_runtime: 数据采集 + 聚合
- projection_runtime: CQRS 投影
- signal_runtime: 信号生成
- execution_runtime: 订单执行
- replay_runtime: 回放引擎
- correlation_runtime: 多数据源相关性分析
- narrative_runtime: AI 叙事引擎
- monitoring_runtime: 监控服务
- scheduler_runtime: 定时调度
"""

from runtime.base import (
    BaseRuntime,
    RuntimeConfig,
    RuntimeState,
    RuntimeContext,
    get_runtime_context,
)

__all__ = [
    "BaseRuntime",
    "RuntimeConfig",
    "RuntimeState",
    "RuntimeContext",
    "get_runtime_context",
]
