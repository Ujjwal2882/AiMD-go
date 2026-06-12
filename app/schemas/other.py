"""
Search, Export and Stat Schemas
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class NearbySearchRequest(BaseModel):
    lat: float
    lon: float
    radius_meters: float = 500
    feature_type: Optional[str] = None

class PolygonSearchRequest(BaseModel):
    coordinates: List[List[float]]  # [[lon, lat], ...]
    feature_type: Optional[str] = None

class ExportRequest(BaseModel):
    format: str = "geojson"  # geojson, csv, shapefile, kml
    layer_ids: Optional[List[str]] = None

class PlatformStats(BaseModel):
    total_projects: int = 0
    total_layers: int = 0
    total_features: int = 0
    total_detections: int = 0
    features_by_source: Dict[str, int] = {}
    storage_path: str = ""

class WSEvent(BaseModel):
    type: str  # "layer_added", "detection_completed", "kpi_update"
    data: Dict[str, Any] = {}
    timestamp: str = ""
