import json
from typing import Dict, Any, Union

from infrastructure.messaging.schema.base_event import BaseEvent, parse_event


class EventSerializer:
    @staticmethod
    def serialize(event: BaseEvent) -> bytes:
        return json.dumps(event.to_dict(), default=str).encode("utf-8")

    @staticmethod
    def serialize_to_str(event: BaseEvent) -> str:
        return json.dumps(event.to_dict(), default=str)

    @staticmethod
    def deserialize(payload: Union[bytes, str]) -> BaseEvent:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        return parse_event(data)

    @staticmethod
    def serialize_dict(data: Dict[str, Any]) -> bytes:
        return json.dumps(data, default=str).encode("utf-8")

    @staticmethod
    def deserialize_to_dict(payload: Union[bytes, str]) -> Dict[str, Any]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)
