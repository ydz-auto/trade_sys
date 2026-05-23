import asyncio
from typing import Dict, Any, Optional, List

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.base_event import BaseEvent, PipelineEventType
from infrastructure.runtime_clock import now_ms

logger = get_logger("runtime.recovery")


RUNTIME_RECOVERY_WINDOWS: Dict[str, int] = {
    "portfolio_runtime": 300000,
    "execution_runtime": 120000,
    "signal_runtime": 300000,
    "feature_runtime": 600000,
    "projection_runtime": 300000,
    "correlation_runtime": 600000,
    "regime_runtime": 600000,
    "narrative_runtime": 600000,
}

DEFAULT_RECOVERY_WINDOW_MS = 300000


class RuntimeRecovery:
    def __init__(self):
        self._recovery_in_progress: Dict[str, bool] = {}
        self._stats = {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "events_replayed": 0,
            "failed_recoveries": 0,
        }

    async def recover_runtime(
        self,
        runtime_id: str,
        runtime_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._recovery_in_progress.get(runtime_id, False):
            return {"success": False, "error": f"Recovery already in progress for {runtime_id}"}

        self._recovery_in_progress[runtime_id] = True
        self._stats["total_recoveries"] += 1

        try:
            window_ms = RUNTIME_RECOVERY_WINDOWS.get(
                runtime_name or runtime_id,
                DEFAULT_RECOVERY_WINDOW_MS,
            )

            end_ms = now_ms()
            start_ms = end_ms - window_ms

            logger.info(
                f"Starting event replay recovery for {runtime_id} "
                f"(window: {window_ms / 1000}s, name: {runtime_name})"
            )

            from infrastructure.messaging.event_journal import get_event_journal
            journal = await get_event_journal()

            events = await journal.query(
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                limit=10000,
            )

            if not events:
                logger.info(f"No events found for {runtime_id} recovery")
                return {
                    "success": True,
                    "events_replayed": 0,
                    "window_ms": window_ms,
                }

            from runtime.bus.runtime_bus import get_runtime_bus
            bus = get_runtime_bus()

            replayed = 0
            errors = 0

            for event in events:
                try:
                    await bus.publish_event(event)
                    replayed += 1
                except Exception as e:
                    logger.debug(f"Recovery replay error for {event.event_type}: {e}")
                    errors += 1

            self._stats["events_replayed"] += replayed
            self._stats["successful_recoveries"] += 1

            logger.info(
                f"Runtime recovery completed for {runtime_id}: "
                f"{replayed} events replayed, {errors} errors"
            )

            return {
                "success": True,
                "events_replayed": replayed,
                "errors": errors,
                "window_ms": window_ms,
            }

        except Exception as e:
            self._stats["failed_recoveries"] += 1
            logger.error(f"Runtime recovery failed for {runtime_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self._recovery_in_progress[runtime_id] = False

    async def recover_all(self, runtime_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for runtime_id in runtime_ids:
            results[runtime_id] = await self.recover_runtime(runtime_id)
        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "recovery_in_progress": dict(self._recovery_in_progress),
            "stats": self._stats.copy(),
            "recovery_windows": RUNTIME_RECOVERY_WINDOWS,
        }


_recovery: Optional[RuntimeRecovery] = None


def get_runtime_recovery() -> RuntimeRecovery:
    global _recovery
    if _recovery is None:
        _recovery = RuntimeRecovery()
    return _recovery
