"""
Layer and Upload Schemas
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.schemas.base import BoundsModel

class LayerStyle(BaseModel):
    color: str = "#6366f1"
    fillColor: str = "#6366f1"
    weight: float = 2
    opacity: float = 0.8
    fillOpacity: float = 0.4
    radius: Optional[float] = 6

class LayerMetadata(BaseModel):
    id: str
    name: str
    source_type: str
    project_id: Optional[str] = None
    feature_count: int = 0
    bounds: Optional[BoundsModel] = None
    style: LayerStyle = LayerStyle()
    visible: bool = True
    opacity: float = 0.8
    created_at: str = ""

class UploadResponse(BaseModel):
    status: str = "success"
    message: str = ""
    job_id: Optional[str] = None # Added for async polling
    layer_id: Optional[str] = None
    feature_count: int = 0
    bounds: Optional[BoundsModel] = None
    layer_name: str = ""
    source_type: str = ""

class CSVUploadConfig(BaseModel):
    lat_column: Optional[str] = None
    lon_column: Optional[str] = None
    address_column: Optional[str] = None

class CSVPreviewResponse(BaseModel):
    headers: List[str]
    sample_rows: List[Dict[str, Any]]
    row_count: int
    detected_lat_column: Optional[str] = None
    detected_lon_column: Optional[str] = None
    has_coordinates: bool = False
