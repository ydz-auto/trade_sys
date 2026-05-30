"""
Low-level deterministic primitives. FrozenClock removed - use infrastructure.utilities.runtime_clock instead
"""

import hashlib
import json
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms, RuntimeClock, ClockMode

logger = get_logger("runtime.kernel.replay.determinism")


@dataclass
class DeterministicContext:

    session_id: str
    seed: int
    frozen_clock: Any
    step_counter: int = 0
    execution_log: List[Dict] = field(default_factory=list)
    _random: Any = field(default=None, repr=False)

    def __post_init__(self):
        self._random = random.Random(self.seed)

    def next_step(self) -> int:
        step = self.step_counter
        self.step_counter += 1
        return step

    def get_random(self) -> Any:
        return self._random


@dataclass
class DeterminismVerificationResult:

    is_deterministic: bool
    total_steps: int
    verified_steps: int
    violations: List[Dict]
    state_hash_mismatches: List[Dict]


class DeterministicReplayEngine:

    def __init__(self, seed: int = 42):
        self.seed = seed
        self._execution_log: Dict[str, List[Dict]] = {}
        self._state_hashes: Dict[str, Dict[str, str]] = {}
        self._contexts: Dict[str, DeterministicContext] = {}
        self._verification_enabled = True

    def create_deterministic_context(self, session_id: str) -> DeterministicContext:
        frozen_clock = RuntimeClock(mode=ClockMode.REPLAY)
        context = DeterministicContext(
            session_id=session_id,
            seed=self.seed,
            frozen_clock=frozen_clock,
        )
        self._contexts[session_id] = context
        self._execution_log[session_id] = []
        self._state_hashes[session_id] = {}
        logger.info(f"Created deterministic context for session: {session_id}")
        return context

    def get_context(self, session_id: str) -> Optional[DeterministicContext]:
        return self._contexts.get(session_id)

    def record_execution(
        self,
        session_id: str,
        step: str,
        input_hash: str,
        output_hash: str,
    ) -> None:
        entry = {
            "step": step,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "step_number": 0,
        }
        context = self._contexts.get(session_id)
        if context:
            entry["step_number"] = context.next_step()
        self._execution_log[session_id].append(entry)
        logger.debug(
            f"Recorded execution: session={session_id}, step={step}, "
            f"input={input_hash[:8]}, output={output_hash[:8]}"
        )

    def verify_determinism(self, session_id: str) -> DeterminismVerificationResult:
        log = self._execution_log.get(session_id, [])
        violations: List[Dict] = []
        state_hash_mismatches: List[Dict] = []

        output_hash_map: Dict[str, str] = {}
        for entry in log:
            input_hash = entry["input_hash"]
            output_hash = entry["output_hash"]
            if input_hash in output_hash_map:
                if output_hash_map[input_hash] != output_hash:
                    violation = {
                        "step": entry["step"],
                        "step_number": entry["step_number"],
                        "input_hash": input_hash,
                        "expected_output": output_hash_map[input_hash],
                        "actual_output": output_hash,
                    }
                    violations.append(violation)
            else:
                output_hash_map[input_hash] = output_hash

        state_hashes = self._state_hashes.get(session_id, {})
        for state_key, current_hash in state_hashes.items():
            pass

        is_deterministic = len(violations) == 0 and len(state_hash_mismatches) == 0

        result = DeterminismVerificationResult(
            is_deterministic=is_deterministic,
            total_steps=len(log),
            verified_steps=len(output_hash_map),
            violations=violations,
            state_hash_mismatches=state_hash_mismatches,
        )

        logger.info(
            f"Determinism verification for session {session_id}: "
            f"deterministic={is_deterministic}, "
            f"total_steps={len(log)}, violations={len(violations)}"
        )
        return result

    def compute_state_hash(self, state: Dict) -> str:
        state_json = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(state_json.encode("utf-8")).hexdigest()

    def record_state_hash(self, session_id: str, state_key: str, state: Dict) -> str:
        state_hash = self.compute_state_hash(state)
        if session_id not in self._state_hashes:
            self._state_hashes[session_id] = {}
        self._state_hashes[session_id][state_key] = state_hash
        return state_hash

    def freeze_time(self, timestamp: int) -> Any:
        clock = RuntimeClock(mode=ClockMode.REPLAY)
        clock.advance_to(timestamp)
        return clock

    def create_seeded_random(self, session_id: str) -> Any:
        context = self._contexts.get(session_id)
        if context:
            return context.get_random()
        return random.Random(self.seed)

    def cleanup_session(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)
        self._execution_log.pop(session_id, None)
        self._state_hashes.pop(session_id, None)
        logger.info(f"Cleaned up deterministic context for session: {session_id}")
