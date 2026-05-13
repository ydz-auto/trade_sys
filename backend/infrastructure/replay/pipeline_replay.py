"""
Pipeline Replay Engine - 全链路事件回放引擎
从raw_data到fill的完整pipeline回放
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.canonical import (
    BaseEvent,
    EventType,
    EventSource,
    generate_trace_id,
    generate_event_id,
)

logger = get_logger("infrastructure.replay.pipeline_replay")


@dataclass
class PipelineReplayConfig:
    """全链路回放配置"""

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
    """全链路回放结果"""

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


class PipelineReplayEngine:
    """全链路事件回放引擎

    能力：
    1. 从raw_data到fill的完整pipeline回放
    2. 支持任意阶段开始回放
    3. 支持回放速度控制
    4. 支持回放过滤（只回放特定symbol/exchange的事件）
    """

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

    def __init__(self, event_store=None, clickhouse_manager=None):
        self.event_store = event_store
        self.clickhouse_manager = clickhouse_manager
        self._handlers: Dict[str, List[Callable]] = {}
        self._pipeline_stages = list(self.PIPELINE_STAGES)
        self._running_sessions: Dict[str, bool] = {}

    async def replay_pipeline(
        self, config: PipelineReplayConfig
    ) -> PipelineReplayResult:
        session_id = f"pipe_{uuid.uuid4().hex[:12]}"
        start_ts = int(datetime.now().timestamp() * 1000)
        self._running_sessions[session_id] = True

        logger.info(
            f"Starting pipeline replay: {session_id}, "
            f"range=[{config.start_time}, {config.end_time}], "
            f"stages=[{config.start_stage}..{config.end_stage}]"
        )

        events_replayed = 0
        stages_completed: List[str] = []
        output_events: List[Dict] = []
        errors: List[str] = []
        is_deterministic = True

        try:
            start_idx = self._get_stage_index(config.start_stage)
            end_idx = self._get_stage_index(config.end_stage)

            if start_idx > end_idx:
                raise ValueError(
                    f"Start stage '{config.start_stage}' is after end stage '{config.end_stage}'"
                )

            for stage_idx in range(start_idx, end_idx + 1):
                stage = self._pipeline_stages[stage_idx]
                if not self._running_sessions.get(session_id, False):
                    break

                stage_events = await self._load_stage_events(stage, config)

                for event_data in stage_events:
                    if not self._running_sessions.get(session_id, False):
                        break

                    handlers = self._handlers.get(stage, [])
                    for handler in handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                result = await handler(event_data)
                            else:
                                result = handler(event_data)
                            if result is not None:
                                if isinstance(result, dict):
                                    output_events.append(result)
                                elif isinstance(result, list):
                                    output_events.extend(result)
                        except Exception as e:
                            errors.append(
                                f"Handler error at stage {stage}: {str(e)}"
                            )
                            logger.error(
                                f"Handler error at stage {stage}: {e}"
                            )

                    events_replayed += 1

                    if config.speed < 1.0 and config.speed > 0:
                        delay = (1.0 / config.speed - 1.0) * 0.001
                        await asyncio.sleep(delay)

                stages_completed.append(stage)
                logger.info(
                    f"Pipeline replay {session_id}: completed stage {stage}, "
                    f"events={len(stage_events)}"
                )

        except Exception as e:
            errors.append(str(e))
            logger.error(f"Pipeline replay {session_id} failed: {e}")
        finally:
            self._running_sessions.pop(session_id, None)

        end_ts = int(datetime.now().timestamp() * 1000)
        duration_ms = end_ts - start_ts

        result = PipelineReplayResult(
            session_id=session_id,
            events_replayed=events_replayed,
            stages_completed=stages_completed,
            output_events=output_events[-1000:],
            duration_ms=duration_ms,
            is_deterministic=is_deterministic,
            errors=errors,
        )

        logger.info(
            f"Pipeline replay {session_id} completed: "
            f"events={events_replayed}, stages={stages_completed}, "
            f"duration={duration_ms}ms, errors={len(errors)}"
        )
        return result

    async def replay_from_stage(
        self, stage: str, config: PipelineReplayConfig
    ) -> PipelineReplayResult:
        config.start_stage = stage
        return await self.replay_pipeline(config)

    async def replay_single_event(self, event: BaseEvent) -> List[BaseEvent]:
        output_events: List[BaseEvent] = []
        event_type = event.event_type
        stage = self._event_type_to_stage(event_type)

        if stage is None:
            logger.warning(f"No stage mapping for event type: {event_type}")
            return output_events

        handlers = self._handlers.get(stage, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event)
                else:
                    result = handler(event)
                if result is not None:
                    if isinstance(result, BaseEvent):
                        output_events.append(result)
                    elif isinstance(result, list):
                        for item in result:
                            if isinstance(item, BaseEvent):
                                output_events.append(item)
            except Exception as e:
                logger.error(f"Handler error for single event replay: {e}")

        return output_events

    def register_stage_handler(self, stage: str, handler: Callable) -> None:
        if stage not in self._handlers:
            self._handlers[stage] = []
        self._handlers[stage].append(handler)
        logger.info(f"Registered handler for stage: {stage}")

    async def get_pipeline_trace(self, trace_id: str) -> List[Dict]:
        trace: List[Dict] = []

        if self.event_store is not None:
            try:
                from shared.replay.models import EventType

                for event_type in EventType:
                    events = await self.event_store.read_events(
                        exchange="",
                        symbol="",
                        event_type=event_type,
                        start_time=0,
                        end_time=int(datetime.now().timestamp() * 1000),
                        limit=10000,
                    )
                    for event in events:
                        if event.data.get("trace_id") == trace_id:
                            trace.append(event.to_dict())
            except Exception as e:
                logger.error(f"Failed to get pipeline trace: {e}")

        trace.sort(key=lambda x: x.get("timestamp", 0))
        return trace

    async def stop_replay(self, session_id: str) -> bool:
        if session_id in self._running_sessions:
            self._running_sessions[session_id] = False
            logger.info(f"Stopped pipeline replay: {session_id}")
            return True
        return False

    def _get_stage_index(self, stage: str) -> int:
        try:
            return self._pipeline_stages.index(stage)
        except ValueError:
            raise ValueError(
                f"Unknown stage: {stage}, valid stages: {self._pipeline_stages}"
            )

    def _event_type_to_stage(self, event_type: str) -> Optional[str]:
        for stage, et in self.STAGE_EVENT_TYPE_MAP.items():
            if et.value == event_type or et == event_type:
                return stage
        return None

    async def _load_stage_events(
        self, stage: str, config: PipelineReplayConfig
    ) -> List[Dict]:
        events: List[Dict] = []

        if self.event_store is None:
            return events

        event_type = self.STAGE_EVENT_TYPE_MAP.get(stage)
        if event_type is None:
            return events

        try:
            from shared.replay.models import EventType as StoreEventType

            store_event_type = StoreEventType(event_type.value)

            for exchange in config.exchanges:
                for symbol in config.symbols:
                    batch = await self.event_store.read_events(
                        exchange=exchange,
                        symbol=symbol,
                        event_type=store_event_type,
                        start_time=config.start_time,
                        end_time=config.end_time,
                        limit=config.batch_size,
                    )
                    for event in batch:
                        if self._matches_filters(event, config.filters):
                            events.append(event.to_dict())
        except Exception as e:
            logger.error(f"Failed to load stage events for {stage}: {e}")

        events.sort(key=lambda x: x.get("timestamp", 0))
        return events

    def _matches_filters(self, event: Any, filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            event_data = event.data if hasattr(event, "data") else event
            if isinstance(event_data, dict):
                if event_data.get(key) != value:
                    return False
        return True
