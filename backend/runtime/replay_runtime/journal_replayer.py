import asyncio
from typing import Optional, Callable, Awaitable

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.base_event import BaseEvent
from infrastructure.utilities.runtime_clock import get_clock, set_clock_mode, ClockMode

logger = get_logger("runtime.replay.journal_replayer")


class JournalReplayer:
    def __init__(self):
        self._running = False
        self._paused = False
        self._speed = 1.0
        self._stats = {
            "events_replayed": 0,
            "events_skipped": 0,
            "replay_sessions": 0,
        }

    async def replay(
        self,
        start_time_ms: int,
        end_time_ms: int,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        speed: float = 1.0,
        publisher: Optional[Callable[[BaseEvent], Awaitable[None]]] = None,
        on_event: Optional[Callable[[BaseEvent], Awaitable[None]]] = None,
    ) -> int:
        if self._running:
            logger.warning("Replay already in progress")
            return 0

        self._running = True
        self._paused = False
        self._speed = max(0.0, speed)
        self._stats["replay_sessions"] += 1

        original_clock_mode = None
        clock = get_clock()
        if clock:
            original_clock_mode = clock.mode

        try:
            set_clock_mode(ClockMode.REPLAY)
            logger.info(
                f"Starting journal replay: {start_time_ms} -> {end_time_ms}, "
                f"speed={speed}x, type={event_type}, symbol={symbol}"
            )

            from infrastructure.messaging.event_journal import get_event_journal
            journal = await get_event_journal()

            total_replayed = 0
            last_event_time_ms: Optional[int] = None

            async for batch in journal.replay(
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                event_type=event_type,
                symbol=symbol,
            ):
                if not self._running:
                    break

                while self._paused and self._running:
                    await asyncio.sleep(0.1)

                if not self._running:
                    break

                for event in batch:
                    if not self._running:
                        break

                    if last_event_time_ms is not None and self._speed > 0:
                        time_delta_ms = event.event_time_ms - last_event_time_ms
                        if time_delta_ms > 0:
                            delay = time_delta_ms / 1000.0 / self._speed
                            delay = min(delay, 10.0)
                            if delay > 0.001:
                                await asyncio.sleep(delay)

                    if clock:
                        clock.advance_to(event.event_time_ms)

                    if publisher:
                        try:
                            await publisher(event)
                        except Exception as e:
                            logger.error(f"Failed to publish replayed event: {e}")
                            self._stats["events_skipped"] += 1
                            continue

                    if on_event:
                        try:
                            await on_event(event)
                        except Exception as e:
                            logger.debug(f"Replay callback error: {e}")

                    total_replayed += 1
                    self._stats["events_replayed"] += 1
                    last_event_time_ms = event.event_time_ms

            logger.info(f"Journal replay completed: {total_replayed} events")
            return total_replayed

        except Exception as e:
            logger.error(f"Journal replay failed: {e}")
            return self._stats["events_replayed"]
        finally:
            self._running = False
            if original_clock_mode is not None:
                try:
                    set_clock_mode(original_clock_mode)
                except Exception:
                    pass

    def pause(self) -> None:
        self._paused = True
        logger.info("Journal replay paused")

    def resume(self) -> None:
        self._paused = False
        logger.info("Journal replay resumed")

    def stop(self) -> None:
        self._running = False
        self._paused = False
        logger.info("Journal replay stopped")

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.0, speed)
        logger.info(f"Journal replay speed set to {self._speed}x")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "speed": self._speed,
            "stats": self._stats.copy(),
        }


_replayer: Optional[JournalReplayer] = None


def get_journal_replayer() -> JournalReplayer:
    global _replayer
    if _replayer is None:
        _replayer = JournalReplayer()
    return _replayer
