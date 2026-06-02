"""
AiMD-go Configuration Module
Centralized settings loaded from environment variables or .env file.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — override via environment variables or .env file."""

    # Application
    APP_NAME: str = "AiMD-go"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    UPLOAD_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    LAYERS_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "layers"
    DETECTIONS_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "detections"
    STATIC_DIR: Path = Path(__file__).resolve().parent.parent / "static"

    # Upload Limits
    MAX_UPLOAD_SIZE_MB: int = 500  # 500MB max upload
    ALLOWED_CSV_EXTENSIONS: list = [".csv"]
    ALLOWED_SHAPE_EXTENSIONS: list = [".zip"]
    ALLOWED_GEOJSON_EXTENSIONS: list = [".json", ".geojson"]
    ALLOWED_IMAGE_EXTENSIONS: list = [".tif", ".tiff", ".jpg", ".jpeg", ".png"]
    ALLOWED_LIDAR_EXTENSIONS: list = [".las", ".laz"]

    # AI Model
    AI_MODEL_NAME: str = "yolov8l.pt"
    AI_CONFIDENCE_THRESHOLD: float = 0.5
    AI_IOU_THRESHOLD: float = 0.45

    # Geocoding (Nominatim — free, 1 req/sec)
    GEOCODER_USER_AGENT: str = "aimd_geospatial_v1"
    GEOCODER_RATE_LIMIT_SEC: float = 1.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def init_directories(self):
        """Create all required data directories on startup."""
        for dir_path in [self.DATA_DIR, self.UPLOAD_DIR, self.LAYERS_DIR, self.DETECTIONS_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
