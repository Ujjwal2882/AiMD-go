"""
AiMD-go Configuration Module (Core)
Centralized settings loaded from environment variables or .env file.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — override via environment variables or .env file."""

    # Application
    APP_NAME: str = "AiMD-go"
    APP_VERSION: str = "2.0.0" # Updated version for refactor
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data"
    UPLOAD_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
    LAYERS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "layers"
    DETECTIONS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "detections"
    STATIC_DIR: Path = Path(__file__).resolve().parent.parent.parent / "static"

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

    # Geocoding
    GEOCODER_USER_AGENT: str = "aimd_geospatial_v2"
    GEOCODER_RATE_LIMIT_SEC: float = 1.0

    # Infrastructure settings (Supabase / Upstash defaults)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:[YOUR-PASSWORD]@db.hwwsjnpdhjpnywnbvaro.supabase.co:5432/postgres"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # Google Drive Integration
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    # Auth Security
    SECRET_KEY: str = "super_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def init_directories(self):
        """Create all required data directories on startup."""
        for dir_path in [self.DATA_DIR, self.UPLOAD_DIR, self.LAYERS_DIR, self.DETECTIONS_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
