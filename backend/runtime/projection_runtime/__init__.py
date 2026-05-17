"""
Projection Runtime - CQRS 投影运行时

消费 Kafka 事件，投影到 Redis 状态

用法:
    python -m runtime.projection_runtime
"""

from runtime.projection_runtime.runtime import ProjectionRuntime, get_projection_runtime

__all__ = ["ProjectionRuntime", "get_projection_runtime"]
