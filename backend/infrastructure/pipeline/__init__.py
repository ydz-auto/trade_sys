"""
Unified Pipeline - 统一数据管道

提供弹性的数据采集、消费和处理能力

主要组件：
- UnifiedPublisher: 统一发布者（带熔断、降级、重试）
- UnifiedConsumer: 统一消费者（带熔断、降级、重试）
- DataPipeline: 端到端数据管道
- create_rss_pipeline: 创建 RSS 数据管道
- create_skill_pipeline: 创建 Skill 数据管道
"""

from .unified_pipeline import (
    DataSourceType,
    PipelineStatus,
    PipelineConfig,
    PipelineMetrics,
    UnifiedPublisher,
    UnifiedConsumer,
    DataPipeline,
    DataSource,
    create_rss_pipeline,
    create_skill_pipeline
)

__all__ = [
    "DataSourceType",
    "PipelineStatus",
    "PipelineConfig",
    "PipelineMetrics",
    "UnifiedPublisher",
    "UnifiedConsumer",
    "DataPipeline",
    "DataSource",
    "create_rss_pipeline",
    "create_skill_pipeline"
]
