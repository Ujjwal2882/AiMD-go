import json
from pathlib import Path
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.geo.converters import CSVConverter, ShapefileConverter
from app.geo.validators import GeometryValidator
from app.storage.object_store import object_store
from app.storage.database import SessionLocal
from app.storage.models import Layer
from app.core.config import settings

logger = get_task_logger(__name__)

@celery_app.task(bind=True)
def convert_geo_file(self, object_key: str, source_type: str, layer_id: str, options: dict = None):
    """
    Background task to convert uploaded CSV/Shapefile to GeoJSON.
    Reads from object store, converts, saves GeoJSON, and updates DB.
    """
    options = options or {}
    logger.info(f"Starting conversion for layer {layer_id} (source: {source_type})")
    
    # 1. Download raw file from object store
    temp_dir = settings.DATA_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / object_key.split("/")[-1]
    
    try:
        object_store.download_file(object_key, temp_file_path)
        
        with open(temp_file_path, "rb") as f:
            content = f.read()

        # 2. Convert based on source type
        if source_type == "csv":
            geojson = CSVConverter.to_geojson(
                content,
                lat_column=options.get("lat_column"),
                lon_column=options.get("lon_column"),
            )
        elif source_type == "shapefile":
            geojson = ShapefileConverter.to_geojson(content)
        else:
            raise ValueError(f"Unknown source_type for conversion: {source_type}")

        # 3. Validate
        valid, msg = GeometryValidator.validate_feature_collection(geojson)
        if not valid:
            raise ValueError(f"Invalid geometry: {msg}")
            
        feature_count = len(geojson.get("features", []))

        # 4. Save GeoJSON to local disk
        layer_file = settings.LAYERS_DIR / f"{layer_id}.geojson"
        with open(layer_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)
            
        # 5. Update DB
        db = SessionLocal()
        try:
            layer = db.query(Layer).filter(Layer.id == layer_id).first()
            if layer:
                layer.feature_count = feature_count
                # TODO: Calculate and set bounds using geoalchemy2 if needed,
                # For now just update count
                db.commit()
        finally:
            db.close()
            
        logger.info(f"Successfully converted layer {layer_id}. Features: {feature_count}")
        return {"status": "success", "layer_id": layer_id, "feature_count": feature_count}

    except Exception as e:
        logger.error(f"Conversion failed for layer {layer_id}: {str(e)}")
        # Optionally, mark layer as failed in DB
        raise e
    finally:
        # Cleanup temp file
        if temp_file_path.exists():
            temp_file_path.unlink()
