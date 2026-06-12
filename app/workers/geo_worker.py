"""
Geo Worker — Celery task that converts uploaded Shapefile/CSV to GeoJSON,
saves to local processed/ folder, uploads to Google Drive, and updates Supabase.
"""
import json
import os
import io
import tempfile
from pathlib import Path
from uuid import uuid4
from celery.utils.log import get_task_logger
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)

PROCESSED_DIR = Path(os.getenv("DATA_DIR", "data")) / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _get_db_conn():
    import psycopg2
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def _upload_to_drive(file_path: Path, folder_id: str) -> str:
    """Upload a file to Google Drive and return the file ID."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds_path = Path("credentials.json")
    if not creds_path.exists():
        logger.warning("credentials.json not found — skipping Drive upload")
        return ""

    creds = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    service = build("drive", "v3", credentials=creds)

    file_metadata = {"name": file_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(file_path), resumable=True)
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return uploaded.get("id", "")


@celery_app.task(bind=True, name="geo.convert_file")
def convert_geo_file(self, upload_id: str, file_path: str, source_type: str, project_id: str = None, options: dict = None):
    """
    Background task: convert CSV/Shapefile → GeoJSON.
    
    Flow:
    1. Update upload status → 'processing'
    2. Read file, convert to GeoJSON (using app.geo.converters)
    3. Save GeoJSON to data/processed/{layer_id}.geojson
    4. Upload GeoJSON to Google Drive
    5. Insert layer record in Supabase with drive_file_id and geojson_path
    6. Update upload status → 'completed'
    """
    options = options or {}
    layer_id = str(uuid4())
    
    conn = _get_db_conn()
    try:
        cur = conn.cursor()
        
        # 1. Mark upload as processing
        cur.execute("UPDATE uploads SET status = 'processing' WHERE id = %s", (upload_id,))
        conn.commit()
        
        # 2. Read and convert
        with open(file_path, "rb") as f:
            content = f.read()

        if source_type == "csv":
            from app.geo.converters import CSVConverter
            geojson = CSVConverter.to_geojson(
                content,
                lat_column=options.get("lat_column"),
                lon_column=options.get("lon_column"),
            )
        elif source_type == "shapefile":
            from app.geo.converters import ShapefileConverter
            geojson = ShapefileConverter.to_geojson(content)
        elif source_type == "geojson":
            from app.geo.converters import GeoJSONConverter
            geojson = GeoJSONConverter.validate_and_normalize(content)
        else:
            raise ValueError(f"Unknown source type: {source_type}")
        
        feature_count = len(geojson.get("features", []))
        
        # 3. Save to local processed/ folder
        output_path = PROCESSED_DIR / f"{layer_id}.geojson"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)
        logger.info(f"Saved {feature_count} features to {output_path}")
        
        # 4. Upload to Google Drive
        drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        drive_file_id = ""
        if drive_folder_id:
            try:
                drive_file_id = _upload_to_drive(output_path, drive_folder_id)
                logger.info(f"Uploaded to Google Drive: {drive_file_id}")
            except Exception as e:
                logger.warning(f"Drive upload failed (non-fatal): {e}")
        
        # 5. Insert layer into Supabase
        layer_name = Path(file_path).stem
        cur.execute(
            """INSERT INTO layers (id, project_id, name, file_type, geojson_path, drive_file_id, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, now())""",
            (layer_id, project_id, layer_name, source_type, str(output_path), drive_file_id)
        )
        
        # 6. Mark upload as completed
        cur.execute("UPDATE uploads SET status = 'completed' WHERE id = %s", (upload_id,))
        conn.commit()
        
        logger.info(f"Geo conversion complete: {layer_name} → {feature_count} features")
        return {"status": "completed", "layer_id": layer_id, "feature_count": feature_count}

    except Exception as e:
        conn.rollback()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE uploads SET status = 'failed' WHERE id = %s", (upload_id,))
            conn.commit()
        except Exception:
            pass
        logger.error(f"Geo conversion failed for upload {upload_id}: {e}")
        raise
    finally:
        conn.close()
        # Clean up temp file
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass
