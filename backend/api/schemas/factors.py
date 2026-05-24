"""
Factors Schemas - Factor Weight Models
"""
from pydantic import BaseModel


class UpdateFactorWeightRequest(BaseModel):
    weight: float
