"""
AiMD-go Pydantic Models
Data validation models — NOT database ORM. Used for API request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ──────────────────── Geometry Models ────────────────────

class BoundsModel(BaseModel):
    north: float
    south: float
    east: float
    west: float


class PointModel(BaseModel):
    lat: float
    lon: float


# ──────────────────── Project Models ────────────────────

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


# ──────────────────── Layer Models ────────────────────

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


# ──────────────────── Upload Models ────────────────────

class UploadResponse(BaseModel):
    status: str = "success"
    message: str = ""
    layer_id: str = ""
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


# ──────────────────── Detection Models ────────────────────

class DetectionRequest(BaseModel):
    confidence_threshold: float = 0.5
    model_name: str = "yolov8l.pt"


class DetectionResult(BaseModel):
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    model_name: str = ""
    confidence_threshold: float = 0.5
    image_name: str = ""
    detections_count: int = 0
    layer_id: Optional[str] = None
    error: Optional[str] = None
    processing_time_sec: float = 0
    created_at: str = ""
    completed_at: Optional[str] = None
    statistics: Dict[str, int] = {}


# ──────────────────── Search Models ────────────────────

class NearbySearchRequest(BaseModel):
    lat: float
    lon: float
    radius_meters: float = 500
    feature_type: Optional[str] = None


class PolygonSearchRequest(BaseModel):
    coordinates: List[List[float]]  # [[lon, lat], ...]
    feature_type: Optional[str] = None


# ──────────────────── Export Models ────────────────────

class ExportRequest(BaseModel):
    format: str = "geojson"  # geojson, csv, shapefile, kml
    layer_ids: Optional[List[str]] = None


# ──────────────────── Statistics Models ────────────────────

class PlatformStats(BaseModel):
    total_projects: int = 0
    total_layers: int = 0
    total_features: int = 0
    total_detections: int = 0
    features_by_source: Dict[str, int] = {}
    storage_path: str = ""


# ──────────────────── WebSocket Models ────────────────────

class WSEvent(BaseModel):
    type: str  # "layer_added", "detection_completed", "kpi_update"
    data: Dict[str, Any] = {}
    timestamp: str = ""
