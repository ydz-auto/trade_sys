import asyncio
from typing import Dict, Any, List, Optional

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.base_event import BaseEvent

logger = get_logger("services.projection.rebuilder")


class ProjectionRebuilder:
    def __init__(self, projections: Optional[List[Any]] = None):
        self._projections: List[Any] = projections or []
        self._running = False
        self._stats = {
            "total_rebuilds": 0,
            "last_rebuild_events": 0,
            "last_rebuild_errors": 0,
        }

    def add_projection(self, projection: Any) -> None:
        self._projections.append(projection)

    def set_projections(self, projections: List[Any]) -> None:
        self._projections = projections

    async def rebuild(
        self,
        start_time_ms: int,
        end_time_ms: int,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        clear_existing: bool = True,
    ) -> Dict[str, Any]:
        if self._running:
            return {"success": False, "error": "Rebuild already in progress"}

        if not self._projections:
            return {"success": False, "error": "No projections registered"}

        self._running = True
        self._stats["total_rebuilds"] += 1
        events_processed = 0
        errors = 0

        try:
            logger.info(
                f"Starting projection rebuild: {start_time_ms} -> {end_time_ms}, "
                f"projections={len(self._projections)}, clear={clear_existing}"
            )

            if clear_existing:
                await self._clear_projection_state()

            from infrastructure.messaging.event_journal import get_event_journal
            journal = await get_event_journal()

            async for batch in journal.replay(
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                event_type=event_type,
                symbol=symbol,
            ):
                for event in batch:
                    event_dict = event.to_dict()
                    for projection in self._projections:
                        try:
                            await projection.handle_event(event_dict)
                        except Exception as e:
                            logger.debug(
                                f"Projection {projection.name} error on {event.event_type}: {e}"
                            )
                            errors += 1
                    events_processed += 1

            self._stats["last_rebuild_events"] = events_processed
            self._stats["last_rebuild_errors"] = errors

            logger.info(
                f"Projection rebuild completed: {events_processed} events, "
                f"{errors} errors, {len(self._projections)} projections"
            )

            return {
                "success": True,
                "events_processed": events_processed,
                "errors": errors,
                "projections": len(self._projections),
            }

        except Exception as e:
            logger.error(f"Projection rebuild failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "events_processed": events_processed,
                "errors": errors,
            }
        finally:
            self._running = False

    async def rebuild_projection(
        self,
        projection_name: str,
        start_time_ms: int,
        end_time_ms: int,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        target = None
        for p in self._projections:
            if p.name == projection_name:
                target = p
                break

        if target is None:
            return {"success": False, "error": f"Projection '{projection_name}' not found"}

        original_projections = self._projections
        self._projections = [target]
        try:
            return await self.rebuild(
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                event_type=event_type,
                symbol=symbol,
                clear_existing=True,
            )
        finally:
            self._projections = original_projections

    async def _clear_projection_state(self) -> None:
        for projection in self._projections:
            try:
                if hasattr(projection, "redis") and projection.redis:
                    keys = await projection.redis.client.keys(f"projection:{projection.name}:*")
                    if keys:
                        await projection.redis.client.delete(*keys)
                        logger.info(f"Cleared {len(keys)} keys for {projection.name}")
            except Exception as e:
                logger.debug(f"Clear state for {projection.name} skipped: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "projections": [p.name for p in self._projections],
            "stats": self._stats.copy(),
        }


_rebuilder: Optional[ProjectionRebuilder] = None


def get_projection_rebuilder() -> ProjectionRebuilder:
    global _rebuilder
    if _rebuilder is None:
        _rebuilder = ProjectionRebuilder()
    return _rebuilder
