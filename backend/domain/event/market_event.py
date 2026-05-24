from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any
import uuid

from domain.event.base_event import Exchange


@dataclass
class MarketEvent:
    symbol: str
    exchange: Exchange
    event_type: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    price: float = 0.0
    volume: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
