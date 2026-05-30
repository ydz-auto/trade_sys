from typing import List, Dict, Any, Optional

from domain.risk.guards.base_guard import GuardViolation, BaseGuard
from domain.risk.guards.availability_guard import AvailabilityGuard
from domain.risk.guards.ordering_guard import OrderingGuard
from domain.risk.guards.mutation_guard import MutationGuard
from domain.risk.guards.partial_candle_guard import PartialCandleGuard
from domain.risk.guards.duplicate_guard import DuplicateGuard
from domain.risk.guards.clock_guard import ClockGuard
from domain.runtime_policy.authority import ClockAuthority, ClockMode
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class GuardSystem:
    def __init__(
        self,
        clock_authority: ClockAuthority,
        enable_all: bool = True,
    ):
        self._clock_authority = clock_authority
        self._guards: List[BaseGuard] = []
        self._guard_map: Dict[str, BaseGuard] = {}

        self._init_guards(enable_all)

    def _init_guards(self, enable_all: bool) -> None:
        self.add_guard(MutationGuard(enabled=enable_all))

        self.add_guard(
            AvailabilityGuard(
                clock_source=self._clock_authority.now_ms,
                enabled=enable_all,
            )
        )

        self.add_guard(OrderingGuard(enabled=enable_all))

        self.add_guard(DuplicateGuard(enabled=enable_all))

        self.add_guard(PartialCandleGuard(enabled=enable_all))

        self.add_guard(
            ClockGuard(
                clock_source=self._clock_authority.now_ms,
                enabled=enable_all,
                strict=False,
            )
        )

    def add_guard(self, guard: BaseGuard) -> None:
        self._guards.append(guard)
        self._guard_map[guard.name] = guard
        logger.debug(f"Added guard: {guard.name}")

    def get_guard(self, name: str) -> Optional[BaseGuard]:
        return self._guard_map.get(name)

    def process_before(self, event: ImmutableEvent) -> None:
        for guard in self._guards:
            guard.before_process(event)

        logger.debug(f"All guards passed for event: {event.event_id}")

    def process_after(self, event: ImmutableEvent, result: Any) -> None:
        for guard in self._guards:
            guard.after_process(event, result)

    def validate_event(self, event: ImmutableEvent) -> bool:
        try:
            self.process_before(event)
            return True
        except GuardViolation as e:
            logger.warning(f"Event validation failed: {e}")
            return False

    def reset(self) -> None:
        for guard in self._guards:
            guard.reset()
        logger.info("All guards reset")

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        stats = {}
        for guard in self._guards:
            stats[guard.name] = {
                "violations": guard.violation_count,
                "processed": guard.processed_count,
                "enabled": guard.enabled,
            }
        return stats

    def set_enabled(self, guard_name: str, enabled: bool) -> bool:
        guard = self._guard_map.get(guard_name)
        if guard:
            guard.enabled = enabled
            logger.info(f"Guard {guard_name} set to enabled={enabled}")
            return True
        logger.warning(f"Guard not found: {guard_name}")
        return False

    def __repr__(self) -> str:
        enabled_count = sum(1 for g in self._guards if g.enabled)
        return f"GuardSystem(guards={len(self._guards)}, enabled={enabled_count})"
