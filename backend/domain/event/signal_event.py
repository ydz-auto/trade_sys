from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


@dataclass
class Signal:
    symbol: str
    direction: str
    strength: float
    confidence: float
    source: str
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    expires_at: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return int(datetime.now().timestamp()) > self.expires_at

    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.strength,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "metadata": self.metadata
        }
