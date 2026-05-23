import logging
from typing import Dict, Any, Callable, List, Optional, Type, Tuple

from infrastructure.messaging.schema.base_event import BaseEvent, SCHEMA_VERSION

logger = logging.getLogger("runtime.event_registry")


class EventUpcaster:
    _upcasters: Dict[Tuple[str, str, str], Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    @classmethod
    def register(
        cls,
        event_type: str,
        from_version: str,
        to_version: str,
        upcaster: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        key = (event_type, from_version, to_version)
        cls._upcasters[key] = upcaster
        logger.debug(f"Registered upcaster: {event_type} {from_version} -> {to_version}")

    @classmethod
    def upgrade(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        event_type = data.get("event_type", "unknown")
        current_version = data.get("schema_version", "1.0")

        if current_version == SCHEMA_VERSION:
            return data

        chain = cls._find_upgrade_chain(event_type, current_version, SCHEMA_VERSION)
        if not chain:
            logger.warning(
                f"No upgrade path for {event_type} from {current_version} to {SCHEMA_VERSION}. "
                f"Using as-is."
            )
            data["schema_version"] = SCHEMA_VERSION
            return data

        for step_from, step_to in chain:
            key = (event_type, step_from, step_to)
            upcaster = cls._upcasters.get(key)
            if upcaster:
                data = upcaster(data)
                data["schema_version"] = step_to
                logger.debug(f"Upcasted {event_type}: {step_from} -> {step_to}")

        return data

    @classmethod
    def _find_upgrade_chain(
        cls,
        event_type: str,
        from_version: str,
        to_version: str,
    ) -> List[Tuple[str, str]]:
        chain: List[Tuple[str, str]] = []
        current = from_version
        visited = set()

        while current != to_version:
            if current in visited:
                return []
            visited.add(current)

            found = False
            for (et, fv, tv), _ in cls._upcasters.items():
                if et == event_type and fv == current:
                    chain.append((fv, tv))
                    current = tv
                    found = True
                    break

            if not found:
                return []

        return chain


class EventRegistry:
    _registry: Dict[str, Dict[str, Type[BaseEvent]]] = {}

    @classmethod
    def register(
        cls,
        event_type: str,
        version: str,
        model: Type[BaseEvent],
    ) -> None:
        if event_type not in cls._registry:
            cls._registry[event_type] = {}
        cls._registry[event_type][version] = model

    @classmethod
    def parse(cls, data: Dict[str, Any]) -> BaseEvent:
        data = EventUpcaster.upgrade(data)

        event_type = data.get("event_type")
        schema_version = data.get("schema_version", SCHEMA_VERSION)

        if event_type not in cls._registry:
            logger.debug(f"Unknown event_type '{event_type}', falling back to BaseEvent")
            return BaseEvent(**data)

        versions = cls._registry[event_type]
        if schema_version in versions:
            return versions[schema_version](**data)

        latest_version = max(versions.keys())
        logger.debug(
            f"Schema version {schema_version} not found for {event_type}, "
            f"using latest: {latest_version}"
        )
        return versions[latest_version](**data)

    @classmethod
    def get_model(
        cls,
        event_type: str,
        version: str = SCHEMA_VERSION,
    ) -> Optional[Type[BaseEvent]]:
        versions = cls._registry.get(event_type, {})
        if version in versions:
            return versions[version]
        if versions:
            return versions[max(versions.keys())]
        return None

    @classmethod
    def registered_types(cls) -> Dict[str, List[str]]:
        return {et: list(versions.keys()) for et, versions in cls._registry.items()}


def _auto_register():
    from infrastructure.messaging.schema.base_event import EVENT_CLASS_MAP

    for event_type, model in EVENT_CLASS_MAP.items():
        EventRegistry.register(event_type, SCHEMA_VERSION, model)


_auto_register()


EventUpcaster.register(
    "raw_data", "1.0", "2.0",
    lambda d: {**d, "schema_version": "2.0", "data_type": d.get("data_type", "news"), "data_source": d.get("data_source", ""), "data": d.get("data", {})}
)

EventUpcaster.register(
    "signal", "1.0", "2.0",
    lambda d: {**d, "schema_version": "2.0", "signal_name": d.get("signal_name", ""), "factors": d.get("factors", {})}
)

EventUpcaster.register(
    "order", "1.0", "2.0",
    lambda d: {**d, "schema_version": "2.0", "order_type": d.get("order_type", d.get("type", "market")), "filled_quantity": d.get("filled_quantity", 0.0)}
)
