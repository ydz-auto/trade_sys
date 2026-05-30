
# DEPRECATED: Migrated to domain/event/kernel_event/event_time_manager.py
# and domain/event/time_types.py (types)
from domain.event.time_types import EventSource, EventTimeRecord, EventTimeConfig
from domain.event.kernel_event.event_time_manager import (
    EventTimeManager,
    get_event_time_manager,
    record_event_time,
)
