"""
Common Schemas - Shared Pydantic Models
"""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class HealthResponse(BaseModel):
    status: str
    mock_mode: bool
    timestamp: datetime


class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
