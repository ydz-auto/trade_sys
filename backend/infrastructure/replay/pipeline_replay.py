"""
Low-level pipeline replay data primitives. High-level replay orchestration belongs in runtime.replay_runtime.

Data structures only:
- PipelineReplayConfig: 全链路回放配置
- PipelineReplayResult: 全链路回放结果
- PIPELINE_STAGES: pipeline 阶段定义
- STAGE_EVENT_TYPE_MAP: 阶段到事件类型的映射

State management and orchestration (replay_single_event, register_stage_handler, etc.) belong in runtime.replay_runtime.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from infrastructure.messaging.schema.canonical import EventType


PIPELINE_STAGES = [
    "raw_data",
    "aggregation",
    "event_extraction",
    "signal_fusion",
    "strategy_decision",
    "risk_check",
    "execution",
    "fill",
]

STAGE_EVENT_TYPE_MAP = {
    "raw_data": EventType.RAW_DATA,
    "aggregation": EventType.MARKET,
    "event_extraction": EventType.EVENT,
    "signal_fusion": EventType.SIGNAL,
    "strategy_decision": EventType.DECISION,
    "risk_check": EventType.RISK_CHECKED,
    "execution": EventType.ORDER,
    "fill": EventType.FILL,
}


@dataclass
class PipelineReplayConfig:
    start_time: int
    end_time: int
    symbols: List[str]
    exchanges: List[str]
    start_stage: str = "raw_data"
    end_stage: str = "fill"
    speed: float = 1.0
    batch_size: int = 1000
    enable_deterministic: bool = True
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineReplayResult:
    session_id: str
    events_replayed: int
    stages_completed: List[str]
    output_events: List[Dict]
    duration_ms: int
    is_deterministic: bool
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "events_replayed": self.events_replayed,
            "stages_completed": self.stages_completed,
            "output_events": self.output_events,
            "duration_ms": self.duration_ms,
            "is_deterministic": self.is_deterministic,
            "errors": self.errors,
        }
