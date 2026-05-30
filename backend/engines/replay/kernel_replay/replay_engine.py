"""
Replay Engine - 确定性回放引擎

核心职责:
- Record 模式: 记录 Live 运行的完整状态
- Replay 模式: 完全按照记录的时间序列回放
- 验证: 对比 Replay 和 Live 是否 100% 一致
"""

from enum import Enum
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from domain.runtime_policy.authority import (
    AuthoritySystem,
    ClockAuthority,
    ClockMode,
)
from domain.risk.guards import (
    GuardSystem,
)
from engines.replay.kernel_replay.event_log import (
    EventLog,
    LoggedEvent,
)
from engines.replay.kernel_replay.state_capture import (
    StateCapture,
    StateSnapshot,
)
from domain.event.protocol import (
    ImmutableEvent,
    ImmutableEventBuilder,
    EventSource,
)
import logging

logger = logging.getLogger(__name__)


class ReplayMode(Enum):
    LIVE = "live"
    RECORD = "record"
    REPLAY = "replay"
    VALIDATE = "validate"


class ReplayEngine:

    def __init__(
        self,
        name: str = "replay_engine",
        authority_system: Optional[AuthoritySystem] = None,
        guard_system: Optional[GuardSystem] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.name = name
        self.storage_dir = storage_dir or Path("./replay_data")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._authority_system = authority_system or AuthoritySystem()
        self._guard_system = guard_system or GuardSystem(
            clock_authority=self._authority_system.clock,
        )

        self._event_log = EventLog(
            name=f"{name}_events",
            storage_path=self.storage_dir / "events.json",
        )
        self._state_capture = StateCapture(
            name=f"{name}_states",
            storage_path=self.storage_dir / "states.json",
        )

        self._mode = ReplayMode.LIVE
        self._is_running = False

        self._state_provider: Optional[Callable[[], Dict[str, Any]]] = None

        logger.info(f"ReplayEngine initialized in {self._mode.value} mode")

    @property
    def mode(self) -> ReplayMode:
        return self._mode

    @property
    def event_log(self) -> EventLog:
        return self._event_log

    @property
    def state_capture(self) -> StateCapture:
        return self._state_capture

    def set_state_provider(
        self,
        provider: Callable[[], Dict[str, Any]],
    ) -> None:
        self._state_provider = provider

    def start_record(self) -> None:
        self._mode = ReplayMode.RECORD
        self._is_running = True

        self._authority_system.clock.switch_to_live_mode()

        self._event_log.start_recording(
            start_time_ms=self._authority_system.clock.now_ms(),
        )

        self._state_capture.reset()

        logger.info(f"ReplayEngine started RECORD mode")

    def stop_record(self) -> None:
        self._is_running = False

        self._event_log.stop_recording()

        self._event_log.save()
        self._state_capture.save()

        logger.info(f"ReplayEngine stopped RECORD mode")

    def process_event(
        self,
        event_type: str,
        symbol: str,
        exchange: str,
        event_time_ms: int,
        payload: Dict[str, Any],
        source: EventSource = EventSource.LIVE,
    ) -> tuple[ImmutableEvent, int]:
        event, sequence_number = self._authority_system.process_raw_event(
            event_type=event_type,
            symbol=symbol,
            exchange=exchange,
            event_time_ms=event_time_ms,
            payload=payload,
            source=source,
        )

        if self._guard_system:
            self._guard_system.process_before(event)

        if self._mode in [ReplayMode.RECORD, ReplayMode.LIVE]:
            self._event_log.record_event(
                event=event,
                sequence_number=sequence_number,
            )

            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_BEFORE",
                    clock_time_ms=self._authority_system.clock.now_ms(),
                    sequence_number=sequence_number,
                    state_data=self._state_provider(),
                    event_id=event.event_id,
                )

        if self._mode in [ReplayMode.RECORD, ReplayMode.LIVE]:
            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_AFTER",
                    clock_time_ms=self._authority_system.clock.now_ms(),
                    sequence_number=sequence_number,
                    state_data=self._state_provider(),
                    event_id=event.event_id,
                )

        if self._guard_system:
            self._guard_system.process_after(event, result={})

        return event, sequence_number

    def start_replay(
        self,
        event_log_path: Optional[Path] = None,
    ) -> None:
        self._mode = ReplayMode.REPLAY
        self._is_running = True

        if event_log_path:
            self._event_log = EventLog.load(event_log_path)

        start_time = self._event_log._start_time_ms
        self._authority_system.switch_to_replay_mode(start_time)

        self._state_capture.reset()

        if self._guard_system:
            self._guard_system.reset()

        logger.info(
            f"ReplayEngine started REPLAY mode, "
            f"events={self._event_log.count}, "
            f"start_time={start_time}"
        )

    def run_full_replay(
        self,
        validate: bool = True,
    ) -> tuple[int, int]:
        if self._mode != ReplayMode.REPLAY:
            self.start_replay()

        processed_count = 0
        violation_count = 0

        for logged_event in self._event_log.get_event_iterator():
            processed_count += 1

            self._authority_system.advance_clock(logged_event.processing_time_ms)

            builder = ImmutableEventBuilder()
            replay_event = (
                builder
                .event_id(logged_event.event_id)
                .event_type(logged_event.event_type)
                .symbol(logged_event.symbol)
                .exchange(logged_event.exchange)
                .event_time_ms(logged_event.event_time_ms)
                .available_time_ms(logged_event.available_time_ms)
                .processing_time_ms(logged_event.processing_time_ms)
                .payload(logged_event.payload)
                .source(EventSource.REPLAY)
                .build()
            )

            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_BEFORE",
                    clock_time_ms=logged_event.processing_time_ms,
                    sequence_number=logged_event.sequence_number,
                    state_data=self._state_provider(),
                    event_id=logged_event.event_id,
                )

            if self._guard_system:
                try:
                    self._guard_system.process_before(replay_event)
                except Exception as e:
                    violation_count += 1
                    logger.error(
                        f"Guard violation during replay: {logged_event.event_id}, "
                        f"error={e}"
                    )

            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_AFTER",
                    clock_time_ms=logged_event.processing_time_ms,
                    sequence_number=logged_event.sequence_number,
                    state_data=self._state_provider(),
                    event_id=logged_event.event_id,
                )

        logger.info(
            f"Replay completed: "
            f"processed={processed_count}, "
            f"violations={violation_count}"
        )

        return processed_count, violation_count

    def save_session(
        self,
        name: Optional[str] = None,
    ) -> Path:
        session_name = name or self.name
        session_dir = self.storage_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)

        self._event_log.save(session_dir / "events.json")
        self._state_capture.save(session_dir / "states.json")

        logger.info(f"Saved session to {session_dir}")
        return session_dir

    @classmethod
    def load_session(
        cls,
        session_dir: Path,
        authority_system: Optional[AuthoritySystem] = None,
        guard_system: Optional[GuardSystem] = None,
    ) -> 'ReplayEngine':
        engine = cls(
            name=session_dir.name,
            authority_system=authority_system,
            guard_system=guard_system,
            storage_dir=session_dir.parent,
        )

        engine._event_log = EventLog.load(session_dir / "events.json")
        engine._state_capture = StateCapture.load(session_dir / "states.json")

        logger.info(f"Loaded session from {session_dir}")
        return engine

    def reset(self) -> None:
        self._is_running = False
        self._mode = ReplayMode.LIVE
        self._event_log.reset()
        self._state_capture.reset()
        self._authority_system.clock.switch_to_live_mode()

        if self._guard_system:
            self._guard_system.reset()

    def __repr__(self) -> str:
        return (
            f"ReplayEngine(mode={self._mode.value}, "
            f"events={self._event_log.count}, "
            f"states={self._state_capture.count})"
        )
