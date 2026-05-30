import logging
from typing import Any, List

__all__ = ["IngestionRunner"]

_logger = logging.getLogger(__name__)


class IngestionRunner:
    def __init__(self, data_source: Any, repository: Any) -> None:
        self._data_source = data_source
        self._repository = repository

    def collect(self) -> List[Any]:
        try:
            events = self._data_source.fetch()
            return events
        except Exception:
            _logger.error("Failed to collect events from data source", exc_info=True)
            return []

    def persist(self, events: List[Any]) -> None:
        if self._repository is not None and events:
            self._repository.save_batch(events)

    def collect_and_persist(self) -> List[Any]:
        events = self.collect()
        self.persist(events)
        return events
