"""
Project Schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.base import BoundsModel

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    layer_ids: List[str] = []
    bounds: Optional[BoundsModel] = None
