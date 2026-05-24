import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "system"
    version: str = "v1"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
