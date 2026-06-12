"""
Common Schemas (Geometry, etc)
"""
from pydantic import BaseModel

class BoundsModel(BaseModel):
    north: float
    south: float
    east: float
    west: float

class PointModel(BaseModel):
    lat: float
    lon: float
