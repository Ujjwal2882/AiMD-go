"""
AiMD-go Upload API Endpoints
Handles CSV, Shapefile, and GeoJSON file uploads with automatic conversion.
"""

import os
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from app.geo.converters import CSVConverter, ShapefileConverter, GeoJSONConverter
from app.geo.validators import GeometryValidator
from app.storage import storage
from app.config import settings

router = APIRouter(prefix="/api", tags=["Upload"])


@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    lat_column: Optional[str] = Form(None),
    lon_column: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
):
    """
    Upload a CSV file and convert to GeoJSON map layer.
    
    - Auto-detects coordinate columns if not specified.
    - Validates coordinate bounds.
    - Creates a new map layer with the converted data.
    """
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_CSV_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")

    try:
        content = await file.read()

        # Convert CSV to GeoJSON
        geojson = CSVConverter.to_geojson(
            content,
            lat_column=lat_column,
            lon_column=lon_column,
        )

        # Validate
        valid, msg = GeometryValidator.validate_feature_collection(geojson)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid geometry: {msg}")

        # Store as layer
        layer_name = os.path.splitext(file.filename)[0]
        layer_meta = storage.save_layer(
            geojson_data=geojson,
            name=layer_name,
            source_type="csv",
            project_id=project_id,
        )

        # Save raw upload
        upload_path = settings.UPLOAD_DIR / file.filename
        with open(upload_path, "wb") as f:
            f.write(content)

        return {
            "status": "success",
            "message": f"CSV uploaded and converted: {len(geojson['features'])} features",
            "layer_id": layer_meta["id"],
            "feature_count": layer_meta["feature_count"],
            "bounds": layer_meta["bounds"],
            "layer_name": layer_name,
            "source_type": "csv",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/preview-csv")
async def preview_csv(file: UploadFile = File(...)):
    """
    Preview a CSV file before uploading.
    Returns headers, sample rows, and auto-detected coordinate columns.
    """
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_CSV_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")

    try:
        content = await file.read()
        preview = CSVConverter.preview_csv(content)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-shapefile")
async def upload_shapefile(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
):
    """
    Upload a Shapefile (as ZIP) and convert to GeoJSON map layer.
    
    The ZIP must contain at least .shp, .shx, and .dbf files.
    """
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_SHAPE_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed for Shapefiles")

    try:
        content = await file.read()

        # Convert Shapefile to GeoJSON
        geojson = ShapefileConverter.to_geojson(content)

        # Validate
        valid, msg = GeometryValidator.validate_feature_collection(geojson)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid geometry: {msg}")

        # Store as layer
        layer_name = os.path.splitext(file.filename)[0]
        layer_meta = storage.save_layer(
            geojson_data=geojson,
            name=layer_name,
            source_type="shapefile",
            project_id=project_id,
        )

        # Save raw upload
        upload_path = settings.UPLOAD_DIR / file.filename
        with open(upload_path, "wb") as f:
            f.write(content)

        return {
            "status": "success",
            "message": f"Shapefile uploaded: {len(geojson['features'])} features",
            "layer_id": layer_meta["id"],
            "feature_count": layer_meta["feature_count"],
            "bounds": layer_meta["bounds"],
            "layer_name": layer_name,
            "source_type": "shapefile",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-geojson")
async def upload_geojson(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
):
    """
    Upload a GeoJSON file directly.
    Validates and normalizes the GeoJSON structure.
    """
    if not file.filename.lower().endswith(tuple(settings.ALLOWED_GEOJSON_EXTENSIONS)):
        raise HTTPException(status_code=400, detail="Only .json and .geojson files are allowed")

    try:
        content = await file.read()

        # Validate and normalize
        geojson = GeoJSONConverter.validate_and_normalize(content)

        # Store as layer
        layer_name = os.path.splitext(file.filename)[0]
        layer_meta = storage.save_layer(
            geojson_data=geojson,
            name=layer_name,
            source_type="geojson",
            project_id=project_id,
        )

        return {
            "status": "success",
            "message": f"GeoJSON uploaded: {len(geojson['features'])} features",
            "layer_id": layer_meta["id"],
            "feature_count": layer_meta["feature_count"],
            "bounds": layer_meta["bounds"],
            "layer_name": layer_name,
            "source_type": "geojson",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
