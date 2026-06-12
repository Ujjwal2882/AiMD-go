"""
Detection Schemas
"""
from typing import Dict, Optional
from pydantic import BaseModel

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
