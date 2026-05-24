"""
Runtime Kernel - 交易内核

设计原则:
- 单一入口: runtime.handle(raw_event) - 没有其他路径
- 强制路径: Authority → Guard → State Transition → Emit
- 不可绕过: 所有事件必须经过完整管道
- 确定性: 同样的输入，100% 同样的输出
"""

from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from datetime import datetime
from pathlib import Path

from runtime.kernel.authority import (
    AuthoritySystem,
    ClockAuthority,
    ClockMode,
)
from runtime.kernel.guards import (
    GuardSystem,
    GuardViolation,
)
from runtime.kernel.replay.event_log import (
    EventLog,
    LoggedEvent,
)
from runtime.kernel.replay.state_capture import (
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


class KernelMode(Enum):
    LIVE = "live"
    RECORD = "record"
    REPLAY = "replay"
    VALIDATE = "validate"


@dataclass
class RawEvent:
    event_type: str
    symbol: str
    exchange: str
    event_time_ms: int
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "event_time_ms": self.event_time_ms,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RawEvent':
        return cls(
            event_type=data["event_type"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            event_time_ms=data["event_time_ms"],
            payload=data["payload"],
        )


@dataclass
class StateTrajectory:
    steps: list[Tuple[int, str, str]] = None
    start_time_ms: int = 0
    end_time_ms: int = 0

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def add_step(
        self,
        sequence_number: int,
        event_id: str,
        state_data: Dict[str, Any],
    ) -> None:
        state_hash = self._compute_hash(state_data)
        self.steps.append((sequence_number, event_id, state_hash))

    @staticmethod
    def _compute_hash(state_data: Dict[str, Any]) -> str:
        content = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def compare(
        self,
        other: 'StateTrajectory',
        name_a: str = "a",
        name_b: str = "b",
    ) -> Tuple[bool, list[Dict[str, Any]]]:
        differences = []

        if len(self.steps) != len(other.steps):
            differences.append({
                "step": -1,
                "category": "step_count_mismatch",
                f"{name_a}_count": len(self.steps),
                f"{name_b}_count": len(other.steps),
            })

        min_steps = min(len(self.steps), len(other.steps))

        for i in range(min_steps):
            seq_a, event_a, hash_a = self.steps[i]
            seq_b, event_b, hash_b = other.steps[i]

            if seq_a != seq_b:
                differences.append({
                    "step": i,
                    "category": "seq_mismatch",
                    "message": f"Sequence mismatch: {seq_a} vs {seq_b}",
                })
                continue

            if event_a != event_b:
                differences.append({
                    "step": i,
                    "category": "event_mismatch",
                    "message": f"Event mismatch: {event_a} vs {event_b}",
                    "seq": seq_a,
                })
                continue

            if hash_a != hash_b:
                differences.append({
                    "step": i,
                    "category": "state_hash_mismatch",
                    "message": f"State hash mismatch at step {i}, seq {seq_a}",
                    "seq": seq_a,
                    "event_id": event_a,
                    f"{name_a}_hash": hash_a,
                    f"{name_b}_hash": hash_b,
                })

        is_consistent = len(differences) == 0
        return is_consistent, differences

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [
                {
                    "seq": s[0],
                    "event_id": s[1],
                    "hash": s[2],
                }
                for s in self.steps
            ],
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateTrajectory':
        return cls(
            steps=[(s["seq"], s["event_id"], s["hash"]) for s in data["steps"]],
            start_time_ms=data["start_time_ms"],
            end_time_ms=data["end_time_ms"],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> 'StateTrajectory':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


class RuntimeKernel:

    def __init__(
        self,
        name: str = "kernel",
        storage_dir: Optional[Path] = None,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.name = name
        self.storage_dir = storage_dir or Path("./kernel_data")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._state_provider = state_provider

        self._authority = AuthoritySystem()
        self._guard_system = GuardSystem(
            clock_authority=self._authority.clock,
        )

        self._event_log = EventLog(
            name=f"{name}_events",
            storage_path=self.storage_dir / "events.json",
        )
        self._state_capture = StateCapture(
            name=f"{name}_states",
            storage_path=self.storage_dir / "states.json",
        )
        self._state_trajectory = StateTrajectory()

        self._mode = KernelMode.LIVE
        self._is_running = False
        self._step_count = 0

        self._business_callback: Optional[Callable[[ImmutableEvent], Dict[str, Any]]] = None

        logger.info(f"RuntimeKernel initialized in {self._mode.value} mode")

    @property
    def mode(self) -> KernelMode:
        return self._mode

    @property
    def state_trajectory(self) -> StateTrajectory:
        return self._state_trajectory

    def set_state_provider(
        self,
        provider: Callable[[], Dict[str, Any]],
    ) -> None:
        self._state_provider = provider

    def set_business_callback(
        self,
        callback: Callable[[ImmutableEvent], Dict[str, Any]],
    ) -> None:
        self._business_callback = callback

    def start_record(self) -> None:
        self._mode = KernelMode.RECORD
        self._is_running = True

        self._authority.switch_to_live_mode()

        self._event_log.start_recording(
            start_time_ms=self._authority.clock.now_ms(),
        )

        self._state_trajectory = StateTrajectory()
        self._state_trajectory.start_time_ms = self._authority.clock.now_ms()

        logger.info("RuntimeKernel started RECORD mode")

    def stop_record(self) -> None:
        self._is_running = False
        self._state_trajectory.end_time_ms = self._authority.clock.now_ms()

        self._event_log.stop_recording()

        self._event_log.save()
        self._state_capture.save()
        self._state_trajectory.save(self.storage_dir / "trajectory.json")

        logger.info(
            f"RuntimeKernel stopped RECORD mode, "
            f"steps={len(self._state_trajectory.steps)}"
        )

    def start_replay(
        self,
        event_log_path: Optional[Path] = None,
    ) -> None:
        self._mode = KernelMode.REPLAY
        self._is_running = True

        if event_log_path:
            self._event_log = EventLog.load(event_log_path)

        start_time = self._event_log._start_time_ms
        self._authority.switch_to_replay_mode(start_time)

        self._state_trajectory = StateTrajectory()
        self._state_trajectory.start_time_ms = start_time
        self._guard_system.reset()

        logger.info(
            f"RuntimeKernel started REPLAY mode, "
            f"events={self._event_log.count}"
        )

    def handle(
        self,
        raw_event: RawEvent,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        self._step_count += 1

        try:
            event, seq_num = self._authority.process_raw_event(
                event_type=raw_event.event_type,
                symbol=raw_event.symbol,
                exchange=raw_event.exchange,
                event_time_ms=raw_event.event_time_ms,
                payload=raw_event.payload,
                source=EventSource.LIVE if self._mode == KernelMode.LIVE else EventSource.REPLAY,
            )

            self._guard_system.process_before(event)

            state_before = self._get_current_state()
            if self._mode in [KernelMode.RECORD, KernelMode.REPLAY]:
                self._state_capture.capture(
                    capture_point="EVENT_BEFORE",
                    clock_time_ms=self._authority.clock.now_ms(),
                    sequence_number=seq_num,
                    state_data=state_before,
                    event_id=event.event_id,
                )

            if self._mode == KernelMode.RECORD:
                self._event_log.record_event(event, seq_num)

            business_result = {}
            if self._business_callback:
                business_result = self._business_callback(event)

            state_after = self._get_current_state()
            if self._mode in [KernelMode.RECORD, KernelMode.REPLAY]:
                self._state_capture.capture(
                    capture_point="EVENT_AFTER",
                    clock_time_ms=self._authority.clock.now_ms(),
                    sequence_number=seq_num,
                    state_data=state_after,
                    event_id=event.event_id,
                )

                self._state_trajectory.add_step(
                    sequence_number=seq_num,
                    event_id=event.event_id,
                    state_data=state_after,
                )

            self._guard_system.process_after(event, business_result)

            return True, business_result

        except GuardViolation as e:
            logger.error(f"Guard violation: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False, None

    def run_full_replay(
        self,
        event_log_path: Optional[Path] = None,
    ) -> Tuple[bool, StateTrajectory]:
        if not self._state_provider:
            raise RuntimeError("State provider not set")

        self.start_replay(event_log_path)

        self._state_trajectory = StateTrajectory()
        self._state_trajectory.start_time_ms = self._authority.clock.now_ms()

        success_count = 0
        fail_count = 0

        for logged_event in self._event_log.get_event_iterator():
            self._authority.advance_clock(logged_event.processing_time_ms)

            raw_event = RawEvent(
                event_type=logged_event.event_type,
                symbol=logged_event.symbol,
                exchange=logged_event.exchange,
                event_time_ms=logged_event.event_time_ms,
                payload=logged_event.payload,
            )

            ok, _ = self.handle(raw_event)
            if ok:
                success_count += 1
            else:
                fail_count += 1

        self._state_trajectory.end_time_ms = self._authority.clock.now_ms()

        if self.storage_dir:
            self._state_trajectory.save(self.storage_dir / "replay_trajectory.json")

        is_success = fail_count == 0
        logger.info(
            f"Full replay complete: success={success_count}, "
            f"fail={fail_count}, trajectory_steps={len(self._state_trajectory.steps)}"
        )

        return is_success, self._state_trajectory

    def _get_current_state(self) -> Dict[str, Any]:
        if self._state_provider:
            return self._state_provider()
        return {"step": self._step_count, "kernel_time": self._authority.clock.now_ms()}

    def reset(self) -> None:
        self._is_running = False
        self._mode = KernelMode.LIVE
        self._step_count = 0
        self._event_log.reset()
        self._state_capture.reset()
        self._state_trajectory = StateTrajectory()
        self._authority.clock.switch_to_live_mode()
        self._guard_system.reset()

    def __repr__(self) -> str:
        return (
            f"RuntimeKernel(mode={self._mode.value}, "
            f"steps={self._step_count}, "
            f"trajectory={len(self._state_trajectory.steps)})"
        )
